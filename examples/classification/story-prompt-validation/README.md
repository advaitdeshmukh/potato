# Story Prompt Validation

Simple binary validation task for deciding whether a WildChat user prompt asks
the model to generate a story.

Run from the repository root:

```bash
python potato/flask_server.py start examples/classification/story-prompt-validation/config.yaml -p 8000
```

For quick debugging:

```bash
python potato/flask_server.py start examples/classification/story-prompt-validation/config.yaml -p 8000 --debug --debug-phase annotation
```

The task data in `data/story-prompt-validation-input.jsonl` was converted from:

```text
/Users/advaitdeshmukh/ForkingPrompts/Wildchat/data/wildchat_4p8m_cluster_first/08_story_prompt_cluster_purity_roberta_seed28/04_human_validation/roberta_story_prompt_validation.n-400.pos-200.neg-200.block-50.seed-42.answer_key.csv
```

The annotation data intentionally excludes the RoBERTa labels and user/IP
fields so annotators see a blind prompt classification task. Use the `id`
field to join annotations back to the original answer key if needed.
