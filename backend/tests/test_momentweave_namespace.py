import json
from pathlib import Path

from app.momentweave_adapter import apply_export


def test_momentweave_import_contract(tmp_path):
    segments = [
        dict(start_ms=0, end_ms=2000, jpg=b"jpeg", title="Original", description="Motion",
             emotion="unclassified", narrative_role="opening", analysis_version="opencv-scene-motion-v1"),
    ]
    vid = "test-video"
    (tmp_path / (vid + ".json")).write_text(json.dumps({"moments": [
        {"start_ms": 0, "end_ms": 2000, "title": "Opening"},
        {"start_ms": 2000, "end_ms": 4000, "title": "Action"},
        {"start_ms": 4000, "end_ms": 6000, "title": "Closing"},
    ]}), encoding="utf-8")
    annotated, used = apply_export(vid, 6.0, segments, tmp_path)
    assert used and len(annotated) == 3
    assert all(m["analysis_version"] == "momentweave-export-v1" for m in annotated)
    assert [m["title"] for m in annotated] == ["Opening", "Action", "Closing"]
