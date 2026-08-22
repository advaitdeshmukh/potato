"""
export_annotations.py

The bridge between the potato annotation server and the analysis repo.

Reads the raw Potato annotation output (annotation_output/results/<annotator>/
user_state.json) plus the source corpus CSV, and writes wide-format parquet
files to one or more destinations.

    python export_annotations.py                       # write to default destinations
    python export_annotations.py --dry-run             # build, report, write nothing
    python export_annotations.py --out-dir /some/path  # override (repeatable)
    python export_annotations.py --out-dir /path:tasks # ... with only the task files

Column conventions follow narradolma-catalog/SCHEMA.md:

    {dim}_gold                    adjudicated label (see GOLD_ANNOTATORS)
    {dim}_{annotator}             each individual annotator's label
    annotation_order_{annotator}  queue position, for drift analysis

Annotators are discovered from the results directories, so a new one is picked
up automatically; EXCLUDE_ANNOTATORS is the only deny-list.

Outputs (all keyed on safe_instance_id):

    setting_annotations.parquet
    agency_annotations.parquet
    event_relation_annotations.parquet
    all_annotations.parquet          <- outer join of the three tasks
    corpus.parquet                   <- every source row, for feature extraction

Destinations get different subsets, because they consume different things:

    narradolma-human-annotation/data/      all five ('full')
    llm-narrative-annotations/annotated_data/   the three task files ('tasks')

See FILE_SETS below.
"""

import argparse
import csv
import glob
import json
import os

import pandas as pd

# -- Configuration -------------------------------------------------------------

_HERE = os.path.dirname(os.path.abspath(__file__))
BASE  = _HERE                                     # teagan_tasks/
REPOS = os.path.abspath(os.path.join(_HERE, '..', '..'))   # .../Repos/

# Annotator whose labels become the *_gold columns for each task.
# Set a task's value to None to omit gold columns for that task.
GOLD_ANNOTATORS = {
    'setting':        'tejo9855',
    'agency':         'tejo9855',
    'event_relation': 'tejo9855',
}

# Annotator directories that are test accounts / abandoned trials. Everything
# else found on disk is exported, so a new annotator shows up automatically
# instead of being silently dropped until someone remembers to edit a list.
EXCLUDE_ANNOTATORS = {'1'}

# Named sets of output files. Destinations differ in what they actually consume,
# so they are not sent the same thing.
TASK_FILES = ['setting_annotations', 'agency_annotations', 'event_relation_annotations']

FILE_SETS = {
    # Everything: per-annotator labels and annotation_order for agreement and
    # drift work, plus corpus.parquet, which feature extraction needs because it
    # covers all sampled passages rather than only the annotated ones.
    'full':  TASK_FILES + ['all_annotations', 'corpus'],

    # Just the three task parquets. llm-narrative-annotations reads only the
    # *_gold columns from these (LLM-vs-human agreement, NarraBERT training).
    # It does not use all_annotations, and it already means something different
    # by "corpus.parquet" -- the full corpus for scale inference -- so sending
    # one here would invite pointing an inference job at the wrong file.
    'tasks': TASK_FILES,
}

DEFAULT_DESTINATIONS = [
    (os.path.join(REPOS, 'narradolma-human-annotation', 'data'),      'full'),
    (os.path.join(REPOS, 'llm-narrative-annotations', 'annotated_data'), 'tasks'),
]

# -- Task definitions ----------------------------------------------------------

TASKS = {
    'setting': {
        'results_dir': f'{BASE}/setting_annotation_task/annotation_output/results',
        'format':      'likert',
        'dimensions':  [
            'setting_concreteness',
            'setting_temporal_grounding',
            'setting_spatial_grounding',
            'setting_sensory',
        ],
    },
    'agency': {
        'results_dir': f'{BASE}/agency_annotation_task/agency_annotations/annotation_output/results',
        'format':      'likert',
        'dimensions':  [
            'agency_focalization',
            'agency_emotion',
            'agency_cognition',
            'agency_change_of_state',
            'agency_conflict',
        ],
    },
    'event_relation': {
        'results_dir': f'{BASE}/event_relation_annotation_task/annotation_output/results',
        'format':      'event_relation',
        'dimensions':  [
            'span1_is_event',
            'span2_is_event',
            'temporal_order',
            'causality_rating',
        ],
    },
}

DATA_CSV = (f'{BASE}/event_relation_annotation_task/data/'
            'dolma_final_sample_s42_n1250_t0.5_llm_summary_safeid_with_spans.csv')

# -- Annotator discovery -------------------------------------------------------

def discover_annotators(results_dir):
    """Annotator handles found on disk, minus EXCLUDE_ANNOTATORS, sorted.

    An annotator counts as present only if they have a user_state.json — potato
    also drops a potato.log and assorted stray files into the results dir.
    """
    found = []
    for path in sorted(glob.glob(os.path.join(results_dir, '*', 'user_state.json'))):
        handle = os.path.basename(os.path.dirname(path))
        if handle in EXCLUDE_ANNOTATORS:
            continue
        found.append(handle)
    return found

