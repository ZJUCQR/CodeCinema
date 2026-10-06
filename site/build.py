"""Build the homepage from the published, finished film assets.

    python3 site/build.py --output /tmp/codecinema-site

Requires an authenticated GitHub CLI. Release assets are checked before a
deployment, and their IDs version video URLs when a master is replaced.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess

ROOT = Path(__file__).resolve().parent.parent
FILMS = {
    "film": ("films", ("SilverGrass.mp4",)),
    "nightrevels": ("films", ("NightRevels.mp4",)),
    "xishen": ("xishen/assets/film", ("ep01.mp4", "ep02.mp4", "ep03.mp4", "xishen_complete.mp4")),
}


def sha256(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def assemble(output, repo):
    output = output.resolve()
    if output == ROOT or ROOT.is_relative_to(output) or output.is_relative_to(ROOT / "site"):
        raise ValueError("Choose an output directory outside the site sources and repository ancestors")
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
    output.mkdir(parents=True, exist_ok=True)
    for source in (ROOT / "site").iterdir():
        if source.name in ("build.py", "__pycache__"):
            continue
        target = output / source.name
        if source.is_dir():
            shutil.copytree(source, target, dirs_exist_ok=True)
        else:
            shutil.copy2(source, target)
    shutil.copytree(ROOT / "assets/images", output / "img", dirs_exist_ok=True)
    for film in ("silvergrass", "nightrevels"):
        shutil.copytree(ROOT / f"films/{film}/assets/images", output / f"img/{film}", dirs_exist_ok=True)
    xishen = output / "xishen"
    xishen.mkdir(exist_ok=True)
    for name in ("watch.html", "watch.css", "watch.js"):
        shutil.copy2(ROOT / "films/xishen" / name, xishen / name)
    shutil.copytree(ROOT / "films/xishen/assets/images", xishen / "assets/images", dirs_exist_ok=True)

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

    revision = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"],
                              check=True, capture_output=True, text=True).stdout.strip()
    version = hashlib.sha256("\n".join([revision, *ids]).encode()).hexdigest()[:12]
    for path in output.rglob("*.html"):
        content = path.read_text(encoding="utf-8")
        content = re.sub(r"(<html\b[^>]*)(>)", rf'\1 data-media-version="{version}"\2', content, count=1)
        # Homepage episode buttons, initial sources and download fallbacks all
        # receive the same version. Dynamic screening URLs use the data above.
        content = re.sub(r'(\.(?:mp4|jpg|png|gif|svg))(["\'])', rf'\1?v={version}\2', content)
        content = re.sub(r'((?:src|href)="[^"?]+\.(?:js|css))(")', rf'\1?v={version}\2', content)
        path.write_text(content, encoding="utf-8")
    print(f"Site ready: {output} (media edition {version})", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", default="ZJUCQR/CodeCinema")
    parser.add_argument("--output", type=Path, default=ROOT / "out/site")
    options = parser.parse_args()
    assemble(options.output, options.repo)


if __name__ == "__main__":
    main()
