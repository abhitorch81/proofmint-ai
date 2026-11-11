"""Deterministic, CPU-only MVP scene/motion candidate segmentation.
NOT the proprietary MomentWeave nine-lens classifier or a trained emotion recognizer.
Use the adapter for actual MomentWeave segment results when supplied.
"""
import hashlib
import math
from pathlib import Path
import cv2
import numpy as np

VERSION = 'opencv-scene-motion-v1'


def dhash(image):
    grayscale = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    resized = cv2.resize(grayscale, (9, 8))
    bits = (resized[:, 1:] > resized[:, :-1]).flatten()
    value = sum(int(bit) << (63 - i) for i, bit in enumerate(bits))
    return f'{value:016x}'


def hamming(a, b):
    return (int(a, 16) ^ int(b, 16)).bit_count()


def inspect_video(path: Path, count=4):
    """Sample at up to 2 fps, form 3-5 bounded segments, return on-disk frame evidence."""
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        raise ValueError('Cannot decode video. Use MP4/H.264 or install appropriate video codecs.')
    fps = float(cap.get(cv2.CAP_PROP_FPS))
    frames = float(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration = frames / fps if fps > 0 and frames > 0 else 0
    if not math.isfinite(duration) or duration < 3 or duration > 3600:
        cap.release()
        raise ValueError('Video must have reliable metadata and last between 3 seconds and 1 hour')
    # Distributed samples avoid decoding every frame of a large upload.
    sample_times = np.arange(0, duration, max(0.5, duration / 120)).tolist()
    values = []
    prev = None
    for seconds in sample_times:
        cap.set(cv2.CAP_PROP_POS_MSEC, seconds * 1000)
        ok, frame = cap.read()
        if not ok:
            continue
        small = cv2.resize(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY), (128, 72))
        if prev is not None:
            motion = float(np.mean(cv2.absdiff(prev, small))) / 255
            values.append((seconds, motion))
        prev = small
    # Rank high-activity sample times while reserving space between segment centers.
    n = min(5, max(3, count))
    span = duration / n
    segments = []
    for i in range(n):
        start = i * span
        end = duration if i == n - 1 else (i + 1) * span
        local = [(t, v) for t, v in values if start <= t < end]
        peak_t, peak = max(local, key=lambda tv: tv[1], default=((start + end) / 2, 0.0))
        center = max(start + 0.15 * span, min(end - 0.15 * span, peak_t))
        # Ensure 3-5 nonoverlapping contiguous microsegments, approx span seconds each.
        cap.set(cv2.CAP_PROP_POS_MSEC, center * 1000)
        ok, frame = cap.read()
        if not ok:
            cap.release()
            raise ValueError('Unable to decode a representative frame')
        resized = cv2.resize(frame, (320, 180))
        success, encoded = cv2.imencode('.jpg', resized, [cv2.IMWRITE_JPEG_QUALITY, 88])
        if not success:
            cap.release()
            raise ValueError('Unable to encode preview frame')
        motion = sum(v for _,v in local) / max(1, len(local))
        # Motion-based tags are DEMO proxies, not actual emotional understanding.
        emotion = 'High energy (motion proxy)' if motion > .12 else 'Steady (motion proxy)' if motion > .035 else 'Calm (motion proxy)'
        role = 'opening' if i == 0 else 'closing' if i == n-1 else 'highlight candidate' if peak > .10 else 'continuity'
        segments.append({'start_ms': round(start*1000), 'end_ms': round(end*1000),
                         'title': f'Moment {i+1} · {role.title()}',
                         'description': f'Automatically proposed scene window {i+1}. Motion proxy {motion:.3f}; peak at {peak_t:.1f}s. Human review required.',
                         'emotion':emotion, 'narrative_role':role, 'motion_score':round(motion,4),
                         'keyframe_dhash':dhash(resized),
                         'keyframe_sha256':hashlib.sha256(encoded.tobytes()).hexdigest(),
                         'jpg':encoded.tobytes(), 'analysis_version':VERSION})
    cap.release()
    return duration, segments
