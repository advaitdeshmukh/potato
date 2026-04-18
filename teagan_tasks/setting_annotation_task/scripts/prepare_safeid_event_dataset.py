#!/usr/bin/env python3
"""Create a safe-instance-id version of the Dolma event/verb span dataset.

This script:
- Deduplicates repeated header columns (keeps the first instance).
- Prepends `safe_instance_id` derived from SHA1(id) + row index.
- Preserves event/verb span columns for annotation.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import sys
from pathlib import Path


DEFAULT_INPUT = Path("data/dolma_combined_final_sample_with_llm_summary.csv")
DEFAULT_OUTPUT = Path("data/dolma_combined_final_sample_with_llm_summary_safeid_with_spans.csv")


def build_safe_instance_id(raw_id: str, row_index: int) -> str:
    digest = hashlib.sha1(raw_id.encode("utf-8")).hexdigest()[:16]
    return f"inst_{digest}_{row_index}"


def dedupe_header(header: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for col in header:
        if col in seen:
            continue
        seen.add(col)
        deduped.append(col)
    return deduped


def convert(input_path: Path, output_path: Path) -> None:
    csv.field_size_limit(sys.maxsize)

    with input_path.open("r", encoding="utf-8", newline="") as in_f:
        reader = csv.DictReader(in_f)
        if not reader.fieldnames:
            raise ValueError(f"No header found in {input_path}")

        deduped_columns = dedupe_header(reader.fieldnames)
        output_columns = ["safe_instance_id", *deduped_columns]

        with output_path.open("w", encoding="utf-8", newline="") as out_f:
            writer = csv.DictWriter(out_f, fieldnames=output_columns, extrasaction="ignore")
            writer.writeheader()

            for idx, row in enumerate(reader):
                row_id = str(row.get("id", ""))
                if not row_id:
                    row_id = f"missing_id_{idx}"

                out_row = {col: row.get(col, "") for col in deduped_columns}
                out_row["safe_instance_id"] = build_safe_instance_id(row_id, idx)
                writer.writerow(out_row)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Convert Dolma CSV to safe-id CSV with span columns.")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT, help="Input CSV path")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="Output CSV path")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    convert(args.input, args.output)
    print(f"Wrote: {args.output}")


if __name__ == "__main__":
    main()
