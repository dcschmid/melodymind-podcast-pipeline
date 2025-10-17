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

### Multilingual Structure (NEW!)

The system now supports multiple languages with the following structure:

```text
./
├─ melody_mind_split.py
├─ SadTalker/
├─ inputs/
│  └─ 1960s/
│     ├─ de/      # German (default)
│     │  ├─ audio/   (*_daniel.mp3, *_annabelle.mp3)
│     │  └─ images/  (daniel.png, annabelle.png)
│     ├─ en/      # English
│     │  ├─ audio/
│     │  └─ images/
│     ├─ es/      # Spanish
│     │  ├─ audio/
│     │  └─ images/
│     └─ [fr, it, pt]/  # French, Italian, Portuguese
└─ outputs/
   └─ 1960s/
      ├─ de/     # German output -> 1960s_de.mp4
      ├─ en/     # English output -> 1960s_en.mp4
      └─ [es, fr, it, pt]/
```

**Supported Languages:** `de` (German), `en` (English), `es` (Spanish), `fr` (French), `it` (Italian), `pt` (Portuguese)

Each segment needs at least one of: `*_daniel.mp3` or `*_annabelle.mp3`. If the counterpart is missing a silent partner track is auto-generated keeping layout consistent.

---

## Basic Usage

### Multilingual Usage

```bash
# German (default)
python melody_mind_split.py --decade 1960s --language de

# English
python melody_mind_split.py --decade 1960s --language en

# Spanish
python melody_mind_split.py --decade 1960s --language es

# Other languages: fr, it, pt
```

### Legacy/Single Language (still works)

```bash
python melody_mind_split.py --decade 1960s
```

### Advanced Examples

```bash
# Custom English version
python melody_mind_split.py --decade 1960s --language en --fps 25 --style still \
  --sadtalker ./SadTalker --preprocess full --enhancer gfpgan --ducking

# Resume run (skip already processed segments)
python melody_mind_split.py --decade 1960s --language de --skip-existing
```

---

## Key Options

* `--language {de,en,es,fr,it,pt}` Language code for multilingual support (default: de)
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

## Multilingual Setup & Tips

### Quick Setup for Multiple Languages

```bash
# Create directories for all languages (done automatically)
mkdir -p inputs/1960s/{de,en,es,fr,it,pt}/{audio,images}

# Place audio files in language-specific directories:
# inputs/1960s/de/audio/segment01_daniel.mp3
# inputs/1960s/en/audio/segment01_daniel.mp3
# etc.
```

### Character Images

Character images (`daniel.png`, `annabelle.png`) are automatically copied to all language directories. 

**For language-specific characters:** Replace images in the respective `images/` directories:
- `inputs/1960s/de/images/daniel.png` (German Daniel)
- `inputs/1960s/en/images/daniel.png` (English Daniel)
- etc.

### Output Files

Language-specific output files:
- German: `outputs/1960s/de/finished/1960s_de.mp4`
- English: `outputs/1960s/en/finished/1960s_en.mp4`
- Spanish: `outputs/1960s/es/finished/1960s_es.mp4`
- etc.

### Processing Tips

1. **Cache Benefits:** Each language has separate cache directories (SadTalker outputs)
2. **Parallel Processing:** You can run different languages simultaneously
3. **Incremental Work:** Use `--skip-existing` to resume interrupted runs per language
4. **Default Language:** If no `--language` specified, defaults to German (`de`)

---

## Output Structure

### Multilingual Output Structure

```text
outputs/<DECADE>/
  <LANGUAGE>/              # e.g., de/, en/, es/
    sadtalker/
      daniel/<segment>/<segment>_daniel.mp4
      annabelle/<segment>/<segment>_annabelle.mp4
    final/
      <segment>_split_core.mp4
    finished/
      <DECADE>_<LANGUAGE>.mp4    # e.g., 1960s_de.mp4
```

The final `<DECADE>_<LANGUAGE>.mp4` is created by concatenating all `*_split_core.mp4` files in sorted order.

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


