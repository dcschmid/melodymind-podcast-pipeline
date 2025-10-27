# MelodyMind Podcast Pipeline

Batch-generate split‑screen podcast-style videos (Daniel left / Annabelle right) from per‑segment audio files using `podcast_pipeline.py`.

This repository orchestrates per-segment processing with SadTalker to produce a final concatenated episode per decade and language.

## Table of contents

<details>
<summary>Click to expand table of contents</summary>

- [Highlights](#highlights)
- [Prerequisites & installation](#prerequisites--installation)
- [Basic usage](#basic-usage)
- [Inputs & outputs layout](#inputs--outputs-layout)
- [Intro / Outro](#intro--outro)
- [Key options](#key-options)
- [Tips & troubleshooting](#tips--troubleshooting)
- [Development notes](#development-notes)
- [Changelog](#changelog)
- [License](#license)

</details>

## Highlights

- Accepts common audio formats (wav, mp3, m4a, flac, aac). WAV files are supported out of the box.
- Single-speaker handling: missing partner audio is synthesized as a silent partner so layout remains consistent.
- Static-image shortcut for silent partners (faster) — enabled by default.
- Optional loudness normalization (EBU R128) and optional audio sidechain ducking.
- Intro/outro cover clips (image + optional music). Intro/outro are opt-in (disabled by default).
- Enhancers and background/face enhancement flags were removed/disabled; the pipeline runs SadTalker only for stability.

## Prerequisites & installation

- Linux (tested on Ubuntu/Debian)
- Python 3.8–3.11
- ffmpeg available on PATH (can be installed via conda-forge or system package manager)
- SadTalker cloned at `./SadTalker` with models downloaded

Recommended: use Miniconda to create a clean environment and install `ffmpeg` from conda-forge.

### Install Miniconda (Linux)

If you don't already have Miniconda/Anaconda, install Miniconda for Linux (x86_64) using the official installer. Example (safe, non-interactive install to $HOME/miniconda3):

```bash
# download installer
curl -fsSL -o ~/miniconda.sh https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh

# run installer (silent, installs to $HOME/miniconda3)
bash ~/miniconda.sh -b -p $HOME/miniconda3

# initialize conda for your shell and activate the changes in the current session
eval "$($HOME/miniconda3/bin/conda shell.bash hook)"
conda init
source ~/.bashrc

# (Optional) Remove installer
rm ~/miniconda.sh
```

If you're on ARM (Apple M1/M2) or need a different platform, grab the appropriate Miniconda installer from https://docs.conda.io/en/latest/miniconda.html.

```bash
# create and activate env
conda create -n melodymind python=3.10 -y
conda activate melodymind

# install ffmpeg + git
conda install -c conda-forge ffmpeg git -y

# install python deps for this repo
pip install -r requirements.txt
```

You can automate the steps above with the helper script included in this repository:

```bash
bash scripts/setup_conda.sh
```

The script will install Miniconda (if missing), create the `melodymind` environment, install `ffmpeg`/`git`, install Python deps, and clone the `SadTalker` repository skeleton (it will not auto-download large models).

### Optional: PyTorch nightly (CUDA 12.8) for RTX 5060

If you need a recent PyTorch build targeting CUDA 12.8 (for NVIDIA RTX 50xx GPUs), you can install the nightly wheels (run inside the activated conda env):

```bash
# For an RTX 5060 GPU (CUDA 12.8):
pip3 install --pre torch torchvision torchaudio --index-url https://download.pytorch.org/whl/nightly/cu128
```

Note: ensure your NVIDIA drivers support CUDA 12.8. If you prefer a pure conda install, check the `pytorch`/`conda-forge` channels for a matching cudatoolkit package. Nightly wheels may be needed for the latest features — use cautiously in production.

Setup SadTalker (required):

```bash
git clone https://github.com/OpenTalker/SadTalker.git
cd SadTalker
pip install -r requirements.txt
bash scripts/download_models.sh
cd ..
```

If you prefer system packages:

```bash
sudo apt update && sudo apt install -y ffmpeg
```

## Basic usage

```bash
# German (default)
python podcast_pipeline.py --decade 1960s --language de
```

With intro/outro (opt-in):

```bash
python podcast_pipeline.py --decade 1960s --language de \
	--intro-image covers/the-melody-mind-podcast.jpg --intro-audio intro/epic-metal.mp3 --intro-duration 5 \
	--outro-image covers/the-melody-mind-podcast.jpg --outro-duration 5
```

## Inputs & outputs layout

Inputs (per-decade, per-language):

```text
inputs/
	1960s/
		de/
			audio/      # *_daniel.wav, *_annabelle.wav etc.
			images/     # daniel.png, annabelle.png
```

Outputs structure:

```text
outputs/
	1960s/
		de/
			sadtalker/
			final/
			finished/
				1960s_de.mp4
```

Audio filename rules

- Use `<segment>_daniel.<ext>` or `<segment>_annabelle.<ext>` (ext = wav/mp3/m4a/flac/aac)
- If one side is missing the pipeline generates a silent partner audio file automatically.

## Intro / Outro

The pipeline can prepend/append simple cover clips (static image + optional music). Behaviour:

- Still image is looped for the specified duration (or matched to audio when `auto` is selected).
- Symmetric fade in/out is applied to both video and audio (default `--fade 1.0`).
- If no audio is provided a silent stereo track is synthesized to keep concat stable.

Examples:

```bash
# intro only (explicit opt-in)
python podcast_pipeline.py --decade 1960s --intro-image covers/intro.png --intro-duration 5

# auto duration (match audio length)
python podcast_pipeline.py --decade 1960s --intro-image covers/intro.png --intro-audio intro/theme_full.mp3 --intro-duration auto
```

Note: intro/outro are disabled by default in the CLI (opt-in). If you prefer explicit positive flags (e.g. `--with-intro`) I can refactor the parser.

## Key options

- `--language {de,en,es,fr,it,pt}` (default: de)
- `--fps` (default: 25)
- `--style {still|pose}`
- `--ducking` (enable sidechain ducking)
- `--no-loudnorm` (disable EBU R128)
- `--no-static-silent` (force SadTalker for silent partner)
- `--skip-existing` (resume using cached outputs)
- `--daniel-image`, `--annabelle-image` (override portraits)

## Tips & troubleshooting

- Provide high-resolution (1920x1080) cover images for intro/outro to avoid upscaling.
- Check `ffmpeg` is on PATH: `ffmpeg -version`.
- Check GPU and driver: `nvidia-smi` (drivers must match the CUDA toolchain if you install GPU-specific wheels).
- SadTalker: ensure `./SadTalker` exists and models are downloaded (`bash SadTalker/scripts/download_models.sh`).

### Deactivating / removing the conda environment

To leave the active conda environment (return to the base shell), run:

```bash
conda deactivate
```

To completely remove the `melodymind` environment and its packages:

```bash
conda remove -n melodymind --all
```

## Development notes

- The orchestrator is `podcast_pipeline.py`.
- SadTalker is invoked as a subprocess; `--sadtalker` should point to the SadTalker repo root.
- Enhancer packages (basicsr/gfpgan/realesrgan) were removed/disabled due to compatibility concerns; reintroducing them should be done as an optional plugin with pinned deps.

## Changelog (high level)

- Support for WAV and other audio formats
- Intro/outro now opt-in (disabled by default)
- Static-image shortcut for silent partner
- Enhancers removed; pipeline simplified to SadTalker-only

## License

Internal Melody Mind project materials. No warranty.


