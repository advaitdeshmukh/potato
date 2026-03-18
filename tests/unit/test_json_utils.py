import json


from potato.server_utils.json import parse_jsonl_records


def test_parse_jsonl_records_allows_u2028_inside_json_string():
    record = {
        "id": "item-1",
        "text": [
            "first sentence\u2028second sentence",
            "other side",
        ],
    }
    raw = json.dumps(record, ensure_ascii=False) + "\n"

    parsed = parse_jsonl_records(raw, "data/test.jsonl")

    assert parsed == [record]
