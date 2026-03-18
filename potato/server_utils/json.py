"""
filename: json.py
date: 10/16/2024
author: Tristan Hilbert (aka TFlexSoom)
desc: Json encoding utilities for the potato tool
"""

import dataclasses
import json
from typing import Any

class EnhancedJSONEncoder(json.JSONEncoder):
    def default(self, o):
        if dataclasses.is_dataclass(o):
            return dataclasses.asdict(o)
        return super().default(o)

def easy_json(obj: Any):
    return json.dumps(obj, cls=EnhancedJSONEncoder)


def parse_jsonl_records(raw: str, data_fname: str) -> list[Any]:
    """
    Parse JSONL content using only literal newline boundaries.

    Python's str.splitlines() treats Unicode separators such as U+2028 as line
    breaks, but those characters may appear inside valid JSON strings. JSONL
    files should only be split on actual record delimiters written by the file
    format, i.e. newline characters.
    """
    records = []
    for line_no, line in enumerate(raw.split("\n"), start=1):
        line = line.strip()
        if not line:
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError as e:
            raise ValueError(
                f"Invalid JSON at line {line_no} in {data_fname}: {e}"
            ) from e

    return records
