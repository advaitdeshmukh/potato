---
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

Columns follow the pattern `{dimension}_{role}`, e.g.
`setting_concreteness_gold`, `setting_concreteness_annotator_1`. A secondary
column is left empty (NaN) for instances that annotator did not label.

## Double-annotation coverage

| Task | Instances (gold) | Double-annotated |
|------|------------------|------------------|
| Setting | 400 | 70 passages by `annotator_2`; 29 more by `annotator_1` |
| Agency | 400 | 100 passages by `annotator_1` |
| Event relation | 440 | 251 passages by `annotator_1` |

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

- Setting: concreteness, temporal_grounding, spatial_grounding, sensory
- Agency: focalization, emotion, cognition, change_of_state, conflict

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
| `{dimension}_gold` | Gold/adjudicated label for a dimension. |
| `{dimension}_annotator_1`, `{dimension}_annotator_2` | Secondary-annotator labels (NaN where not annotated). |
