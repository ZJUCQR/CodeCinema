# Changelog

Notable changes to CodeCinema. Versions follow [Semantic Versioning](https://semver.org/).

## [2.1.0] - 2026-10-08

### Added

- **Screenplay cartoons** (`production = "cartoon"`): a cast from the character library, sets, times of day, props and effects, scenes of shots with timed beats, an automatic camera director (shot sizes, sides, angles and moves that avoid obstacles), lip sync, Foley, titles and subtitles. `codecinema new <id> --template cartoon` starts one.
- **Character library**: 24 characters (new: toddler, teen, chef, dog, bear, panda, mouse, pig, duck and chick) built from shared parts: six body shapes, head shapes, a dozen hair styles, seven hats, accessories (glasses, scarf, earmuffs, ribbon, moustache, bow tie, backpack) and animal ears, snouts and tails. `codecinema library --sheet` renders them in their signature poses.
- **Motion**: springy entry and exit with overshoot, wind-ups, follow-through on heads, ears, tails, flippers, hands and scarves, squash and stretch, leaning into speed changes and turns, weight shifts and eye movements at rest, gestures and nods that follow the voice, turns where the head leads and the feet step, rounded paths, bending flippers and wing tips.
- **Staging checks**: `plan` warns about moves too fast for their gait and about overlapping lines; misspelled fonts fail at `plan`.
- **Sound library**: 113 instruments (a SoundFont player for the General MIDI bank GeneralUser GS with synthesized fallbacks, Chinese and Japanese instruments, organs, guitars, saxophones, 8-bit voices), a composer with theme notation and 27 styles, 163 procedural sound effects, 30 ambience beds, 20 cartoon voice profiles with 39 vocalizations, and a mixer with buses, ducking, acoustic spaces and loudness mastering.
- **Fonts**: a catalog of 73 open-licensed families for Latin, Chinese, Japanese, Korean, Arabic, Devanagari, Thai and Hebrew, downloaded on demand from pinned sources with checksums, mirrors and offline switches; per-script fallback for mixed-language text and complex-script shaping on every platform. `codecinema library fonts` lists, prefetches and samples them.
- **Voices on every platform**: recordings, a local neural voice, the system voice (macOS, Windows, Linux) or cartoon babble; takes can be stored with a film.
- **Example films**: *Pebble* (English) and *Nian* (Mandarin), each a single screenplay.
- **Project health**: a pytest suite (no Blender or network needed), CI tests on Linux, macOS and Windows, a `dev` extra, a Code of Conduct, a security policy and this changelog.

### Changed

- Packaging lists the bundled resources once for wheels and source archives (no `MANIFEST.in`) and declares its license as an SPDX expression.
- `codecinema library` lists styles and voices with descriptions and never downloads the sound bank just to list instruments.

### Fixed

- Repeated beats are capped so flapping no longer strobes at 24 fps; beat phases no longer jump when speed changes.
- Characters no longer skate: step rates are capped per gait and strides lengthen instead.
- Poses held from a shot's start now end at the next starting state instead of lasting for the rest of the film.
- A spin no longer unwinds backwards when it ends; look targets blend instead of snapping; close shots keep the whole head in frame during jumps.

### Removed

- The *The Last Beacon* and *I Am Not the God of Drama* examples.
- Obsolete stand-in event tools of the *Silver Grass* production pack and unused helpers across the framework.

## [2.0.0] - 2026-10-08

### Changed

- Films became data: story files live in `films/<id>/`, media in `assets/<id>/`, and every film's settings in the root `pyproject.toml`.
- The framework was organized into focused packages (`workspace`, `engine`, `runtime`, `renderers`, `studio`, `audio`, `productions`) with a renderer plugin interface for Skia, Blender and third-party backends.
- The local Studio edits scenes, looks, formats and voices and renders in the background.
