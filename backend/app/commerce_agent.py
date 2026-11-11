"""Constrained agentic commerce tools; no LLM is trusted with checkout authority.

LangGraph is used when installed. Without it a deterministic sequential fallback
keeps text demos runnable, and the response exposes the orchestration mode.
"""
import re
from typing import TypedDict
from sqlalchemy import select
from sqlalchemy.orm import Session
from .models import Moment, VideoAsset
from .moments_api import moment_out
from .semantic_search import score_documents

class AgentState(TypedDict, total=False):
    query: str
    budget_cents: int | None
    max_duration_s: int | None
    candidates: list[dict]
    recommendations: list[dict]
    explanation: str
    search_method: str
    audit: list[str]


def extract_constraints(query: str):
    budget = None
    match = re.search(r'(?:under|below|less than|maximum|max|up to|budget(?: of)?|for)\s*(?:USD\s*)?\$\s*(\d+(?:\.\d{1,2})?)', query, re.I)
    if not match:
        match = re.search(r'(?:under|below|less than|maximum|max|up to|budget(?: of)?)\s*(\d+(?:\.\d{1,2})?)\s*(?:dollars|usd)',query,re.I)
    if not match:
        word_amounts={'one':1,'two':2,'three':3,'four':4,'five':5,'six':6,'seven':7,'eight':8,'nine':9,'ten':10,'fifteen':15,'twenty':20,'thirty':30,'fifty':50,'hundred':100}
        spoken=re.search(r'(?:under|below|less than|maximum|max|up to|budget(?: of)?)\s+([a-z]+)\s+(?:dollars|usd)',query,re.I)
        if spoken and spoken.group(1).lower() in word_amounts:
            budget=word_amounts[spoken.group(1).lower()]*100
    if match: budget = int(round(float(match.group(1))*100))
    duration = None
    match = re.search(r'(?:under|less than|up to|max(?:imum)?|about|around)?\s*(\d{1,3})\s*(?:second|sec|s)\b',query,re.I)
    if match: duration = int(match.group(1))
    # Remove mechanical constraints before querying index; preserve the remaining words.
    clean = re.sub(r'(?:under|below|less than|maximum|max|up to|budget(?: of)?|for)\s*(?:USD\s*)?\$\s*\d+(?:\.\d+)?',' ',query,flags=re.I)
    clean = re.sub(r'\b\d{1,3}\s*(?:seconds?|secs?)\b',' ',clean,flags=re.I)
    clean = re.sub(r'\b(find|me|show|please|a|an|video|clip|moment|commercial|commercially|license|buy|purchase|that|can|i|use|and|with|priced|at|for|the)\b',' ',clean,flags=re.I)
    return budget,duration,' '.join(clean.split())


def provenance_evidence(moment: Moment, video: VideoAsset):
    return {'source_sha256':video.source_sha256,
            'keyframe_sha256':moment.keyframe_sha256,
            'keyframe_dhash':moment.keyframe_dhash,
            'analysis_version':moment.analysis_version,
            'rights_asserted_by_uploader':bool(video.rights_asserted),
            'legal_ownership_verified':False,
            'evidence_level':'UNVERIFIED_RIGHTS_ASSERTION',
            'note':'Hashes identify stored data. Keyframe fingerprint permits similarity comparison; neither proves copyright or rights ownership.'}


def search_moment_tool(db:Session,query:str,budget_cents=None,max_duration_s=None):
    records=db.scalars(select(Moment)).all()
    pairs=[]
    for m in records:
        v=db.get(VideoAsset,m.video_id)
        if not v or not v.rights_asserted: continue
        if budget_cents is not None and m.price_cents>budget_cents:continue
        if max_duration_s is not None and (m.end_ms-m.start_ms)>max_duration_s*1000:continue
        pairs.append((m,v))
    clean_query=extract_constraints(query)[2]
    docs=[' '.join([m.title,m.description,m.emotion,m.narrative_role,v.title]) for m,v in pairs]
    scores,method=score_documents(clean_query,docs)
    ranked=sorted([(float(score),m,v) for score,(m,v) in zip(scores,pairs) if score>0 or not clean_query],key=lambda t:(-t[0],t[1].id))[:3]
    return ranked,method


def run_commerce_agent(db:Session, utterance:str):
    budget,duration,clean=extract_constraints(utterance)
    state:AgentState={'query':utterance,'budget_cents':budget,'max_duration_s':duration,'audit':[]}
    def discovery(s:AgentState):
        ranked,method=search_moment_tool(db,s['query'],s.get('budget_cents'),s.get('max_duration_s'))
        s['candidates']=[{'score':score,'moment':m,'video':v} for score,m,v in ranked]
        s['search_method']=method;s['audit'].append('search_moment_tool')
        return s
    def rights(s:AgentState):
        result=[]
        for c in s['candidates']:
            m,v=c['moment'],c['video']
            result.append({**moment_out(m),'source_video_title':v.title,'relevance':round(c['score'],3),
                           'provenance':provenance_evidence(m,v)})
        s['recommendations']=result;s['audit'].append('verify_provenance_tool')
        return s
    def response(s:AgentState):
        n=len(s['recommendations'])
        if n:
            top=s['recommendations'][0]
            s['explanation']=(f'I found {n} candidate moment(s). The top match is {top["title"]}, '
               f'{(top["end_ms"]-top["start_ms"])/1000:g} seconds for ${top["price_cents"]/100:.2f}. '
               'The uploader asserted licensing rights, but legal ownership has not been independently verified. '
               'Review the clip and terms before explicitly approving PayPal sandbox checkout.')
        else:
            s['explanation']='No moments matched your criteria. Try a different description, budget, or duration.'
        s['audit'].append('compose_response_tool')
        return s
    try:
        from langgraph.graph import StateGraph, START, END
    except ImportError:
        mode='DETERMINISTIC_FALLBACK_LANGGRAPH_NOT_INSTALLED'
        state=response(rights(discovery(state)))
    else:
        graph=StateGraph(AgentState)
        graph.add_node('discover',discovery);graph.add_node('verify',rights);graph.add_node('respond',response)
        graph.add_edge(START,'discover');graph.add_edge('discover','verify');graph.add_edge('verify','respond');graph.add_edge('respond',END)
        state=graph.compile().invoke(state)
        mode='LANGGRAPH_STATE_GRAPH'
    return {'transcript':utterance,'reply':state['explanation'],'recommendations':state['recommendations'],
            'search_method':state['search_method'],'orchestrator':mode,'audit':state['audit'],
            'constraints':{'max_price_cents':budget,'max_duration_seconds':duration},
            'payment_action':'NONE_CHECKOUT_REQUIRES_EXPLICIT_UI_APPROVAL'}
