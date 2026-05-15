"""
update_event_relation_spans.py

For rows AFTER index 310 in the event-relation annotation CSV:
  - If the row has >= 2 LitBank event spans: randomly choose a consecutive
    neighboring pair (index i and i+1 in the sorted list).
  - Otherwise, if the row has >= 2 spaCy verb spans: same consecutive logic.
  - If neither condition holds: leave assigned_span1 / assigned_span2 as null.

Span ordering: assigned_span1 always has the lower start offset (guaranteed by
consecutive selection since spans are sorted by start position).
Random seed: 42 (matches the original corpus sampling seed).

Run:
    python update_event_relation_spans.py
"""

import csv
import json
import random

DATA_PATH = (
    '/Users/tejo9855/Documents/Research/Pre Training Narrative Project/'
    'Repos/potato/teagan_tasks/event_relation_annotation_task/data/'
    'dolma_final_sample_s42_n1250_t0.5_llm_summary_safeid_with_spans.csv'
)

RANDOM_SEED   = 42
CUTOFF_INDEX  = 310   # rows with index <= CUTOFF_INDEX are left unchanged

random.seed(RANDOM_SEED)

csv.field_size_limit(10 ** 7)
with open(DATA_PATH, newline='') as f:
    reader    = csv.DictReader(f)
    fieldnames = reader.fieldnames
    rows      = list(reader)

stats = {'event': 0, 'verb': 0, 'null': 0, 'skipped': 0}

for i, row in enumerate(rows):
    if i <= CUTOFF_INDEX:
        stats['skipped'] += 1
        continue

    try:
        event_spans = json.loads(row.get('event_spans') or '[]')
    except (json.JSONDecodeError, TypeError):
        event_spans = []

    try:
        verb_spans = json.loads(row.get('verb_spans') or '[]')
    except (json.JSONDecodeError, TypeError):
        verb_spans = []

    if len(event_spans) >= 2:
        i = random.randrange(len(event_spans) - 1)
        chosen    = [event_spans[i], event_spans[i + 1]]
        span_type = 'event'
        stats['event'] += 1
    elif len(verb_spans) >= 2:
        i = random.randrange(len(verb_spans) - 1)
        chosen    = [verb_spans[i], verb_spans[i + 1]]
        span_type = 'verb'
        stats['verb'] += 1
    else:
        row['assigned_span1'] = 'null'
        row['assigned_span2'] = 'null'
        stats['null'] += 1
        continue

    # Consecutive spans are already sorted by start position
    row['assigned_span1'] = json.dumps(chosen[0][:3] + [span_type])
    row['assigned_span2'] = json.dumps(chosen[1][:3] + [span_type])

with open(DATA_PATH, 'w', newline='') as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)

print('Done.')
print(f"  Skipped (index ≤ {CUTOFF_INDEX}):  {stats['skipped']}")
print(f"  Updated via LitBank events:       {stats['event']}")
print(f"  Updated via verb fallback:        {stats['verb']}")
print(f"  Left as null (not enough spans):  {stats['null']}")
