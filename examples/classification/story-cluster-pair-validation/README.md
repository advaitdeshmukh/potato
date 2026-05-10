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

The task data in `data/story-cluster-pair-validation-input.jsonl` was copied
from the blind validation JSONL at:

```text
/Users/advaitdeshmukh/ForkingPrompts/Wildchat/data/wildchat_4p8m_cluster_first/09_story_prompt_exact_clusters_roberta_seed28/10_human_cluster_validation/story_cluster_pair_validation.n-400.same-200.different-200.block-50.seed-42.blind.jsonl
```

The source folder also contains CSV metadata and an answer key, but this task
uses the blind JSONL so annotators only see prompt pairs. The pairwise decision
is saved under `cluster_match.selection` as `same_cluster`,
`different_cluster`, or `tie`.
