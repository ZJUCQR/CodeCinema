"""Split a line of text into runs of one font each: per-run fallback for mixed scripts.

    runs("Nian · 年", [fredoka, zcool])        # -> [("Nian · ", fredoka), ("年", zcool)]

Each word takes the first font that covers all of it; Han, kana and other ideographs choose per character.
Spaces, digits and punctuation stay with the font of the text before them (or after them at the start), and
combining marks stay with their base letter. Characters no font covers use the first font.
"""
from codecinema.typography import scripts

_IDEOGRAPHIC = {"Han", "Hiragana", "Katakana", "Bopomofo"}


def clusters(text):
    """Base characters with their combining marks and joined characters."""
    out = []
    for ch in text:
        if out and (scripts.script_of(ch) == "Inherited" or out[-1].endswith("\u200d")):
            out[-1] += ch
        else:
            out.append(ch)
    return out


def tokens(text):
    """[segment, kind, script] with kind "word", "ideograph" or "common" (spaces, digits, punctuation)."""
    out = []
    for cluster in clusters(text):
        script = scripts.script_of(cluster[0])
        kind = "common" if script in ("Common", "Inherited") else "ideograph" if script in _IDEOGRAPHIC else "word"
        if out and kind != "ideograph" and out[-1][1] == kind and (kind == "common" or out[-1][2] == script):
            out[-1][0] += cluster
        else:
            out.append([cluster, kind, script])
    return out


def _first(faces, segment):
    return next((face for face in faces if face.covers(segment)), None)


def runs(text, faces):
    """[(segment, face)] covering `text` in order, adjacent segments of the same face merged."""
    if not text:
        return []
    faces = [face for face in faces if face is not None]
    if len(faces) <= 1:
        return [(text, faces[0] if faces else None)]
    items = tokens(text)
    picks = [None if kind == "common" else _first(faces, segment) for segment, kind, _ in items]
    for i, (segment, kind, _) in enumerate(items):
        if kind == "common":
            before = picks[i - 1] if i else None
            after = next((picks[j] for j in range(i + 1, len(items)) if picks[j] is not None), None)
            picks[i] = next((f for f in (before, after) if f is not None and f.covers(segment)), None) \
                or _first(faces, segment)
    out = []
    for (segment, _kind, _script), face in zip(items, picks):
        parts = [(segment, face)] if face is not None else \
            [(cluster, _first(faces, cluster) or faces[0]) for cluster in clusters(segment)]
        for part, part_face in parts:
            if out and out[-1][1] == part_face:
                out[-1] = (out[-1][0] + part, part_face)
            else:
                out.append((part, part_face))
    return out
