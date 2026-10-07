# Publishing the example films

The homepage plays the finished MP4s attached to parallel film releases:

| Film | Release tag | Finished assets |
| --- | --- | --- |
| Duel in the Silver Grass | `film` | `SilverGrass.mp4` |
| The Night Revels of Han Xizai, Cat Edition | `nightrevels` | `NightRevels.mp4` |
| The Last Beacon | `beacon` | `TheLastBeacon.mp4` |
| I Am Not the God of Drama: The Opening Trilogy | `xishen` | `ep01.mp4`, `ep02.mp4`, `ep03.mp4`, `xishen_complete.mp4` |

Finish rendering and run the film's quality checks before replacing its release
assets. Keep the filenames stable so existing download links continue to work.
Attach finished films only; intermediate clips, frames,
diagnostics and checksum files belong in the local ignored output directory.
Unchanged films already match their release and do not need uploading again.
The film-name tags identify the current published source edition; keep them
aligned with the source commit used for the finished masters.

For the opening trilogy, run from the repository root:

```bash
codecinema run xishen all --narration required --speech-engine local
git push origin main
gh release upload xishen films/xishen/assets/film/ep01.mp4 films/xishen/assets/film/ep02.mp4 films/xishen/assets/film/ep03.mp4 films/xishen/assets/film/xishen_complete.mp4 --clobber
gh release edit film --notes-file films/silvergrass/RELEASE.md
gh release edit nightrevels --notes-file films/nightrevels/RELEASE.md
gh release edit xishen --notes-file films/xishen/RELEASE.md
gh workflow run pages.yml --ref main
```

The trilogy uses Skia throughout. `all` regenerates changed inputs and reuses
completed render chunks only when their source and settings signatures match.

Commit and push any source, poster and webpage updates to `main` first. Upload
all changed finished assets, then run the Pages workflow on `main`. Replacing
an asset does not trigger a release publication event, so dispatch the workflow
explicitly even if the release already exists. Release notes should use the
same specification, downloads and reproduction sections for every example film,
and describe the actual published renderer and edition. Each film's tracked
`RELEASE.md` is the canonical release description; publish it with `--notes-file`
so the repository and GitHub show the same instructions.

The site builder downloads only the expected finished MP4s listed in `site/build.py`, verifies their
sizes and GitHub-provided digests, and versions video URLs using the asset IDs.
Each build starts in a fresh staging directory, so removed files do not survive
from an earlier edition. A completed build replaces the old staging directory.
Incomplete releases fail the build before deployment, keeping the previous
site online. The homepage and screening room receive the same media edition,
including after an episode switch.

To inspect the assembled site locally:

```bash
python3 site/build.py
python3 -m http.server 8080 --directory out/site
```

Custom output directories must be empty or contain a previous CodeCinema site
build marker. Repository source folders are rejected as output paths.
