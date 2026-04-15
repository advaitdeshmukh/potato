#!/usr/bin/env python3
"""Sync pair policy, question text, and event helper from config into task_layout_custom.html."""

from __future__ import annotations

import json
import re
from pathlib import Path

import yaml


ROOT = Path("/Users/tejo9855/Documents/Research/potato_hosting/potato/event_relation_annotation_task/")
CONFIG_PATH = ROOT / "config.yaml"
LAYOUT_PATH = ROOT / "layouts" / "task_layout_custom.html"

START = "/* PAIR_POLICY_START */"
END = "/* PAIR_POLICY_END */"
QSTART = "/* QUESTION_TEXT_START */"
QEND = "/* QUESTION_TEXT_END */"
HSTART = "/* EVENT_HELPER_START */"
HEND = "/* EVENT_HELPER_END */"


def main() -> int:
    config = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8")) or {}
    policy = config.get("pair_assignment_policy")
    if not isinstance(policy, dict):
        raise ValueError("pair_assignment_policy missing or invalid in annotation_config.yaml")
    questions = config.get("pair_question_text")
    if not isinstance(questions, dict):
        raise ValueError("pair_question_text missing or invalid in annotation_config.yaml")
    helper = config.get("event_helper", {})
    if not isinstance(helper, dict):
        raise ValueError("event_helper must be a mapping in annotation_config.yaml")

    policy_json = json.dumps(policy, indent=2, sort_keys=True)
    replacement = (
        f"{START}\n"
        f"  var _rawPairPolicyFromConfig = {policy_json};\n"
        f"  {END}"
    )
    questions_json = json.dumps(questions, indent=2, sort_keys=True)
    qreplacement = (
        f"{QSTART}\n"
        f"  var _questionTextFromConfig = {questions_json};\n"
        f"  {QEND}"
    )
    helper_json = json.dumps(helper, indent=2, sort_keys=True)
    hreplacement = (
        f"{HSTART}\n"
        f"  var _eventHelperFromConfig = {helper_json};\n"
        f"  {HEND}"
    )

    text = LAYOUT_PATH.read_text(encoding="utf-8")
    pattern = re.compile(
        re.escape(START) + r"[\s\S]*?" + re.escape(END),
        flags=re.MULTILINE,
    )
    if not pattern.search(text):
        raise ValueError("Policy marker block not found in layout file")
    qpattern = re.compile(
        re.escape(QSTART) + r"[\s\S]*?" + re.escape(QEND),
        flags=re.MULTILINE,
    )
    if not qpattern.search(text):
        raise ValueError("Question-text marker block not found in layout file")
    hpattern = re.compile(
        re.escape(HSTART) + r"[\s\S]*?" + re.escape(HEND),
        flags=re.MULTILINE,
    )
    if not hpattern.search(text):
        raise ValueError("Event-helper marker block not found in layout file")

    updated = pattern.sub(lambda _: replacement, text, count=1)
    updated = qpattern.sub(lambda _: qreplacement, updated, count=1)
    updated = hpattern.sub(lambda _: hreplacement, updated, count=1)
    LAYOUT_PATH.write_text(updated, encoding="utf-8")
    print(f"Synced pair policy + question text + event helper from {CONFIG_PATH} -> {LAYOUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