# -- Parsers -------------------------------------------------------------------

def _load_user_state(results_dir, annotator):
    path = os.path.join(results_dir, annotator, 'user_state.json')
    if not os.path.exists(path):
        print(f'    [skip] {annotator}: {path} not found')
        return None
    with open(path) as f:
        return json.load(f)


def _annotation_order(state):
    """{safe_instance_id: 1-based position in the order the annotator saw it}.

    Potato records the queue in instance_id_ordering; ranking only the instances
    that were actually labelled gives a dense sequence, which is what the drift
    analysis needs.
    """
    labelled = state['instance_id_to_label_to_value']
    ordering = state.get('instance_id_ordering') or []
    ranked = [i for i in ordering if i in labelled]
    return {inst_id: n for n, inst_id in enumerate(ranked, start=1)}


def parse_likert(results_dir, annotator, dimensions):
    state = _load_user_state(results_dir, annotator)
    if state is None:
        return pd.DataFrame(columns=['safe_instance_id'] + dimensions)
    order = _annotation_order(state)
    rows = []
    for inst_id, labels in state['instance_id_to_label_to_value'].items():
        row = {'safe_instance_id': inst_id, 'annotation_order': order.get(inst_id)}
        for entry in labels:
            schema = entry[0]['schema']
            if schema in dimensions:
                # last write wins -- Potato stores an edit log per label
                row[schema] = int(entry[0]['name'])
        rows.append(row)
    return pd.DataFrame(rows)


def _load_span_lookup():
    """Return {safe_instance_id: (span1_start, span2_start)} from the data CSV."""
    lookup = {}
    csv.field_size_limit(10 ** 7)
    with open(DATA_CSV) as f:
        for row in csv.DictReader(f):
            raw1 = row.get('assigned_span1') or ''
            raw2 = row.get('assigned_span2') or ''
            if not raw1 or not raw2:
                continue
            try:
                lookup[row['safe_instance_id']] = (json.loads(raw1)[0], json.loads(raw2)[0])
            except (json.JSONDecodeError, IndexError, TypeError):
                pass
    return lookup


def parse_event_relation(results_dir, annotator, span_lookup):
    dims = ['span1_is_event', 'span2_is_event', 'temporal_order', 'causality_rating']
    state = _load_user_state(results_dir, annotator)
    if state is None:
        return pd.DataFrame(columns=['safe_instance_id'] + dims)
    order = _annotation_order(state)
    rows = []
    for inst_id, labels in state['instance_id_to_label_to_value'].items():
        row = {'safe_instance_id': inst_id, 'annotation_order': order.get(inst_id)}
        for entry in labels:
            raw = entry[1]
            if not (isinstance(raw, str) and raw.startswith('[')):
                continue
            try:
                pairs = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if pairs:
                p = pairs[0]
                row['span1_is_event']   = p.get('span1_is_event')
                row['span2_is_event']   = p.get('span2_is_event')
                row['causality_rating'] = p.get('causality_rating')

                temporal_order = p.get('temporal_order')
                # The UI always writes 'span1_first' but may have swapped the
                # spans first, so check which original assigned span ended up
                # in the span1 slot to get the correct label.
                if temporal_order == 'span1_first' and inst_id in span_lookup:
                    orig_s1_start, orig_s2_start = span_lookup[inst_id]
                    ann_span1_start = p.get('span1', {}).get('start')
                    if ann_span1_start == orig_s2_start:
                        temporal_order = 'span2_first'
                row['temporal_order'] = temporal_order
        rows.append(row)
    return pd.DataFrame(rows)

# -- Metadata ------------------------------------------------------------------

def load_metadata():
    csv.field_size_limit(10 ** 7)
    with open(DATA_CSV) as f:
        meta = pd.DataFrame(list(csv.DictReader(f)))
    meta = meta.rename(columns={
        'id':     'dolma_id',
        'shard':  'dolma_shard',
        'source': 'dolma_source',
    })
    for col in ['narrative_confidence', 'topic_confidence', 'event_count', 'verb_count']:
        meta[col] = pd.to_numeric(meta[col], errors='coerce')
    meta['is_noise'] = meta['is_noise'].map({'True': True, 'False': False})
    return meta

# -- Task builder --------------------------------------------------------------

