"""The starter presets and their editable scene-file contract (standard library only)."""
import math
import re

PRESETS = {
    "moonrise": {
        "description": "A rising moon, stars and layered mountain silhouettes",
        "captions": ["A little light in the quiet.", "The night moves at its own pace.", "Some nights are worth keeping."],
    },
    "sunset": {
        "description": "A warm sunset, distant islands and shimmering water",
        "captions": ["Stay for the last light.", "Every ripple holds a little gold.", "Let the evening linger."],
    },
    "aurora": {
        "description": "Moving northern lights above a lake and a dark forest",
        "captions": ["The sky has a story to tell.", "Light travels quietly across the water.", "Carry a little wonder home."],
    },
    "neon": {
        "description": "A violet city skyline, neon windows and reflections after dark",
        "captions": ["The city wakes after sunset.", "A thousand windows, a thousand stories.", "Find your own light."],
    },
    "ocean": {
        "description": "Turquoise waves, sunlit clouds and an open sea",
        "captions": ["Leave a little room for the sea.", "Breathe with the tide.", "There is always another horizon."],
    },
    "ink": {
        "description": "Paper, misty ink mountains, birds and a vermilion sun",
        "captions": ["A mountain begins with a quiet line.", "Let the empty space breathe.", "A moment, held on paper."],
    },
    "cosmos": {
        "description": "A ringed planet, moving moons and a deep star field",
        "captions": ["A small story in an endless sky.", "Every orbit is a journey.", "Keep looking up."],
    },
    "ember": {
        "description": "Fireflies and warm amber light in a twilight forest",
        "captions": ["Follow the smallest lights.", "The forest keeps its own rhythm.", "A little warmth for the way home."],
    },
}
FORMATS = {"landscape": (16, 9), "portrait": (9, 16), "square": (1, 1)}
QUALITIES = {
    "preview": {"short_side": 360, "crf": 25, "preset": "ultrafast"},
    "standard": {"short_side": 720, "crf": 20, "preset": "fast"},
    "high": {"short_side": 1080, "crf": 16, "preset": "medium"},
}
VOICES = ("Serena", "Dylan", "Vivian", "Uncle_Fu", "Eric", "Ryan", "Aiden", "Ono_Anna", "Sohee")


def duration(value):
    """Validate a total duration before creating files or starting an encoder."""
    try:
        seconds = float(value)
    except (ValueError, TypeError):
        raise ValueError("duration must be a number of seconds") from None
    if not math.isfinite(seconds) or not 1.5 <= seconds <= 600:
        raise ValueError("duration must be between 1.5 and 600 seconds")
    return seconds


def dimensions(format_name, quality):
    x, y = FORMATS[format_name]
    short = QUALITIES[quality]["short_side"]
    return tuple(round(short * part / min(x, y) / 2) * 2 for part in (x, y))


def make_story(title, preset="moonrise", seconds=12.0, subtitle=None):
    seconds = duration(seconds)
    captions = PRESETS[preset]["captions"]
    scenes = []
    for i, camera in enumerate(("wide", "drift", "close")):
        scenes.append({
            "name": ("Opening", "Drift", "Afterglow")[i],
            "preset": preset,
            "duration_s": seconds / 3,
            "camera": camera,
            "title": title if i != 1 else "",
            "subtitle": subtitle if i == 0 and subtitle is not None else captions[i],
        })
    return {"version": 1, "title": title, "seed": 7, "scenes": scenes}


def validate_story(data):
    """Validate user-edited JSON with errors that point to the field to fix."""
    if not isinstance(data, dict) or data.get("version") != 1:
        raise ValueError("scenes.json must be an object with version: 1")
    if not isinstance(data.get("title"), str) or not data["title"].strip():
        raise ValueError("scenes.json: title must be a non-empty string")
    if type(data.get("seed", 7)) is not int or not 0 <= data.get("seed", 7) <= 2**63 - 1:
        raise ValueError("scenes.json: seed must be a non-negative integer below 2^63")
    scenes = data.get("scenes")
    if not isinstance(scenes, list) or not scenes:
        raise ValueError("scenes.json: scenes must contain at least one scene")
    total = 0.0
    for index, scene in enumerate(scenes, 1):
        field = f"scenes.json: scene {index}"
        if not isinstance(scene, dict):
            raise ValueError(f"{field} must be an object")
        if not isinstance(scene.get("preset"), str) or scene["preset"] not in PRESETS:
            raise ValueError(f"{field}.preset must be one of: {', '.join(PRESETS)}")
        sec = scene.get("duration_s")
        if type(sec) not in (float, int) or not math.isfinite(sec) or sec < 0.5:
            raise ValueError(f"{field}.duration_s must be a finite number of at least 0.5 seconds")
        if scene.get("camera", "wide") not in ("wide", "drift", "close"):
            raise ValueError(f"{field}.camera must be wide, drift or close")
        for key in ("title", "subtitle", "name"):
            if not isinstance(scene.get(key, ""), str):
                raise ValueError(f"{field}.{key} must be a string")
        if "accent" in scene and not re.fullmatch(r"#[0-9a-fA-F]{6}", str(scene["accent"])):
            raise ValueError(f"{field}.accent must be a hex color such as #e8c89d")
        narration = scene.get("narration", {})
        if not isinstance(narration, dict):
            raise ValueError(f"{field}.narration must be an object")
        for key in ("text", "direction", "recording"):
            if not isinstance(narration.get(key, ""), str) or len(narration.get(key, "")) > 2000:
                raise ValueError(f"{field}.narration.{key} must be text of at most 2000 characters")
        if narration.get("voice", "Serena") not in VOICES:
            raise ValueError(f"{field}.narration.voice must be one of: {', '.join(VOICES)}")
        if narration.get("language", "Chinese") not in ("Chinese", "English", "Japanese", "Korean", "French", "German", "Spanish", "Italian", "Portuguese", "Russian"):
            raise ValueError(f"{field}.narration.language is unsupported")
        if narration.get("recording") and not re.fullmatch(r"[a-zA-Z0-9_-]+\.wav", narration["recording"]):
            raise ValueError(f"{field}.narration.recording must be a filename such as scene-1.wav in assets/voices/")
        total += sec
    duration(total)
    return total
