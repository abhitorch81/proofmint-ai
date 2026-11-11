"""MomentGraph edges and labels derived from imported *real* MomentWeave exports.
No invented emotion inference and no database migration required.
"""
import json
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select
from .db import get_db
from .models import Moment, VideoAsset
from .config import get_settings

router=APIRouter(prefix='/api/videos',tags=['MomentWeave integration'])

@router.get('/{video_id}/narrative-graph')
def narrative_graph(video_id: str, db: Session=Depends(get_db)):
    video=db.get(VideoAsset,video_id)
    if video is None: raise HTTPException(404,'Video not found')
    moments=db.scalars(select(Moment).where(Moment.video_id==video_id).order_by(Moment.start_ms)).all()
    path=Path(get_settings().momentweave_export_dir)/f'{video_id}.json'
    imported=False
    edges=[]
    if path.is_file():
        try:
            content=json.loads(path.read_text(encoding='utf-8'))
            imported=True
        except (ValueError, OSError):
            content={}
        # Accept only bounded, documented relationship indices.
        for edge in content.get('edges',[]) if isinstance(content.get('edges',[]),list) else []:
            if not isinstance(edge,dict):continue
            src=edge.get('source_index'); dst=edge.get('target_index')
            if type(src) is int and type(dst) is int and 0<=src<len(moments) and 0<=dst<len(moments) and src!=dst:
                edges.append({'from':moments[src].id,'to':moments[dst].id,
                              'relation':str(edge.get('relation','related'))[:60], 'source':'MOMENTWEAVE_EXPORT'})
    if not edges:
        edges=[{'from':a.id,'to':b.id,'relation':'next_in_time','source':'TEMPORAL_FALLBACK'}
               for a,b in zip(moments,moments[1:])]
    return {'video_id':video_id,'source':'MOMENTWEAVE_JSON' if imported else 'OPENCV_TEMPORAL_FALLBACK',
            'nodes':[{'id':m.id,'title':m.title,'emotion':m.emotion,'narrative_role':m.narrative_role,
                      'start_ms':m.start_ms,'end_ms':m.end_ms,'analysis_version':m.analysis_version} for m in moments],
            'edges':edges,
            'notice':'Imported labels are user-supplied MomentWeave assertions; they are not independently checked by this service.'}
