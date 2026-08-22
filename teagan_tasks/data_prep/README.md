# data_prep

Scripts that turn a dolma-sampling export into the CSV the Potato tasks serve.
These previously lived in three places with two different behaviours; this is
the single canonical copy. All of them resolve paths from `__file__`, so they
run from any working directory.

## Pipeline

```
dolma-sampling
      │  dolma_final_sample_s42_n1250_t0.5_llm_summary.csv    (not committed here)
      ▼
prepare_safeid_event_dataset.py
      │  adds safe_instance_id, dedupes header columns,
      │  fills topic_classification / topic_confidence blanks
      ▼
      …_safeid_with_spans.csv
      │
      ▼
precompute_span_pairs.py          (event-relation task only)
      │  adds assigned_span1 / assigned_span2 so every annotator
      │  sees the same highlighted pair
      ▼
potato serves it  ──►  annotation_output/results/<annotator>/user_state.json
      │
      ▼
../export_annotations.py          parquet for the analysis repo
```

`sync_pair_policy_to_layout.py` is separate: it pushes `pair_assignment_policy`,
`pair_question_text`, and `event_helper` from `config.yaml` into the JS in
`layouts/task_layout_custom.html`. **Do not run it while annotation is live** —
it rewrites the served layout.

## safe_instance_id

`prepare_safeid_event_dataset.py` mints `inst_<sha1(id)[:16]>_<row_index>`. This
repo is the only place that generates it; `dolma-sampling`,
`llm-narrative-annotations`, `llm_narrative_data_analysis`, and
`narradolma-catalog` all join on it. The format is documented in
`narradolma-catalog/SCHEMA.md`. Changing the derivation invalidates every
downstream join and every existing annotation.

## Note on the event-relation span assignments

Rows after index 310 of the event-relation s42 CSV had their `assigned_span1` /
`assigned_span2` reassigned once, by a one-time script (`random.seed(42)`,
consecutive-neighbour pair selection, LitBank event spans preferred over spaCy
verb spans). That script was non-idempotent — re-running it would re-randomize
spans that annotators have already labelled — so it was deleted after its effect
was baked into the CSV. Its output is what the task now serves.

If the corpus is ever regenerated from scratch, the span-assignment policy needs
to be re-derived; it is not recoverable from the CSV alone.

## Data files

The three task directories each hold their own copy of
`dolma_final_sample_s42_n1250_t0.5_llm_summary_safeid_with_spans.csv`. They are
identical apart from `assigned_span1` / `assigned_span2`, which only the
event-relation task reads. They could be collapsed to one shared copy, but that
means repointing `data_files` in all three configs — worth doing once annotation
is finished, not while the server may resume.