def build_task_df(task_key, cfg):
    """Return a df with safe_instance_id + {dim}_gold + {dim}_{annotator} columns.

    Gold columns come first, then one block per annotator, so the column order
    reads gold-then-individuals within each dimension group.
    """
    dims = cfg['dimensions']
    annotators = discover_annotators(cfg['results_dir'])
    if not annotators:
        print('    no annotator directories found')
        return None
    print(f'    annotators on disk: {", ".join(annotators)}')

    span_lookup = _load_span_lookup() if cfg['format'] == 'event_relation' else None

    ann_dfs = []
    present = []
    for ann in annotators:
        if cfg['format'] == 'likert':
            ann_df = parse_likert(cfg['results_dir'], ann, dims)
        else:
            ann_df = parse_event_relation(cfg['results_dir'], ann, span_lookup)

        if ann_df.empty:
            print(f'    {ann}: no annotations, skipped')
            continue

        renames = {d: f'{d}_{ann}' for d in dims}
        renames['annotation_order'] = f'annotation_order_{ann}'
        ann_df = ann_df.rename(columns=renames)
        ann_dfs.append(ann_df)
        present.append(ann)
        print(f'    {ann}: {len(ann_df)} instances')

    if not ann_dfs:
        print('    no annotation data found')
        return None

    df = ann_dfs[0]
    for other in ann_dfs[1:]:
        df = df.merge(other, on='safe_instance_id', how='outer')

    gold_ann = GOLD_ANNOTATORS.get(task_key)
    gold_cols = []
    if gold_ann is not None:
        if gold_ann not in present:
            print(f'    [warn] gold annotator "{gold_ann}" has no data -- no gold columns')
        else:
            for dim in dims:
                src = f'{dim}_{gold_ann}'
                if src in df.columns:
                    df[f'{dim}_gold'] = df[src]
                    gold_cols.append(f'{dim}_gold')
            print(f'    gold annotator: {gold_ann}')

    # Dimension-grouped ordering: {dim}_gold, then {dim}_<each annotator>.
    label_cols = []
    for dim in dims:
        if f'{dim}_gold' in df.columns:
            label_cols.append(f'{dim}_gold')
        for ann in present:
            if f'{dim}_{ann}' in df.columns:
                label_cols.append(f'{dim}_{ann}')

    order_cols = [f'annotation_order_{a}' for a in present
                  if f'annotation_order_{a}' in df.columns]

    return df[['safe_instance_id'] + label_cols + order_cols]

# -- Main ----------------------------------------------------------------------

def write_all(frames, destinations, dry_run):
    """Write each destination's file set. destinations is [(out_dir, set_name)]."""
    for out_dir, set_name in destinations:
        wanted = [n for n in FILE_SETS[set_name] if n in frames]
        print(f'\n[{out_dir}]  ({set_name}: {len(wanted)} files)')
        if dry_run:
            for name in wanted:
                df = frames[name]
                print(f'  (dry run) {name}.parquet  {len(df)} rows x {len(df.columns)} cols')
            continue
        os.makedirs(out_dir, exist_ok=True)
        for name in wanted:
            df = frames[name]
            path = os.path.join(out_dir, f'{name}.parquet')
            df.to_parquet(path, index=False)
            size = os.path.getsize(path) / 1e6
            print(f'  {name}.parquet  {len(df)} rows x {len(df.columns)} cols  ({size:.1f} MB)')


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--out-dir', action='append', default=None,
                        help='Destination directory (repeatable). Overrides the '
                             'defaults and NARR_ANNOTATION_OUT. Append ":tasks" '
                             'to send only the three task parquets, e.g. '
                             '--out-dir /some/path:tasks. Defaults to the full set.')
    parser.add_argument('--dry-run', action='store_true',
                        help='Build everything and report, but write no files.')
    args = parser.parse_args()

    def parse_dest(raw):
        """'path' or 'path:set_name' -> (path, set_name)."""
        for name in FILE_SETS:
            if raw.endswith(f':{name}'):
                return raw[:-(len(name) + 1)], name
        return raw, 'full'

    if args.out_dir:
        destinations = [parse_dest(p) for p in args.out_dir]
    elif os.environ.get('NARR_ANNOTATION_OUT'):
        destinations = [parse_dest(p)
                        for p in os.environ['NARR_ANNOTATION_OUT'].split(os.pathsep) if p]
    else:
        destinations = DEFAULT_DESTINATIONS

    print('Loading metadata ...')
    meta = load_metadata()
    meta_cols = [c for c in meta.columns if c != 'safe_instance_id']
    print(f'  {len(meta)} instances, {len(meta.columns)} columns\n')

    frames = {'corpus': meta[['safe_instance_id'] + meta_cols]}
    task_dfs = {}

    for task_key, cfg in TASKS.items():
        print(f'[{task_key}]')
        task_df = build_task_df(task_key, cfg)
        if task_df is None:
            continue
        task_dfs[task_key] = task_df

        label_cols = [c for c in task_df.columns if c != 'safe_instance_id']
        df = meta.merge(task_df, on='safe_instance_id', how='right')
        frames[f'{task_key}_annotations'] = df[['safe_instance_id'] + meta_cols + label_cols]
        print()

    # Combined parquet: outer join all tasks, then attach metadata
    if task_dfs:
        combined = list(task_dfs.values())[0]
        for other in list(task_dfs.values())[1:]:
            combined = combined.merge(other, on='safe_instance_id', how='outer')
        all_label_cols = [c for c in combined.columns if c != 'safe_instance_id']
        combined = meta.merge(combined, on='safe_instance_id', how='right')
        frames['all_annotations'] = combined[['safe_instance_id'] + meta_cols + all_label_cols]

    write_all(frames, destinations, args.dry_run)


if __name__ == '__main__':
    main()
