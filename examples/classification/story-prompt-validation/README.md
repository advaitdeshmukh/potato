# Story Prompt Validation

Simple binary validation task for deciding whether a WildChat user prompt asks
the model to generate a story.

Run from the repository root:

```bash
python potato/flask_server.py start examples/classification/story-prompt-validation/config.yaml
```

Then open:

```text
http://localhost:9007/
```

For quick debugging:

```bash
python potato/flask_server.py start examples/classification/story-prompt-validation/config.yaml --debug --debug-phase annotation
```

The hosted-server input in
`data/story-prompt-validation-qwen35-hosted-input.jsonl` was
converted from:

```text
/Users/advaitdeshmukh/Downloads/qwen35_story_prompt_validation.n-400.pos-200.neg-200.block-50.seed-42.answer_key.csv
```

The annotation data intentionally includes only `id` and `text`, excluding the
Qwen labels and user/IP fields so annotators see a blind prompt classification
task. Use the `id` field to join annotations back to the original answer key if
needed.
