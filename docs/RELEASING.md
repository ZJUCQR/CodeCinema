# Publishing the example films

The homepage plays the finished MP4s attached to three parallel releases:

| Film | Release tag | Finished assets |
| --- | --- | --- |
| Duel in the Silver Grass | `film` | `SilverGrass.mp4` |
| The Night Revels of Han Xizai, Cat Edition | `nightrevels` | `NightRevels.mp4` |
| I Am Not the God of Drama: The Opening Trilogy | `xishen` | `ep01.mp4`, `ep02.mp4`, `ep03.mp4`, `xishen_complete.mp4` |

Finish rendering and run the film's quality checks before replacing its release
assets. Keep the filenames stable so existing download links continue to work.
Attach finished films only; intermediate clips, Blender studies, frames,
diagnostics and checksum files belong in the local ignored output directory.
Unchanged films already match their release and do not need uploading again.
The film-name tags identify the current published source edition; keep them
aligned with the source commit used for the finished masters.

For the opening trilogy, run from the repository root:

```bash
codecinema run xishen refresh --opening-renderer blender --narration required --speech-engine local
gh release upload xishen films/xishen/assets/film/ep01.mp4 films/xishen/assets/film/ep02.mp4 films/xishen/assets/film/ep03.mp4 films/xishen/assets/film/xishen_complete.mp4 --clobber
gh workflow run pages.yml --ref main
```

`refresh` reuses existing base picture and the two Blender opening clips. Use
`all --opening-renderer blender` to produce the mixed edition from scratch.

Commit and push any source, poster and webpage updates to `main` first. Upload
all changed finished assets, then run the Pages workflow on `main`. Replacing
an asset does not trigger a release publication event, so dispatch the workflow
explicitly even if the release already exists. Release notes should use the
same specification, downloads and reproduction sections for all three films,
and describe the actual published renderer and edition.

The site builder downloads only the six expected finished MP4s, verifies their
sizes and GitHub-provided digests, and versions video URLs using the asset IDs.
Incomplete releases fail the build before deployment, keeping the previous
site online. The homepage and screening room receive the same media edition,
including after an episode switch.

To inspect the assembled site locally:

```bash
python3 site/build.py
python3 -m http.server 8080 --directory out/site
```
