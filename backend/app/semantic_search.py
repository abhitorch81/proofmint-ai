"""Sentence-embedding semantic search when the optional model is installed.
Falls back to lexical/token matching with the method explicitly reported.
Run `pip install -r requirements-semantic.txt` to enable embeddings; first use downloads weights.
"""
from functools import lru_cache
import re

@lru_cache(maxsize=1)
def encoder():
    try:
        from sentence_transformers import SentenceTransformer
        return SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')
    except (ImportError, OSError):
        return None

def score_documents(query, documents):
    if not query.strip():
        return [1.0] * len(documents), 'BROWSE_ALL'
    model=encoder()
    if model is not None:
        import numpy as np
        vectors=model.encode([query,*documents],normalize_embeddings=True)
        return [max(0.0,float(x)) for x in (vectors[1:]@vectors[0])], 'MINILM_COSINE_EMBEDDINGS'
    def tokens(s):
        return set(re.findall(r'[a-z0-9]+',s.lower())) - {'the','a','an','is','for','and','of','to','in','on','with'}
    wanted=tokens(query)
    return [len(wanted & tokens(d))/max(1,len(wanted)) for d in documents], 'LOCAL_LEXICAL_FALLBACK_NO_EMBEDDINGS'
