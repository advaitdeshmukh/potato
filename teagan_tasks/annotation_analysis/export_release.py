"""
export_release.py

Builds the *public HuggingFace release* version of the annotation data:
anonymized annotator columns, column-trimmed, one row per gold-annotated
instance. This is distinct from export_annotations.py (which produces the
gold-only analysis parquets in this directory and is left untouched).

Run:

    python export_release.py

Outputs (into huggingface_release/):
    setting_annotations.parquet
    agency_annotations.parquet
    event_relation_annotations.parquet
    all_annotations.parquet          ← outer join of all three tasks
    README.md                        ← data dictionary

All data-shaping config (annotators, anonymization map, kept columns) lives in
this file. The uploader (upload_to_hf.py) knows none of it — it just pushes the
generated folder.
"""

import os

import pandas as pd

# Reuse the parsers/metadata loader from the analysis exporter.
from export_annotations import (
    parse_likert,
    parse_event_relation,
    _load_span_lookup,
    load_metadata,
)

# ── Configuration ──────────────────────────────────────────────────────────────

_HERE = os.path.dirname(os.path.abspath(__file__))
BASE  = os.path.join(_HERE, '..')
OUT_DIR = os.path.join(_HERE, 'huggingface_release')

# Annotator whose labels become the *_gold columns (the adjudicator).
GOLD_ANNOTATOR = 'tejo9855'

# Real handle → anonymized role. maria is annotator_1 across ALL tasks so the
# same secondary annotator reads consistently. Any annotator not listed here and
# not the gold annotator is dropped from the release.
ANON_MAP = {
    'maria':    'annotator_1',
    'roda9210': 'annotator_2',
}

# Preferred column order for the suffixes within each dimension group.
_ROLE_ORDER = ['gold', 'annotator_1', 'annotator_2']

# Metadata columns kept in the release (names as produced by load_metadata()).
_BASE_META = ['folder', 'dolma_source', 'sampled_text']

TASKS = {
    'setting': {
        'results_dir': f'{BASE}/setting_annotation_task/annotation_output/results',
        'annotators':  ['tejo9855', 'maria', 'roda9210'],   # mppauk dropped
        'format':      'likert',
        'dimensions':  [
            'setting_concreteness',
            'setting_temporal_grounding',
            'setting_spatial_grounding',
            'setting_sensory',
        ],
        'keep_meta':   _BASE_META,
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
        'keep_meta':   _BASE_META,
    },
    'event_relation': {
        'results_dir': f'{BASE}/event_relation_annotation_task/annotation_output/results',
        'annotators':  ['tejo9855', 'maria'],               # adde1214 trial dropped
        'format':      'event_relation',
        'dimensions':  [
            'span1_is_event',
            'span2_is_event',
            'temporal_order',
            'causality_rating',
        ],
        # assigned_span1/2 are needed to interpret the span labels.
        'keep_meta':   _BASE_META + ['assigned_span1', 'assigned_span2'],
    },
}

# ── Builders ────────────────────────────────────────────────────────────────────

def _role_for(annotator):
    """Anonymized suffix for an annotator, or None if it should be dropped."""
    if annotator == GOLD_ANNOTATOR:
        return 'gold'
    return ANON_MAP.get(annotator)


def _ordered_label_cols(dims):
    """Dimension-grouped column order: {dim}_gold, {dim}_annotator_1, ..."""
    return [f'{dim}_{role}' for dim in dims for role in _ROLE_ORDER]


def build_task_labels(task_key, cfg):
    """Return a df: safe_instance_id + anonymized label columns, gold rows only."""
    dims = cfg['dimensions']
    span_lookup = _load_span_lookup() if cfg['format'] == 'event_relation' else None

    gold_df = None
    secondary_dfs = []

    for ann in cfg['annotators']:
        role = _role_for(ann)
        if role is None:
            print(f'    [skip] {ann}: not gold and not in ANON_MAP')
            continue

        if cfg['format'] == 'likert':
            ann_df = parse_likert(cfg['results_dir'], ann, dims)
        else:
            ann_df = parse_event_relation(cfg['results_dir'], ann, span_lookup)

        if ann_df is None or ann_df.empty:
            print(f'    [skip] {ann}: no data')
            continue

        ann_df = ann_df.dropna(subset=dims, how='all')
        ann_df = ann_df.rename(columns={d: f'{d}_{role}' for d in dims})
        print(f'    {ann} → {role}: {len(ann_df)} instances')

        if role == 'gold':
            gold_df = ann_df
        else:
            secondary_dfs.append(ann_df)

    if gold_df is None:
        raise RuntimeError(f'{task_key}: no gold ({GOLD_ANNOTATOR}) annotations found')

    # Left-merge secondaries onto gold so the row set is exactly the gold
    # instances (every secondary annotator is a subset of gold here).
    df = gold_df
    for sec in secondary_dfs:
        df = df.merge(sec, on='safe_instance_id', how='left')

    label_cols = [c for c in _ordered_label_cols(dims) if c in df.columns]
    return df[['safe_instance_id'] + label_cols], label_cols


def attach_metadata(labels_df, keep_meta, meta):
    keep = [c for c in keep_meta if c in meta.columns]
    missing = [c for c in keep_meta if c not in meta.columns]
    if missing:
        print(f'    [warn] metadata missing columns: {missing}')
    out = meta[['safe_instance_id'] + keep].merge(
        labels_df, on='safe_instance_id', how='right')
    label_cols = [c for c in labels_df.columns if c != 'safe_instance_id']
    return out[['safe_instance_id'] + keep + label_cols]

# ── Main ────────────────────────────────────────────────────────────────────────

