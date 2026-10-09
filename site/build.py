"""Build the homepage from the published, finished film assets.

    python3 site/build.py --output /tmp/codecinema-site

Requires an authenticated GitHub CLI and FFmpeg. Release assets are checked
before a deployment, and their IDs version video URLs when a master is
replaced. Each release holds only its finished film; the web player's
subtitles are extracted from the film's own subtitle tracks.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parent.parent
FILMS = {
    "pebble": ("films", ("Pebble.mp4",)),
    "nian": ("films", ("Nian.mp4",)),
    "film": ("films", ("SilverGrass.mp4",)),
    "nightrevels": ("films", ("NightRevels.mp4",)),
}
# Subtitle track language (ISO 639-2) -> the suffix the pages use, as in Pebble.zh.vtt
LANGUAGES = {"eng": "en", "chi": "zh", "zho": "zh"}


def sha256(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def subtitles(video):
    """Write each subtitle track of a finished film as <name>.<lang>.vtt beside it, for the web player."""
    probe = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "s", "-show_entries",
                            "stream=index:stream_tags=language", "-of", "json", str(video)],
                           check=True, capture_output=True, text=True)
    for stream in json.loads(probe.stdout).get("streams", []):
        lang = LANGUAGES.get(stream.get("tags", {}).get("language", ""))
        if lang:
            target = video.with_name(f"{video.stem}.{lang}.vtt")
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(video), "-map", f"0:{stream['index']}",
                            "-c:s", "webvtt", str(target)], check=True)
            print(f"Extracted {target.name}", flush=True)


def build(output, repo):
    """Assemble and verify a complete edition in a fresh staging directory."""
    releases = {}
    for tag, (_, names) in FILMS.items():
        response = subprocess.run(
            ["gh", "api", f"repos/{repo}/releases/tags/{tag}"],
            check=True, capture_output=True, text=True,
        )
        release = json.loads(response.stdout)
        if release["draft"]:
            raise ValueError(f"{tag}: publish the release before deploying")
        assets = {a["name"]: a for a in release["assets"] if a["state"] == "uploaded"}
        missing = set(names) - assets.keys()
        if missing:
            raise ValueError(f"{tag}: missing finished films: {', '.join(sorted(missing))}")
        releases[tag] = assets

    # Copy only homepage files; this build script is not part of the public site.
    for source in (ROOT / "site").iterdir():
        if source.name in ("build.py", "__pycache__"):
            continue
        target = output / source.name
        if source.is_dir():
            shutil.copytree(source, target)
        else:
            shutil.copy2(source, target)
    shutil.copytree(ROOT / "assets/_shared/site", output, dirs_exist_ok=True)
    shutil.copytree(ROOT / "assets/_shared/images", output / "img")
    for film in ("pebble", "nian", "silvergrass", "nightrevels"):
        shutil.copytree(ROOT / f"assets/{film}/images", output / f"img/{film}")

    ids = []
    for tag, (folder, names) in FILMS.items():
        directory = output / folder
        directory.mkdir(parents=True, exist_ok=True)
        for name in names:
            asset = releases[tag][name]
            subprocess.run(
                ["gh", "release", "download", tag, "--repo", repo,
                 "--pattern", name, "--dir", str(directory), "--clobber"], check=True,
            )
            path = directory / name
            if path.stat().st_size != asset["size"]:
                raise ValueError(f"{tag}/{name}: incomplete download")
            expected = asset.get("digest")
            if expected and expected != "sha256:" + sha256(path):
                raise ValueError(f"{tag}/{name}: download differs from the release")
            ids.append(str(asset["id"]))
            print(f"Verified {tag}/{name}: {asset['size']:,} bytes", flush=True)
            subtitles(path)

    revision = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"],
                              check=True, capture_output=True, text=True).stdout.strip()
    version = hashlib.sha256("\n".join([revision, *ids]).encode()).hexdigest()[:12]
    for path in output.rglob("*.html"):
        content = path.read_text(encoding="utf-8")
        content = re.sub(r"(<html\b[^>]*)(>)", rf'\1 data-media-version="{version}"\2', content, count=1)
        # Homepage episode buttons, initial sources and download fallbacks all
        # receive the same media version.
        content = re.sub(r'(\.(?:mp4|jpg|png|gif|svg))(["\'])', rf'\1?v={version}\2', content)
        content = re.sub(r'((?:src|href)="[^"?]+\.(?:js|css))(")', rf'\1?v={version}\2', content)
        path.write_text(content, encoding="utf-8")
    (output / ".codecinema-site.json").write_text(
        json.dumps({"kind": "codecinema-site", "revision": revision, "media_version": version}) + "\n",
        encoding="utf-8",
    )
    return version


def assemble(output, repo):
    if output.is_symlink():
        raise ValueError("Choose a real output directory, not a symbolic link")
    output = output.resolve()
    if (output == ROOT or ROOT.is_relative_to(output)
            or (output.is_relative_to(ROOT) and not output.is_relative_to(ROOT / "out")
                and output != ROOT / "_site")):
        raise ValueError("Use out/site, _site or a directory outside the repository sources")
    if output.exists():
        if not output.is_dir():
            raise ValueError("The output path must be a directory")
        marker = output / ".codecinema-site.json"
        # Allow the default staging folder from editions before build markers.
        if any(output.iterdir()) and output != ROOT / "out/site":
            if (not marker.is_file()
                    or json.loads(marker.read_text(encoding="utf-8")).get("kind") != "codecinema-site"):
                raise ValueError("Choose an empty output directory or a previous CodeCinema site build")
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".codecinema-site-", dir=output.parent) as temporary:
        stage = Path(temporary) / "site"
        stage.mkdir()
        version = build(stage, repo)
        previous = Path(temporary) / "previous"
        if output.exists():
            output.replace(previous)
        try:
            stage.replace(output)
        except OSError:
            if previous.exists():
                previous.replace(output)
            raise
    print(f"Site ready: {output} (media edition {version})", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", default="ZJUCQR/CodeCinema")
    parser.add_argument("--output", type=Path, default=ROOT / "out/site")
    options = parser.parse_args()
    assemble(options.output, options.repo)


if __name__ == "__main__":
    main()
