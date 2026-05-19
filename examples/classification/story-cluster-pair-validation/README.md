# Story Cluster Pair Validation

Pairwise cluster-validation task for deciding whether two WildChat story
prompts belong in the same exact prompt cluster.

Run from the repository root:

```bash
python potato/flask_server.py start examples/classification/story-cluster-pair-validation/config.yaml
```

Then open:

```text
http://localhost:9002/
```

For quick debugging:

```bash
python potato/flask_server.py start examples/classification/story-cluster-pair-validation/config.yaml --debug --debug-phase annotation
```

The task data in
`data/story-cluster-pair-validation-qwen35-hosted-input.jsonl` was generated
from the validation answer-key CSV at:

```text
/Users/advaitdeshmukh/Downloads/story_cluster_pair_validation.n-400.same-200.different-200.block-50.seed-42.answer_key.csv
```

The hosted input keeps `id`, block indices, and `text` prompt pairs, but strips
gold labels and source identifiers so annotators only see prompt pairs. The
pairwise decision is saved under `cluster_match.selection` as `same_cluster`,
`different_cluster`, or `tie`.
