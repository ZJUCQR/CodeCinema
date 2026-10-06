"""The shared story clock and continuity contract for all three episodes."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CANON = json.loads((ROOT / "data/canon.json").read_text(encoding="utf-8"))
STORY = json.loads((ROOT / "data/episodes.json").read_text(encoding="utf-8"))


@dataclass(frozen=True)
class Shot:
    episode_id: str
    index: int
    data: dict
    start: float
    end: float
    costume: str
    letter: bool

    @property
    def id(self):
        return f"{self.episode_id}_{self.data['id']}"

    @property
    def duration(self):
        return self.end - self.start

    @property
    def text(self):
        return self.data.get("text", "")


def timeline(episode):
    cursor = 0.0
    costume = episode["opening_state"]["costume"]
    letter = episode["opening_state"]["letter"]
    for index, data in enumerate(episode["shots"]):
        costume = data.get("costume", costume)
        letter = data.get("letter", letter)
        end = cursor + data["seconds"]
        yield Shot(episode["id"], index, data, cursor, end, costume, letter)
        cursor = end


def validate():
    errors = []
    expectations = []
    for index, episode in enumerate(STORY["episodes"]):
        shots = list(timeline(episode))
        if abs(shots[-1].end - episode["duration_s"]) > 1e-6:
            errors.append(f"{episode['id']}: shot durations do not total {episode['duration_s']} s")
        if len({s.id for s in shots}) != len(shots):
            errors.append(f"{episode['id']}: duplicate shot ids")
        if index:
            previous = STORY["episodes"][index - 1]["closing_state"]
            current = episode["opening_state"]
            for key in ("clock", "costume", "expectation", "letter"):
                if previous[key] != current[key]:
                    errors.append(f"{episode['id']}: discontinuity in {key}")
        last_chapter = 0
        for shot in shots:
            source = CANON["sources"].get(shot.data["source"])
            if not source or source["chapter"] not in episode["chapters"]:
                errors.append(f"{shot.id}: incorrect source")
                continue
            if source["chapter"] < last_chapter:
                errors.append(f"{shot.id}: chapter order reversed")
            last_chapter = source["chapter"]
            if shot.costume not in CANON["characters"]["chen_ling"]["costumes"]:
                errors.append(f"{shot.id}: unknown costume")
            if "expectation" in shot.data:
                value = shot.data["expectation"]
                if not expectations or value != expectations[-1]:
                    expectations.append(value)
            if shot.data.get("increment") and "expectation" in shot.data:
                errors.append(f"{shot.id}: increments cannot invent a final value")
        if shots[-1].costume != episode["closing_state"]["costume"]:
            errors.append(f"{episode['id']}: final costume incorrect")
        if shots[-1].letter != episode["closing_state"]["letter"]:
            errors.append(f"{episode['id']}: letter disappears")
    if expectations != CANON["expectation_order"]:
        errors.append(f"expectation sequence differs from canon: {expectations}")
    if errors:
        raise ValueError("\n".join(errors))
    return {"episodes": len(STORY["episodes"]), "shots": sum(len(e["shots"]) for e in STORY["episodes"]),
            "duration_s": sum(e["duration_s"] for e in STORY["episodes"]), "expectations": expectations}


def digest(extra=""):
    """Invalidate generated work when any story, renderer, audio or setting changes."""
    h = hashlib.sha256(extra.encode())
    paths = [ROOT / "film.toml", *sorted((ROOT / "data").glob("*.json")),
             *sorted((ROOT / "src").glob("*.py"))]
    for path in paths:
        h.update(path.name.encode())
        h.update(path.read_bytes())
    return h.hexdigest()[:20]


def srt_time(seconds):
    ms = round(seconds * 1000)
    hours, ms = divmod(ms, 3_600_000)
    minutes, ms = divmod(ms, 60_000)
    seconds, ms = divmod(ms, 1000)
    return f"{hours:02}:{minutes:02}:{seconds:02},{ms:03}"


def write_plan(out):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    report = {"validation": validate(), "canon": CANON, "episodes": []}
    script = ["# 我不是戏神 · 开篇三集", "", "按官方开篇六章压缩改编，台词与旁白重新创作。", ""]
    full_srt = []
    offset = 0.0
    for episode in STORY["episodes"]:
        entry = {k: v for k, v in episode.items() if k != "shots"}
        entry["shots"] = []
        subtitles = []
        script.extend([f"## 第 {episode['number']} 集 · {episode['title']}", ""])
        for shot in timeline(episode):
            entry["shots"].append({**shot.data, "start": shot.start, "end": shot.end,
                                   "resolved_costume": shot.costume, "has_letter": shot.letter})
            script.append(f"- {shot.start:06.1f}–{shot.end:06.1f}s · {shot.data['scene']} · {shot.data['source']}")
            if shot.text:
                text = ((shot.data["speaker"] + "：") if shot.data.get("speaker") else "") + shot.text
                subtitles.append(f"{len(subtitles)+1}\n{srt_time(shot.start+0.65)} --> {srt_time(shot.end-0.5)}\n{text}\n")
                full_srt.append(f"{len(full_srt)+1}\n{srt_time(offset+shot.start+0.65)} --> "
                                f"{srt_time(offset+shot.end-0.5)}\n{text}\n")
                script.extend([f"  {text}", ""])
        (out / f"{episode['id']}.srt").write_text("\n".join(subtitles), encoding="utf-8")
        report["episodes"].append(entry)
        offset += episode["duration_s"]
    (out / "complete.srt").write_text("\n".join(full_srt), encoding="utf-8")
    (out / "continuity.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "screenplay.md").write_text("\n".join(script), encoding="utf-8")
    return report["validation"]