def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    print('Loading metadata ...')
    meta = load_metadata()
    print(f'  {len(meta)} instances\n')

    task_frames = {}   # task_key -> (df_with_meta, label_cols)

    for task_key, cfg in TASKS.items():
        print(f'[{task_key}]')
        labels_df, label_cols = build_task_labels(task_key, cfg)
        df = attach_metadata(labels_df, cfg['keep_meta'], meta)
        task_frames[task_key] = (df, label_cols, cfg)
        out_path = os.path.join(OUT_DIR, f'{task_key}_annotations.parquet')
        df.to_parquet(out_path, index=False)
        print(f'  → {out_path}   ({len(df)} rows × {len(df.columns)} cols)\n')

    # Combined: outer join label frames, attach the widest metadata (event's).
    print('[all_annotations]')
    combined = None
    all_label_cols = []
    for task_key, cfg in TASKS.items():
        labels_df, label_cols = build_task_labels(task_key, cfg)
        all_label_cols += label_cols
        combined = labels_df if combined is None else combined.merge(
            labels_df, on='safe_instance_id', how='outer')
    keep_meta = TASKS['event_relation']['keep_meta']   # superset (adds spans)
    combined = attach_metadata(combined, keep_meta, meta)
    out_path = os.path.join(OUT_DIR, 'all_annotations.parquet')
    combined.to_parquet(out_path, index=False)
    print(f'  → {out_path}   ({len(combined)} rows × {len(combined.columns)} cols)\n')

    write_readme(task_frames)
    print(f'  → {os.path.join(OUT_DIR, "README.md")}')


def write_readme(task_frames):
    """Emit a data dictionary. Counts are read back from the generated frames."""
    def nn(df, col):
        return int(df[col].notna().sum()) if col in df.columns else 0

    setting_df = task_frames['setting'][0]
    agency_df  = task_frames['agency'][0]
    event_df   = task_frames['event_relation'][0]

    s_dims = TASKS['setting']['dimensions']
    a_dims = TASKS['agency']['dimensions']
    e_dims = TASKS['event_relation']['dimensions']

    md = f"""---
pretty_name: Narrative Annotation Dataset
language:
- en
license: cc-by-4.0
task_categories:
- text-classification
tags:
- narrative
- annotation
- dolma
configs:
- config_name: setting
  data_files: setting_annotations.parquet
- config_name: agency
  data_files: agency_annotations.parquet
- config_name: event_relation
  data_files: event_relation_annotations.parquet
- config_name: all
  data_files: all_annotations.parquet
---

# Narrative annotation dataset

Human annotations for three narrative-analysis tasks — **setting**, **agency**,
and **event relation** — over passages sampled from the Dolma corpus.

## Annotators & anonymization

Annotator identities are anonymized. Each task has a single **gold** adjudicator
plus one or more secondary annotators used for double annotation / agreement.

| Role | Meaning |
|------|---------|
| `gold` | The adjudicated / primary label for every released instance. |
| `annotator_1` | Second independent annotator (present in all three tasks). |
| `annotator_2` | Additional second annotator (setting task only). |

Columns follow the pattern `{{dimension}}_{{role}}`, e.g.
`setting_concreteness_gold`, `setting_concreteness_annotator_1`. A secondary
column is left empty (NaN) for instances that annotator did not label.

## Double-annotation coverage

| Task | Instances (gold) | Double-annotated |
|------|------------------|------------------|
| Setting | {len(setting_df)} | {nn(setting_df, s_dims[0] + '_annotator_2')} passages by `annotator_2`; {nn(setting_df, s_dims[0] + '_annotator_1')} more by `annotator_1` |
| Agency | {len(agency_df)} | {nn(agency_df, a_dims[0] + '_annotator_1')} passages by `annotator_1` |
| Event relation | {len(event_df)} | {nn(event_df, e_dims[0] + '_annotator_1')} passages by `annotator_1` |

Note: for the setting task the two secondary annotators cover **disjoint**
passage sets (`annotator_2`'s and `annotator_1`'s do not overlap), so the total
double-annotated count is their sum.

## Files

- `setting_annotations.parquet` — setting task
- `agency_annotations.parquet` — agency task
- `event_relation_annotations.parquet` — event-relation task
- `all_annotations.parquet` — the three tasks outer-joined on `safe_instance_id`

## Label scales

**Setting** and **agency** dimensions are **1–5 Likert** ratings:

- Setting: {', '.join(d.replace('setting_', '') for d in s_dims)}
- Agency: {', '.join(d.replace('agency_', '') for d in a_dims)}

**Event relation** dimensions:

- `span1_is_event`, `span2_is_event` — boolean (is the marked span an event?)
- `temporal_order` — one of `span1_first`, `span2_first`, `simultaneous`,
  `same_event`, `too_hard_to_tell`
- `causality_rating` — one of `direct_cause`, `enables`, `not_related`

The event spans being judged are given by `assigned_span1` / `assigned_span2`
(`[start, end, text, type]`), whose character offsets index into `sampled_text`.

## Columns

| Column | Description |
|--------|-------------|
| `safe_instance_id` | Unique passage identifier (join key across files). |
| `folder` | Dolma sub-corpus the passage came from. |
| `dolma_source` | Original Dolma source. |
| `sampled_text` | The passage text shown to annotators. |
| `assigned_span1`, `assigned_span2` | *(event file only)* the two spans judged; offsets index into `sampled_text`. |
| `{{dimension}}_gold` | Gold/adjudicated label for a dimension. |
| `{{dimension}}_annotator_1`, `{{dimension}}_annotator_2` | Secondary-annotator labels (NaN where not annotated). |
"""
    with open(os.path.join(OUT_DIR, 'README.md'), 'w') as f:
        f.write(md)


if __name__ == '__main__':
    main()
