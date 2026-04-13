#!/usr/bin/env python3
"""Pre-compute a fixed span pair for every instance in the Dolma event dataset.

Replicates the deterministic logic from task_layout_custom.html:
  seed = simpleHash(instanceKey + '|' + sampledText)
  mode = schedule[seed % totalWeight].mode          (deterministic, not counter-based)
  pair = pickOneNeighborPair(mode-filtered spans, seed)

Adds two columns to the CSV:
  assigned_span1  [start, end, token, type]
  assigned_span2  [start, end, token, type]

The layout JS reads these columns so every annotator always sees the same
highlighted spans, regardless of their browser's localStorage state.

Usage (run from event_relation_annotation_task/):
  python precompute_span_pairs.py
  python precompute_span_pairs.py --csv data/other.csv --output data/other_with_pairs.csv
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

import yaml

DEFAULT_CSV = Path("data/dolma_combined_final_sample_600_with_llm_summary_safeid_with_spans.csv")
DEFAULT_CONFIG = Path("config.yaml")


# ---------------------------------------------------------------------------
# Hash — must match simpleHash() in task_layout_custom.html exactly.
# JS: h = (Math.imul(h ^ charCode, 0x9e3779b9)) >>> 0
# ---------------------------------------------------------------------------
def simple_hash(s: str) -> int:
    h = 0x9E3779B9
    for ch in s:
        h = ((h ^ ord(ch)) * 0x9E3779B9) & 0xFFFFFFFF
    return h


# ---------------------------------------------------------------------------
# Span helpers — must match mergeAndSortSpans() in the layout.
# event_spans / verb_spans from CSV are lists of [start, end, token].
# Verbs that overlap any event span are dropped (JS does the same).
# ---------------------------------------------------------------------------
def merge_and_sort_spans(
    event_spans: list[list],
    verb_spans: list[list],
) -> list[dict]:
    events = [{"start": s[0], "end": s[1], "token": s[2], "type": "event"} for s in event_spans]

    def overlaps_any_event(v: list) -> bool:
        for e in events:
            if not (v[1] <= e["start"] or v[0] >= e["end"]):
                return True
        return False

    verbs = [
        {"start": s[0], "end": s[1], "token": s[2], "type": "verb"}
        for s in verb_spans
        if not overlaps_any_event(s)
    ]

    all_spans = events + verbs
    all_spans.sort(key=lambda s: s["start"])
    return all_spans


def pick_one_neighbor_pair(span_indices: list[int], seed: int) -> list[int] | None:
    """Replicates pickOneNeighborPair() in the layout."""
    n = len(span_indices)
    if n < 2:
        return None
    if n == 2:
        return [span_indices[0], span_indices[1]]
    i = seed % (n - 1)
    return [span_indices[i], span_indices[i + 1]]


def choose_pair_mode(policy: dict, seed: int) -> str:
    """Deterministic mode selection driven by seed (not localStorage counter)."""
    total_weight = sum(item["weight"] for item in policy["schedule"])
    if total_weight <= 0:
        total_weight = 1
    slot = seed % total_weight
    running = 0
    for item in policy["schedule"]:
        running += item["weight"]
        if slot < running:
            return item["mode"]
    return policy["schedule"][0]["mode"]


def assign_pair(
    all_spans: list[dict],
    seed: int,
    policy: dict,
) -> list[int] | None:
    """Replicates assignSinglePair() in the layout (minus localStorage)."""
    if len(all_spans) < 2:
        return None

    mode = choose_pair_mode(policy, seed)
    mode_def = policy.get("mode_definitions", {}).get(mode, {})
    allowed_types: list[str] = mode_def.get("span_types", [])

    all_idx = list(range(len(all_spans)))
    mode_idx = [i for i, s in enumerate(all_spans) if s["type"] in allowed_types]

    pair = pick_one_neighbor_pair(mode_idx, seed)
    if pair:
        return pair
    # Fallback: any two adjacent spans
    return pick_one_neighbor_pair(all_idx, seed)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(
        description="Pre-compute fixed span pairs for every instance in the annotation CSV."
    )
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV, help="Input CSV path")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG, help="config.yaml path")
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output CSV path (default: overwrite input CSV)",
    )
    args = parser.parse_args()

    config = yaml.safe_load(args.config.read_text(encoding="utf-8"))
    policy: dict = config["pair_assignment_policy"]

    csv.field_size_limit(sys.maxsize)

    with args.csv.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        fieldnames: list[str] = list(reader.fieldnames or [])
        rows: list[dict] = list(reader)

    # Append new columns if not already present
    for col in ("assigned_span1", "assigned_span2"):
        if col not in fieldnames:
            fieldnames.append(col)

    n_assigned = 0
    n_fallback = 0
    n_empty = 0

    for row in rows:
        instance_key = row.get("safe_instance_id") or row.get("id", "")
        text = row.get("sampled_text", "")

        try:
            event_spans: list = json.loads(row.get("event_spans") or "[]")
        except (json.JSONDecodeError, TypeError):
            event_spans = []
        try:
            verb_spans: list = json.loads(row.get("verb_spans") or "[]")
        except (json.JSONDecodeError, TypeError):
            verb_spans = []

        all_spans = merge_and_sort_spans(event_spans, verb_spans)
        seed = simple_hash(instance_key + "|" + text)
        pair = assign_pair(all_spans, seed, policy)

        if pair and len(pair) == 2:
            s1, s2 = all_spans[pair[0]], all_spans[pair[1]]
            row["assigned_span1"] = json.dumps([s1["start"], s1["end"], s1["token"], s1["type"]])
            row["assigned_span2"] = json.dumps([s2["start"], s2["end"], s2["token"], s2["type"]])
            n_assigned += 1
        else:
            row["assigned_span1"] = ""
            row["assigned_span2"] = ""
            n_empty += 1

    output_path = args.output or args.csv
    with output_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    print(f"Wrote {len(rows)} rows to {output_path}")
    print(f"  Pairs assigned : {n_assigned}")
    print(f"  No pair (empty): {n_empty}")
    print()
    print("Sample assignments:")
    for row in rows[:5]:
        print(f"  {row['safe_instance_id']}")
        print(f"    span1 = {row['assigned_span1']}")
        print(f"    span2 = {row['assigned_span2']}")


if __name__ == "__main__":
    main()
