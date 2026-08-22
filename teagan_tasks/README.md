# teagan_tasks

Three Potato annotation tasks — **agency**, **setting**, and **event relation** —
plus the data prep that feeds them and the exporter that ships their output.

This directory owns annotation only. Analysis lives in a separate repo,
**[narradolma-human-annotation](https://github.com/johnsont4/narradolma-human-annotation)**:
nothing here imports from it, and nothing there reads raw annotation output.

```
dolma-sampling ──► data_prep/ ──► potato serves the task ──► annotation_output/
                                                                    │
                                                   export_annotations.py
                                                                    │
                        ┌───────────────────────────────────────────┴────────┐
                        ▼                                                    ▼
        narradolma-human-annotation/data/            llm-narrative-annotations/annotated_data/
        agreement, EDA, figures, HF release          LLM-vs-human eval, NarraBERT training
```

## Layout

```
setting_annotation_task/           annotation_config.yaml, layouts/, data/, annotation_output/
agency_annotation_task/
  agency_annotations/              (nested one level deeper than the others)
event_relation_annotation_task/    config.yaml (not annotation_config.yaml)
data_prep/                         corpus -> served CSV; see data_prep/README.md
export_annotations.py              annotation output -> parquet, for downstream repos
```

Each task directory holds:

| Path | What |
|---|---|
| `annotation_config.yaml` | schemes, scales, definitions, examples, `data_files` |
| `layouts/task_layout_custom.html` | the annotation UI |
| `data/…_safeid_with_spans.csv` | the served corpus, keyed by `safe_instance_id` |
| `annotation_output/results/<annotator>/user_state.json` | raw output — the source of truth |

`user_state.json` is what Potato writes as people annotate. It is the only
durable record of the labels; everything downstream is derived from it by
`export_annotations.py`.

## The tasks

**Setting** and **agency** are 1–5 Likert scales, nine dimensions in total. The
config carries a full definition and worked examples per dimension; the codebook
is linked from `annotation_codebook_url` in `setting_annotation_task/annotation_config.yaml`.

| Task | Dimension | Question |
|---|---|---|
| setting | `setting_concreteness` | How concrete is the language of the text? |
| setting | `setting_temporal_grounding` | How strongly does the text create a sense of being anchored in a particular time? |
| setting | `setting_spatial_grounding` | How strongly does the text create a sense of being anchored in a particular place? |
| setting | `setting_sensory` | How central are sensory details to the text? |
| agency | `agency_focalization` | How central is a specific character's/narrator's perspective? |
| agency | `agency_emotion` | How central are a character's emotional states? |
| agency | `agency_cognition` | How central are a character's thoughts, reasoning, or motivations? |
| agency | `agency_change_of_state` | How central is a change in a character's condition or state? |
| agency | `agency_conflict` | How central is conflict involving characters? |

All nine are 1–5. (Some older analysis code assumed setting was 1–3; it is not.)

**Event relation** works differently. Rather than a Likert scheme it uses a
custom layout that shows two pre-assigned spans per passage and asks four
questions:

| Column | Values |
|---|---|
| `span1_is_event` / `span2_is_event` | true / false |
| `temporal_order` | `span1_first`, `span2_first`, `simultaneous`, `same_event`, `too_hard_to_tell` |
| `causality_rating` | `direct_cause`, `enables`, `not_related` |

The span pair is fixed per instance by `data_prep/precompute_span_pairs.py`, so
every annotator sees the same pair. `pair_assignment_policy` in `config.yaml`
weights which span types are drawn (4:1 LitBank events to a mixed event/verb
pool); `data_prep/sync_pair_policy_to_layout.py` pushes that policy and the
question text into the layout's JS.

> **Interpreting `temporal_order`:** the UI always writes `span1_first`, but may
> have swapped the two spans before displaying them. `export_annotations.py`
> corrects this by checking which original span landed in the span1 slot. The
> parquet is corrected; raw `user_state.json` is **not**. Anything reading the
> raw files directly must apply the same correction.

## Running a task

```bash
python -m potato start setting_annotation_task/annotation_config.yaml
python -m potato start agency_annotation_task/agency_annotations/annotation_config.yaml
python -m potato start event_relation_annotation_task/config.yaml
```

## Exporting annotations

After a round of annotation:

```bash
python export_annotations.py            # write to the default destinations
python export_annotations.py --dry-run  # preview, write nothing
```

Five parquets are built, all keyed on `safe_instance_id`:

| File | Rows | Contents |
|---|---|---|
| `setting_annotations.parquet` | 400 | one task, gold-annotated instances |
| `agency_annotations.parquet` | 405 | |
| `event_relation_annotations.parquet` | 440 | |
| `all_annotations.parquet` | 457 | the three outer-joined |
| `corpus.parquet` | 1072 | every sampled passage, metadata only, no labels |

The two destinations get different subsets, because they consume different things:

| Destination | Set | Files | Why |
|---|---|---|---|
| `narradolma-human-annotation/data/` | `full` | all five | agreement needs per-annotator columns, drift needs `annotation_order_*`, and feature extraction needs `corpus.parquet`, which covers all 1072 passages rather than only the annotated ones |
| `llm-narrative-annotations/annotated_data/` | `tasks` | the three task files | reads only `*_gold` columns, for LLM-vs-human agreement and NarraBERT training |

`all_annotations.parquet` is unused by the second repo, and `corpus.parquet`
would collide with what that repo already calls `corpus.parquet` — the full
corpus for scale inference — so neither is sent there.

Override with `--out-dir` (repeatable) or `NARR_ANNOTATION_OUT`. Both default to
the full set; append `:tasks` for the three-file set:

```bash
python export_annotations.py --out-dir /some/path         # full
python export_annotations.py --out-dir /some/path:tasks   # three task parquets
```

### Output columns

Naming follows `narradolma-catalog/SCHEMA.md`, so these join cleanly against the
rest of the project:

| Pattern | Meaning |
|---|---|
| `{dim}_gold` | the adjudicator's label (`GOLD_ANNOTATORS`, currently `tejo9855` for all three tasks) |
| `{dim}_{annotator}` | each individual annotator's label |
| `annotation_order_{annotator}` | that annotator's queue position for the instance, from Potato's `instance_id_ordering`; used for drift analysis |

Filtering label columns by suffix will also match `annotation_order_*`, since it
ends with the annotator handle too. Exclude it explicitly.

### Annotators

Annotators are **discovered from the `annotation_output/results/` directories**,
not from a hardcoded list, so a new annotator is exported automatically. Only
`EXCLUDE_ANNOTATORS` at the top of the script filters anything out (currently
`{'1'}`, a test account).

Current roster, and how many instances each has labelled:

| Task | Gold | Secondary annotators |
|---|---|---|
| setting | tejo9855 (400) | roda9210 (70), mppauk (50), akritidhasmana (41), maria (29) |
| agency | tejo9855 (405) | maria (100) |
| event relation | tejo9855 (440) | maria (251), akritidhasmana (15), adde1214 (6) |

Every secondary annotator has worked on a strict subset of the gold instances,
so the row count of each parquet is the gold annotator's count.

Note that the public HuggingFace release drops anyone not in its `ANON_MAP`
(over in `narradolma-human-annotation/release/export_release.py`). Adding an
annotator here does not add them to a release.

## Known rough edges

- The agency task is nested one directory deeper than the other two, and the
  event task's config is `config.yaml` rather than `annotation_config.yaml`.
- Each task directory holds its own copy of the same source CSV. They are
  identical except for `assigned_span1`/`assigned_span2`, which only the event
  task reads. Collapsing them to one shared copy means repointing `data_files`
  in all three configs — best done once annotation is finished, not while the
  server may resume.
- `old_annotations/` is tracked in git but deleted from the working tree.
