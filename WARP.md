# WARP.md

This file provides guidance to WARP (warp.dev) when working with code in this repository.

## Project Overview

MelodyMind Podcast Pipeline is a batch video generation system that creates split-screen podcast-style videos from per-segment audio files. It generates 1920x1080 videos with Daniel on the left and Annabelle on the right, using SadTalker for AI-driven facial animation.

**Key Technologies:**
- Python 3.8-3.10 (Linux only)
- FFmpeg for video processing
- SadTalker (external dependency) for facial animation
- Multilingual support: German (de), English (en), Spanish (es), French (fr), Italian (it), Portuguese (pt)

## Core Architecture

### Single-File Design
The entire pipeline is contained in `podcast_pipeline.py` (~710 lines). The design is intentionally monolithic for simplicity and portability.

### Processing Pipeline Flow
1. **Audio Preparation**: Convert input audio (MP3/WAV/M4A/FLAC/AAC) to 16kHz mono WAV
2. **Silent Partner Generation**: Auto-create silent audio tracks when only one speaker file exists (enables single-speaker segments)
3. **Facial Animation**: Run SadTalker on each portrait or use static image shortcut for silent partners
4. **Composition**: Build split-screen layout (960x1080 per speaker), mix audio with optional ducking/loudness normalization
5. **Concatenation**: Combine all segments into final `<decade>_<language>.mp4` with optional intro/outro

### Directory Structure Pattern
```
inputs/<DECADE>/<LANGUAGE>/audio/*_daniel.mp3, *_annabelle.mp3
inputs/<DECADE>/<LANGUAGE>/images/daniel.png, annabelle.png
outputs/<DECADE>/<LANGUAGE>/sadtalker/daniel/, annabelle/
outputs/<DECADE>/<LANGUAGE>/final/*_split_core.mp4
outputs/<DECADE>/<LANGUAGE>/finished/<DECADE>_<LANGUAGE>.mp4
```

Language code is critical to pipeline behavior - each language maintains separate cache and output directories.

### Key Design Patterns

**Encoder Fallback System**: `select_video_encoder()` probes FFmpeg for available codecs (libx264 → libopenh264 → h264_nvenc → AV1 → VP9 → copy) and auto-selects best available to handle GPL vs non-GPL FFmpeg builds.

**Dependency Resilience**: Automatic enhancer detection disables gfpgan/realesrgan if torchvision API incompatibility detected (common with torch>=2.0 + basicsr expecting old functional_tensor API).

**Audio Format Flexibility**: Pipeline accepts MP3, WAV, M4A, FLAC, AAC via `as_wav()` normalization layer.

**Cache-Aware Processing**: `--skip-existing` enables resumable runs by checking for pre-existing SadTalker outputs and final split videos.

## Common Development Commands

### Basic Pipeline Execution
```bash
# German (default language)
python podcast_pipeline.py --decade 1960s --language de

# English with quality options
python podcast_pipeline.py --decade 1960s --language en \
  --fps 30 --style still --enhancer gfpgan --ducking --loudnorm --verbose

# Resume interrupted run (skip cached segments)
python podcast_pipeline.py --decade 1960s --language de --skip-existing
```

### Testing & Validation
No formal test suite exists. Manual validation workflow:
```bash
# Dry-run check (look for missing images/audio before processing)
ls inputs/1960s/de/audio/*_daniel.mp3 inputs/1960s/de/audio/*_annabelle.mp3
ls inputs/1960s/de/images/daniel.png inputs/1960s/de/images/annabelle.png

# Process single decade, monitor output
python podcast_pipeline.py --decade 1960s --language de --verbose

# Verify final output exists
ls -lh outputs/1960s/de/finished/1960s_de.mp4
```

### SadTalker Setup (Required Dependency)
```bash
# Initial setup (must be done once per environment)
git clone https://github.com/OpenTalker/SadTalker.git
cd SadTalker
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
bash scripts/download_models.sh  # Downloads ~2GB of models
deactivate
cd ..
```

SadTalker must exist at `./SadTalker` (default) or path specified via `--sadtalker`.

