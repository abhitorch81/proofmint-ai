"""Pluggable MomentWeave export adapter.
Optional file: backend/momentweave_exports/<video-id>.json; not a claim of original integration.
Format: {"moments": [{"start_ms":0,"end_ms":5000,"title":"...",
"description":"...", "emotion":"...", "narrative_role":"..."}]}.
Only labels/timing are imported; visual cryptographic evidence is created locally.
"""
import json
from pathlib import Path


def apply_export(video_id, duration, segments, export_dir):
    path = Path(export_dir) / f'{video_id}.json'
    if not path.is_file():
        return segments, False
    payload = json.loads(path.read_text(encoding='utf-8'))
    labels = payload.get('moments', [])
    if not isinstance(labels,list) or not 3 <= len(labels) <= 5:
        raise ValueError('MomentWeave export requires 3-5 moments')
    result=[]
    for idx, label in enumerate(labels):
        if not isinstance(label,dict):
            raise ValueError('Invalid MomentWeave moment')
        st, end = label.get('start_ms'), label.get('end_ms')
        if not isinstance(st,int) or not isinstance(end,int) or st < 0 or end <= st or end > round(duration*1000)+50:
            raise ValueError('Invalid MomentWeave temporal bounds')
        # Pair with nearest local keyframe as approximate image evidence only.
        base = min(segments, key=lambda seg: abs((seg['start_ms']+seg['end_ms'])/2-(st+end)/2)).copy()
        base.update(start_ms=st, end_ms=end, title=str(label.get('title','Moment'))[:160],
                    description=str(label.get('description','MomentWeave annotated moment'))[:2000],
                    emotion=str(label.get('emotion','unclassified'))[:40],
                    narrative_role=str(label.get('narrative_role','unclassified'))[:50],
                    analysis_version='momentweave-export-v1')
        result.append(base)
    if any(result[i]['start_ms'] < result[i-1]['end_ms'] for i in range(1,len(result))):
        raise ValueError('MomentWeave export moments must be nonoverlapping and sorted')
    return result, True
