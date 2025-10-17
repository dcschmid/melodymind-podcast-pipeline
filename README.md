# MelodyMind Video Pipeline (SadTalker Only)

Batch-generate split‑screen podcast style videos (Daniel left / Annabelle right) from per‑segment MP3 files.

Per segment the pipeline:

1. Converts input MP3 to 16 kHz mono WAV.
2. Creates a silent partner WAV if only one speaker file exists.
3. Runs SadTalker for each portrait (unless silent -> optional static image shortcut).
4. Builds a 1920x1080 side‑by‑side video (no center gap) and mixes audio (optionally loudness normalization + ducking).
5. After all segments: concatenates a single `<decade>.mp4`.

Linux only (tested on Ubuntu/Debian). Python 3.8–3.10 recommended.

---

## Requirements

* Python 3.8–3.10
* ffmpeg
* SadTalker repo cloned at `./SadTalker` with models downloaded (`bash scripts/download_models.sh` inside SadTalker)

### Install ffmpeg (Ubuntu/Debian)

```bash
sudo apt update && sudo apt install -y ffmpeg python3-venv git
```

### Get SadTalker

```bash
git clone https://github.com/OpenTalker/SadTalker.git
cd SadTalker
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
bash scripts/download_models.sh
deactivate
cd ..
```

---

## Directory Layout

```text
./
├─ melody_mind_split.py
├─ SadTalker/
├─ inputs/
│  └─ 1960s/
│     ├─ audio/   (1960s_segment_001_daniel.mp3, 1960s_segment_002_annabelle.mp3, ...)
│     └─ images/  (daniel.png, annabelle.png)
└─ outputs/
```

Each segment needs at least one of: `*_daniel.mp3` or `*_annabelle.mp3`. If the counterpart is missing a silent partner track is auto-generated keeping layout consistent.

---

## Basic Usage

```bash
python melody_mind_split.py --decade 1960s
```

Custom example:

```bash
python melody_mind_split.py --decade 1960s --fps 25 --style still \
  --sadtalker ./SadTalker --preprocess full --enhancer gfpgan --ducking
```

Resume run (skip already processed segments):

```bash
python melody_mind_split.py --decade 1960s --skip-existing
```

---

## Key Options

* `--fps` Target frame rate (default 25)
* `--style {still|pose}` Head motion style (still = calmer)
* `--preprocess {crop|resize|full}` SadTalker preprocessing (default: full)
* `--enhancer {gfpgan|RestoreFormer|none}` Face enhancer
* `--background-enhancer {realesrgan|none}` Optional full-frame upscaler
* `--no-enhancers` Disable face & background enhancement entirely
* `--ducking` Sidechain compression (reduces other speaker loudness)
* `--no-loudnorm` Disable EBU R128 loudness normalization
* `--no-static-silent` Force SadTalker even for silent partner (slower, may improve uniformity)
* `--skip-existing` Cache mode: if both speaker mp4s and final split_core exist the segment is skipped
* `--daniel-image / --annabelle-image` Override portraits for the run
* `--audio-dir` Override audio directory for the selected decade
* `--quiet` Minimal output / `--verbose` more diagnostic detail
* Intro / Outro (new):
  * `--intro-image`, `--intro-audio`, `--intro-duration`, `--no-intro`
  * `--outro-image`, `--outro-audio`, `--outro-duration`, `--no-outro`
  * `--fade` (applies to both intro & outro audio/video fades)

---

## Intro / Outro Feature

* You can set `--intro-duration auto` or `--outro-duration auto` to use the exact length of the provided audio file.
You can prepend and append simple cover clips (static image + optional music) automatically.

Behavior:

* Still image is looped for the specified duration (default 5s).
* If you provide an audio file it is trimmed (not looped) to the duration.
* Symmetric fade in/out is applied to both video and audio (default 1s).
* If no audio given a silent stereo track is synthesized to keep concat stable.

Basic example (image only):

```bash
python melody_mind_split.py --decade 1960s \
  --intro-image covers/intro.png \
Auto duration example (matches audio length):

```bash
python melody_mind_split.py --decade 1960s \
  --intro-image covers/intro.png --intro-audio intro/theme_full.mp3 --intro-duration auto \
  --outro-image covers/outro.png --outro-audio intro/outro_jingle.mp3 --outro-duration auto
```
  --outro-image covers/outro.png
```

With music and custom durations/fade:

```bash
python melody_mind_split.py --decade 1960s \
  --intro-image covers/intro.png --intro-audio intro/intro_music.mp3 --intro-duration 6 \
  --outro-image covers/outro.png --outro-audio intro/outro_music.mp3 --outro-duration 8 \
  --fade 1.5
```

Disable only the intro (while keeping outro):

```bash
python melody_mind_split.py --decade 1960s \
  --intro-image covers/intro.png --no-intro \
  --outro-image covers/outro.png
```

Tips:

* Ensure audio is at least as long as the requested duration (otherwise it will just cut early).
* Use a slightly larger fade (1–2s) for smoother transitions when concatenated.
* Provide high-resolution PNGs (e.g. 1920x1080) to avoid upscaling artifacts.

---

## Output Structure

```text
outputs/<DECADE>/
  sadtalker/
    daniel/<segment>/<segment>_daniel.mp4
    annabelle/<segment>/<segment>_annabelle.mp4
  final/
    <segment>_split_core.mp4
  finished/
    <DECADE>.mp4
```

The final `<DECADE>.mp4` is created by concatenating all `*_split_core.mp4` files in sorted order.

---

## Changelog (abridged)

* Single-speaker handling with silent partner
* Final episode concatenation step
* Video encoder auto-selection with fallbacks
* Loudness normalization + optional ducking
* Static image shortcut for silent partner
* Skip caching via `--skip-existing`
* Removed experimental EchoMimic support (repository simplified to SadTalker only)

---

## License

Internal use for the Melody Mind project. No warranty.


