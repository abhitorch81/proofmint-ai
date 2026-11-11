"""Phase 4: keypoint evidence and keyed DCT watermark on *still frames*.

An AKAZE geometric match is visual similarity evidence, not copyright proof.
The watermark is an original, experimental per-frame signal, not C2PA or
production-grade adversarial-resistant video watermarking.
"""
import hashlib
import hmac
import math
import cv2
import numpy as np

CANONICAL_W, CANONICAL_H = 512, 288
BLOCK = 8
TAG_BITS = 32
REPEATS = 12
Q = 34.0


def safe_decode(data: bytes):
    if len(data) > 8 * 1024 * 1024:
        raise ValueError('Image exceeds 8 MB')
    img = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
    if img is None or img.size == 0:
        raise ValueError('Invalid or unsupported image')
    if img.shape[0] * img.shape[1] > 16_000_000:
        raise ValueError('Image dimensions exceed 16 megapixels')
    return img


def akaze_evidence(source, candidate):
    """AKAZE descriptors + Lowe ratio + RANSAC homography inliers."""
    def scale(im):
        h, w = im.shape[:2]
        if max(h, w) > 1000:
            f = 1000 / max(h, w)
            return cv2.resize(im, None, fx=f, fy=f, interpolation=cv2.INTER_AREA)
        return im
    a, b = scale(source), scale(candidate)
    detector = cv2.AKAZE_create()
    ka, da = detector.detectAndCompute(cv2.cvtColor(a, cv2.COLOR_BGR2GRAY), None)
    kb, db = detector.detectAndCompute(cv2.cvtColor(b, cv2.COLOR_BGR2GRAY), None)
    out = {'method':'AKAZE_HAMMING_RATIO_RANSAC','source_keypoints':len(ka),
           'candidate_keypoints':len(kb),'ratio_matches':0,'inliers':0,
           'inlier_ratio':0.0,'candidate_visual_match':False,
           'assessment':'insufficient evidence',
           'note':'Geometric visual similarity evidence only; not a legal ownership or watermark verification result.'}
    if da is None or db is None or len(da)<2 or len(db)<2:
        return out
    # Binary AKAZE descriptors: Hamming distance.
    pairs = cv2.BFMatcher(cv2.NORM_HAMMING).knnMatch(da, db, k=2)
    good = [m for pair in pairs if len(pair)==2 for m,n in [pair] if m.distance < .75 * n.distance]
    out['ratio_matches'] = len(good)
    if len(good)<4:
        return out
    s = np.float32([ka[m.queryIdx].pt for m in good]).reshape(-1,1,2)
    t = np.float32([kb[m.trainIdx].pt for m in good]).reshape(-1,1,2)
    try:
        H, mask = cv2.findHomography(s,t,cv2.RANSAC,5.0)
    except cv2.error:
        return out
    if H is None or mask is None:
        return out
    inliers = int(mask.sum())
    ratio = inliers / len(good)
    accepted = inliers>=8 and ratio>=.5
    out.update(inliers=inliers,inlier_ratio=round(ratio,4),
               candidate_visual_match=accepted,
               assessment='geometric candidate match' if accepted else 'weak or ambiguous match')
    return out


def _tag(secret: str, moment_id: str):
    if not secret or secret=='development-only-change-me' or len(secret)<32:
        raise ValueError('Set a strong RECEIPT_SIGNING_SECRET before watermark operations')
    return hmac.new(secret.encode(), ('proofmint-frame-watermark-v1:'+moment_id).encode(), hashlib.sha256).digest()[:4]


def _indices(secret: str, moment_id: str):
    seed = hmac.new(secret.encode(), ('proofmint-blocks-v1:'+moment_id).encode(), hashlib.sha256).digest()
    rng = np.random.default_rng(int.from_bytes(seed[:8], 'big'))
    nblocks = (CANONICAL_W//BLOCK)*(CANONICAL_H//BLOCK)
    return rng.permutation(nblocks)[:TAG_BITS*REPEATS]


def _bits(value: bytes):
    return np.unpackbits(np.frombuffer(value, dtype=np.uint8))


def _luma(image):
    canvas=cv2.resize(image,(CANONICAL_W,CANONICAL_H),interpolation=cv2.INTER_AREA)
    return cv2.cvtColor(canvas, cv2.COLOR_BGR2YCrCb)


def embed_frame(source, secret: str, moment_id: str):
    """Embed a keyed 32-bit tag into 384 DCT blocks, return a 512x288 PNG frame."""
    tag=_tag(secret,moment_id)
    yc=_luma(source)
    luma=yc[:,:,0].astype(np.float32)
    bits=_bits(tag)
    ids=_indices(secret,moment_id)
    cols=CANONICAL_W//BLOCK
    for i, idx in enumerate(ids):
        y=(idx//cols)*BLOCK; x=(idx%cols)*BLOCK
        dct=cv2.dct(luma[y:y+8,x:x+8]-128.0)
        # Quantization-index modulation of a mid-frequency coefficient.
        coeff=float(dct[3,2]); bit=int(bits[i%TAG_BITS])
        bucket=round((coeff-(Q/2 if bit else 0))/Q)
        dct[3,2]=bucket*Q+(Q/2 if bit else 0)
        luma[y:y+8,x:x+8]=cv2.idct(dct)+128.0
    yc[:,:,0]=np.clip(np.rint(luma),0,255).astype(np.uint8)
    marked=cv2.cvtColor(yc,cv2.COLOR_YCrCb2BGR)
    ok, buf=cv2.imencode('.png', marked)
    if not ok: raise ValueError('Cannot encode marked frame')
    return buf.tobytes(), tag.hex()


def verify_frame_watermark(candidate, secret: str, moment_id: str):
    """Decode keyed signal after resizing to canonical dimensions.

    Thresholds are demo heuristics, not empirical guarantees.
    """
    expected=_bits(_tag(secret,moment_id))
    ids=_indices(secret,moment_id)
    luma=_luma(candidate)[:,:,0].astype(np.float32)
    cols=CANONICAL_W//BLOCK
    votes=np.zeros((TAG_BITS,2), dtype=np.int32)
    for i,idx in enumerate(ids):
        y=(idx//cols)*BLOCK;x=(idx%cols)*BLOCK
        dct=cv2.dct(luma[y:y+8,x:x+8]-128.0)
        coeff=float(dct[3,2])
        d0=abs(coeff-Q*round(coeff/Q))
        d1=abs(coeff-(Q*round((coeff-Q/2)/Q)+Q/2))
        votes[i%TAG_BITS, 1 if d1<d0 else 0]+=1
    recovered=(votes[:,1]>votes[:,0]).astype(np.uint8)
    correct=int((recovered==expected).sum())
    agreement=float(np.max(votes,axis=1).sum()/votes.sum())
    # For random unrelated frames, 28/32 matching bits probability is tiny.
    detected=correct>=28 and agreement>=.65
    return {'method':'KEYED_DCT_QIM_FRAME_V1','moment_id':moment_id,'watermark_detected':bool(detected),
            'tag_bits_matched':correct,'tag_bits_total':TAG_BITS,
            'vote_agreement':round(agreement,4),
            'evidence':'Experimental keyed watermark detected in image frame' if detected else 'Watermark not detected with sufficient confidence',
            'note':'Per-frame demo. A positive result links this marked frame to a locally issued moment tag, not legal ownership or a watermarked full video.'}