### Intro/Outro Generation
```bash
# With auto-duration matching audio length
python podcast_pipeline.py --decade 1960s --language de \
  --intro-image covers/podcast-de.png \
  --intro-audio intro/epic-metal.mp3 \
  --intro-duration auto \
  --outro-image covers/podcast-de.png \
  --outro-duration auto \
  --fade 1.5
```

## File Naming Conventions

**Input Audio**: Must follow `<segment>_daniel.mp3` or `<segment>_annabelle.mp3` pattern. Segment prefix determines ordering (sorted lexicographically). Missing partner files trigger silent audio generation.

**Character Images**: Fixed names `daniel.png` and `annabelle.png` in `inputs/<decade>/<language>/images/`. Override via `--daniel-image` or `--annabelle-image`.

**Output Videos**: Final concatenated video named `<decade>_<language>.mp4` (e.g., `1960s_de.mp4`, `1960s_en.mp4`).

## Important Implementation Details

### FFmpeg Filter Complexity
Split-screen layout uses complex filter chains in `build_split_filter()`:
- Each input scaled to 960x1080 bounding box (preserves aspect ratio)
- Left speaker: padded left-aligned (speaking head touches center)
- Right speaker: padded right-aligned (speaking head touches center)
- Audio: either simple amix or sidechain ducking (reduces inactive speaker volume)

### Loudness Normalization
EBU R128 normalization via FFmpeg `loudnorm` filter (target -16 LUFS). Enabled by default, disable with `--no-loudnorm`.

### Static vs. Animated Silent Partners
When partner audio is silent, `--static-silent` (default) generates still image video instead of running SadTalker. Faster but may show visual discontinuity. Use `--no-static-silent` to force SadTalker for uniform quality.

### Enhancer Dependency Hell
gfpgan/realesrgan depend on basicsr which expects `torchvision.transforms.functional_tensor` (removed in torchvision 0.15+). Pipeline auto-detects breakage and disables enhancers. Suggested stable combo: `torch==1.13.* / torchvision==0.14.*`.

## Modifying the Pipeline

### Adding New Language Support
1. Add language code to `--language` choices in `build_arg_parser()` (line 625)
2. Create directory structure: `mkdir -p inputs/<decade>/<lang>/{audio,images}`
3. Place character images and audio files
4. No code changes needed - directory structure drives behavior

### Changing Video Layout
Modify `build_split_filter()` (line 183-217):
- Current: 1920x1080 split (960px per speaker)
- Scale/pad arithmetic in filter chain controls positioning
- Watch for aspect ratio preservation vs. distortion tradeoffs

### Custom Audio Processing
Audio filters applied in two stages:
1. Per-segment: `loudnorm_filter()` applied during split-screen composition
2. Final concat: Re-encode pass via `concat_final_segments()`

Insert custom filters in `build_split_filter()` audio chain or modify `loudnorm_filter()`.

### Encoder Preferences
Edit `select_video_encoder()` (line 100-118) to reorder codec preferences. Ensure fallback logic in segment processing (line 544-567) matches.

## Performance Considerations

**Bottleneck**: SadTalker inference (~30s-2min per segment depending on GPU). Use `--skip-existing` for iterative work.

**Parallel Processing**: Safe to run multiple languages simultaneously - separate cache directories prevent conflicts.

**Memory**: SadTalker requires ~4-6GB GPU VRAM. Falls back to CPU if CUDA unavailable (extremely slow).

## Troubleshooting Common Issues

**"No segment files found"**: Verify audio files match `*_daniel.mp3` or `*_annabelle.mp3` pattern in correct language subdirectory.

**Encoder errors**: FFmpeg build may lack libx264. Pipeline auto-falls back to libopenh264/libx265. Worst case: install full FFmpeg (`sudo apt install ffmpeg`).

**Enhancer crashes**: Torchvision version mismatch. Either downgrade (`pip install torch==1.13.1 torchvision==0.14.1`) or use `--no-enhancers`.

**SadTalker not found**: Ensure `./SadTalker/inference.py` exists or specify correct path via `--sadtalker`.

**Audio sync issues**: Verify input audio sample rate (pipeline converts to 16kHz). Mismatched rates in source files may cause drift.
