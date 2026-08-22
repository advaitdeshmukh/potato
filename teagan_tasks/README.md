# teagan_tasks

Three Potato annotation tasks — **agency**, **setting**, and **event relation** —
plus the data prep that feeds them and the exporter that ships their output.

Analysis lives in a separate repo: **[narradolma-human-annotation](https://github.com/johnsont4/narradolma-human-annotation)**.
Nothing here imports from it, and nothing there reads raw annotation output.

## Layout

```
setting_annotation_task/           annotation_config.yaml, layouts/, data/, annotation_output/
agency_annotation_task/
  agency_annotations/              (nested one level deeper than the others)
event_relation_annotation_task/    config.yaml (not annotation_config.yaml)
data_prep/                         corpus -> served CSV; see data_prep/README.md
export_annotations.py              annotation output -> parquet, for downstream repos
```

## Running a task

```bash
python -m potato start setting_annotation_task/annotation_config.yaml
python -m potato start agency_annotation_task/agency_annotations/annotation_config.yaml
python -m potato start event_relation_annotation_task/config.yaml
```

## Exporting annotations

After a round of annotation:

```bash
python export_annotations.py            # writes parquet to both destinations
python export_annotations.py --dry-run  # preview, write nothing
python export_annotations.py --out-dir /somewhere/else
```

Two default destinations, which get different file sets because they consume
different things:

| Destination | Set | Files | Why |
|---|---|---|---|
| `narradolma-human-annotation/data/` | `full` | all five | agreement and drift need per-annotator columns; `corpus.parquet` covers all 1072 passages, which feature extraction needs |
| `llm-narrative-annotations/annotated_data/` | `tasks` | the three task parquets | reads only `*_gold` columns, for LLM-vs-human agreement and NarraBERT training |

`all_annotations.parquet` is unused by the second repo, and `corpus.parquet`
would collide with what that repo already calls corpus.parquet — the full corpus
for scale inference — so neither is sent there.

Override with `--out-dir` (repeatable) or `NARR_ANNOTATION_OUT`. Both default to
the full set; append `:tasks` for the three-file set:

```bash
python export_annotations.py --out-dir /some/path         # full
python export_annotations.py --out-dir /some/path:tasks   # three task parquets
```

Annotators are discovered from the `annotation_output/results/` directories, so
a new annotator is exported automatically. Test accounts are excluded via
`EXCLUDE_ANNOTATORS` at the top of the script (currently `{'1'}`).

Output columns follow `narradolma-catalog/SCHEMA.md`:

| Pattern | Meaning |
|---|---|
| `{dim}_gold` | the adjudicator's label (`GOLD_ANNOTATORS`, currently `tejo9855`) |
| `{dim}_{annotator}` | each individual annotator's label |
| `annotation_order_{annotator}` | queue position, for drift analysis |

## Known rough edges

- The agency task is nested one directory deeper than the other two, and the
  event task's config is `config.yaml` rather than `annotation_config.yaml`.
- Each task directory holds its own copy of the same source CSV. They differ
  only in `assigned_span1`/`assigned_span2`, which only the event task reads.
  Collapsing them means repointing `data_files` in all three configs — best done
  when annotation is finished rather than while the server may resume.
