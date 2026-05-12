"""
export_annotations.py

Converts Potato annotation results for each task to wide-format parquet files.
One row per annotated instance; one column per annotator per dimension.

Gold label columns ({dim}_gold) copy the specified annotator's values.
Configure GOLD_ANNOTATORS and OUT_DIR below, then run:

    python export_annotations.py

Output files:
    setting_annotations.parquet
    agency_annotations.parquet
    event_relation_annotations.parquet
"""

import csv
import json
import os

import pandas as pd

# ── Configuration ──────────────────────────────────────────────────────────────

_HERE = os.path.dirname(os.path.abspath(__file__))
BASE  = os.path.join(_HERE, '..')

# Annotator whose labels become the *_gold columns for each task.
# Set a task's value to None to omit gold columns for that task.
GOLD_ANNOTATORS = {
    'setting':        'tejo9855',
    'agency':         'tejo9855',
    'event_relation': 'tejo9855',
}

OUT_DIR = _HERE

# ── Task definitions ───────────────────────────────────────────────────────────

TASKS = {
    'setting': {
        'results_dir': f'{BASE}/setting_annotation_task/annotation_output/results',
        'annotators':  ['mppauk', 'tejo9855', 'roda9210'],
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
        'annotators':  ['tejo9855', 'maria'],
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
        'annotators':  ['tejo9855', 'adde1214', '1'],
        'format':      'event_relation',
        'dimensions':  [
            'span1_is_event',
            'span2_is_event',
            'temporal_order',
            'causality_rating',
        ],
    },
}

DATA_CSV     = (f'{BASE}/setting_annotation_task/data/'
                'dolma_final_sample_s42_n1250_t0.5_llm_summary_safeid_with_spans.csv')
FEATURES_CSV = f'{BASE}/automatic_features/features.csv'

# ── Parsers ────────────────────────────────────────────────────────────────────

def _load_user_state(results_dir, annotator):
    path = os.path.join(results_dir, annotator, 'user_state.json')
    if not os.path.exists(path):
        print(f'    [skip] {annotator}: {path} not found')
        return None
    with open(path) as f:
        return json.load(f)


def parse_likert(results_dir, annotator, dimensions):
    state = _load_user_state(results_dir, annotator)
    if state is None:
        return pd.DataFrame(columns=['safe_instance_id'] + dimensions)
    rows = []
    for inst_id, labels in state['instance_id_to_label_to_value'].items():
        row = {'safe_instance_id': inst_id}
        for entry in labels:
            schema = entry[0]['schema']
            if schema in dimensions:
                # last write wins — Potato stores an edit log per label
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
    rows = []
    for inst_id, labels in state['instance_id_to_label_to_value'].items():
        row = {'safe_instance_id': inst_id}
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

# ── Metadata + features ────────────────────────────────────────────────────────

def load_metadata():
    csv.field_size_limit(10 ** 7)
    with open(DATA_CSV) as f:
        meta = pd.DataFrame(list(csv.DictReader(f)))
    for col in ['narrative_confidence', 'topic_confidence', 'event_count', 'verb_count']:
        meta[col] = pd.to_numeric(meta[col], errors='coerce')
    meta['is_noise'] = meta['is_noise'].map({'True': True, 'False': False})
    feat = pd.read_csv(FEATURES_CSV)
    return meta.merge(feat, on='safe_instance_id', how='left')

# ── Task builder ───────────────────────────────────────────────────────────────

def build_task_df(task_key, cfg, meta):
    dims = cfg['dimensions']
    ann_dfs = []

    span_lookup = _load_span_lookup() if cfg['format'] == 'event_relation' else None

    for ann in cfg['annotators']:
        if cfg['format'] == 'likert':
            ann_df = parse_likert(cfg['results_dir'], ann, dims)
        else:
            ann_df = parse_event_relation(cfg['results_dir'], ann, span_lookup)

        if ann_df.empty:
            continue

        # suffix every dimension column with the annotator name
        ann_df = ann_df.rename(columns={d: f'{d}_{ann}' for d in dims})
        ann_dfs.append(ann_df)
        print(f'    {ann}: {len(ann_df)} instances')

    if not ann_dfs:
        print('    no annotation data found')
        return None

    # outer-join all annotators so every annotated instance is included
    df = ann_dfs[0]
    for other in ann_dfs[1:]:
        df = df.merge(other, on='safe_instance_id', how='outer')

    # gold label columns
    gold_ann = GOLD_ANNOTATORS.get(task_key)
    if gold_ann is not None:
        if gold_ann not in cfg['annotators']:
            print(f'    [warn] gold annotator "{gold_ann}" not in annotators list — skipping gold columns')
        else:
            for dim in dims:
                src = f'{dim}_{gold_ann}'
                if src in df.columns:
                    df[f'{dim}_gold'] = df[src]
            print(f'    gold annotator: {gold_ann}')

    # attach metadata + features (left join; keeps only annotated instances)
    annotation_cols = [c for c in df.columns if c != 'safe_instance_id']
    df = meta.merge(df, on='safe_instance_id', how='right')

    # column order: safe_instance_id | metadata | features | annotations | gold
    meta_cols    = [c for c in meta.columns if c != 'safe_instance_id']
    gold_cols    = [c for c in df.columns if c.endswith('_gold')]
    ann_cols     = [c for c in annotation_cols if not c.endswith('_gold')]
    ordered_cols = ['safe_instance_id'] + meta_cols + ann_cols + gold_cols
    df = df[[c for c in ordered_cols if c in df.columns]]

    return df

# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    print('Loading metadata + features ...')
    meta = load_metadata()
    print(f'  {len(meta)} instances, {len(meta.columns)} columns\n')

    for task_key, cfg in TASKS.items():
        print(f'[{task_key}]')
        df = build_task_df(task_key, cfg, meta)
        if df is None:
            continue
        out_path = os.path.join(OUT_DIR, f'{task_key}_annotations.parquet')
        df.to_parquet(out_path, index=False)
        print(f'  → {out_path}')
        print(f'     {len(df)} rows × {len(df.columns)} columns\n')


if __name__ == '__main__':
    main()
