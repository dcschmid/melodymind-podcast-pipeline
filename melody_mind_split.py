#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""MelodyMind Video Pipeline (Linux)

Steps per segment:
    1. Convert *_daniel.mp3 / *_annabelle.mp3 to 16 kHz mono WAV.
    2. Generate missing partner silent WAV (single-speaker segments supported).
    3. Run SadTalker for each portrait (Daniel, Annabelle) to produce per-speaker MP4.
    4. Build 1920x1080 side‑by‑side split video (no middle gap) & mix audio (amix or ducking).
    5. (Optional) Loudness normalization (EBU R128).
    6. After all segments: concatenate into one finished video <decade>.mp4.

Design goals:
    - Robust ffmpeg encoder selection (works even without libx264).
    - Graceful fallback encoders.
    - Minimal console output (use --verbose for full detail).
    - English comments & clear structure.
"""

import argparse
import sys
import shutil
import subprocess
import re
from pathlib import Path
from typing import Optional, Union
import tempfile
import os

# --------------------------------------------------------------------------------------
# Logging helpers
# --------------------------------------------------------------------------------------

class Logger:
    def __init__(self, verbose: bool, quiet: bool):
        self.verbose = verbose
        self.quiet = quiet

    def info(self, msg: str):
        if not self.quiet:
            print(msg, flush=True)

    def verbose_msg(self, msg: str):
        if self.verbose and not self.quiet:
            print(msg, flush=True)

    def warn(self, msg: str):
        if not self.quiet:
            print(f"WARNING: {msg}", flush=True)

    def error(self, msg: str):
        print(f"ERROR: {msg}", flush=True, file=sys.stderr)


def run(cmd, cwd=None, quiet=False, verbose=False):
    """Run a shell command with error handling.

    Parameters
    ----------
    cmd : list[str]
        Command tokens.
    cwd : str | Path | None
        Working directory for the process.
    quiet : bool
        Suppress command line echo.
    verbose : bool
        If True, do not hide ffmpeg's banner / lower loglevel.
    """
    display_cmd = [str(c) for c in cmd]
    if not verbose:
        # Add ffmpeg quieting flags when appropriate.
        if display_cmd and display_cmd[0].endswith('ffmpeg') and '-loglevel' not in display_cmd:
            display_cmd.insert(1, '-hide_banner')
            display_cmd.insert(2, '-loglevel')
            display_cmd.insert(3, 'error')
    if not quiet:
        print(" $", " ".join(display_cmd), flush=True)
    res = subprocess.run(display_cmd, cwd=cwd)
    if res.returncode != 0:
        raise RuntimeError(f"Command failed: {' '.join(display_cmd)}")


def ensure_dir(p: Path):
    p.mkdir(parents=True, exist_ok=True)


def ffmpeg_exists() -> bool:
    return shutil.which("ffmpeg") is not None


def python_exists() -> bool:
    return shutil.which("python") is not None or shutil.which("python3") is not None


def py_exec() -> str:
    return shutil.which("python") or shutil.which("python3")


def select_video_encoder() -> str:
    """Return preferred available video encoder or 'copy'."""
    try:
        out = subprocess.check_output(["ffmpeg", "-hide_banner", "-encoders"], text=True, stderr=subprocess.STDOUT)
    except Exception:
        return "copy"
    prefs = [
        ("libx264", r"\blibx264\b"),          # GPL build
        ("libopenh264", r"\blibopenh264\b"),  # Non-GPL alternative
        ("h264_nvenc", r"\bh264_nvenc\b"),
        ("libsvtav1", r"\blibsvtav1\b"),
        ("libaom-av1", r"\blibaom-av1\b"),
        ("libx265", r"\blibx265\b"),
        ("libvpx-vp9", r"\blibvpx-vp9\b"),
    ]
    for name, pat in prefs:
        if re.search(pat, out):
            return name
    return "copy"


def make_static_video(image_path: Path, audio_wav: Path, out_path: Path, fps: int, encoder: str, logger: 'Logger'):
    """Create a simple still-image video for the duration of audio_wav.

    Speeds up generation for silent partner (no need to run SadTalker).
    """
    if out_path.exists():
        logger.verbose_msg(f"Skip static video (exists): {out_path}")
        return
    enc_args = ["-c:v", encoder]
    if encoder.startswith("libx"):
        # Better quality for still images
        enc_args += ["-crf", "18"]
        if encoder == "libx264":
            enc_args += ["-tune", "stillimage"]
    elif encoder == "libopenh264":
        enc_args += ["-b:v", "1M"]

    run([
        "ffmpeg", "-y",
        "-loop", "1",
        "-i", str(image_path),
        "-i", str(audio_wav),
        *enc_args,
        "-r", str(fps),
        "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k",
        "-shortest",
        str(out_path)
    ], quiet=True, verbose=logger.verbose)
    logger.verbose_msg(f"Created static partner video: {out_path}")


 


def as_wav(mp3_path: Path, wav_dir: Path) -> Path:
    """Convert MP3 to 16kHz mono WAV if needed."""
    ensure_dir(wav_dir)
    out = wav_dir / (mp3_path.stem + ".wav")
    if not out.exists():
        run([
            "ffmpeg", "-y",
            "-i", str(mp3_path),
            "-ar", "16000", "-ac", "1",
            str(out)
        ], quiet=True)
    return out


def loudnorm_filter(use_loudnorm: bool) -> str:
    """Return audio filter for loudness normalization (EBU R128) or passthrough."""
    if use_loudnorm:
        return "loudnorm=I=-16:TP=-1.5:LRA=11:dual_mono=true"
    return "anull"


def build_split_filter(use_ducking: bool) -> str:
    """
    ffmpeg filter_complex for:
      - scale/pad both videos to 960x1080
      - hstack → 1920x1080
      - audio: either amix or sidechain ducking + amix
    Produces [v] and [a].
    """
    # Scale each input into a 960x1080 bounding box preserving aspect, then pad to exactly 960x1080.
    # Layout goal: images touch in the center (no black vertical bar).
    # Left side: pad only on the left so the speaking head is right-aligned inside its half.
    # Right side: pad at x=0 so the head is left-aligned.
    # Vertical centering via y=(1080-ih)/2.
    common_video = (
        "[0:v]scale=960:1080:force_original_aspect_ratio=decrease,"
        "pad=960:1080:(960-iw):(1080-ih)/2:black[left];"
        "[1:v]scale=960:1080:force_original_aspect_ratio=decrease,"
        "pad=960:1080:0:(1080-ih)/2:black[right];"
        "[left][right]hstack=inputs=2[v];"
    )
    if use_ducking:
        audio = (
            "[0:a]aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo,volume=1.0[a0];"
            "[1:a]aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo,volume=1.0[a1];"
            "[a0][a1]sidechaincompress=threshold=0.02:ratio=8:attack=50:release=200:makeup=1[a0d];"
            "[a1][a0]sidechaincompress=threshold=0.02:ratio=8:attack=50:release=200:makeup=1[a1d];"
            "[a0d][a1d]amix=inputs=2:normalize=0:dropout_transition=0[amix]"
        )
    else:
        audio = (
            "[0:a]aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo,volume=1.0[a0];"
            "[1:a]aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo,volume=1.0[a1];"
            "[a0][a1]amix=inputs=2:normalize=0:dropout_transition=0[amix]"
        )
    return common_video + audio


###################################################################################################
# Intro / Outro Clip Creation
###################################################################################################
def probe_audio_duration(audio: Path) -> Optional[float]:
    """Return audio duration in seconds using ffprobe (None if probing fails)."""
    if not audio or not audio.exists():
        return None
    try:
        out = subprocess.check_output([
            'ffprobe', '-v', 'error', '-show_entries', 'format=duration',
            '-of', 'default=noprint_wrappers=1:nokey=1', str(audio)
        ], text=True)
        return float(out.strip())
    except Exception:
        return None


def create_cover_clip(image: Path, out_file: Path, duration: Union[float, str], fade: float, fps: int, encoder: str,
                      logger: 'Logger', audio: Optional[Path] = None):
    """Create a cover (intro/outro) clip from a still image with optional music.

    Behaviour:
        * Loops the still image for the specified duration (or audio length when duration='auto').
        * If audio provided: trimmed (no loop). User should supply long enough audio unless using duration='auto'.
        * Adds symmetrical fade in/out (video & audio) using 'fade' seconds.
        * If no audio provided a silent stereo track is synthesized so concat stays robust.
    """
    if out_file.exists():
        logger.verbose_msg(f"Skip cover clip (exists): {out_file}")
        return
    if not image.exists():
        raise FileNotFoundError(f"Cover image not found: {image}")
    if audio and not audio.exists():
        raise FileNotFoundError(f"Cover audio not found: {audio}")

    # Build ffmpeg command
    if isinstance(duration, str) and duration == 'auto':
        auto_dur = probe_audio_duration(audio)
        if auto_dur is None:
            raise RuntimeError("duration='auto' requested but audio missing or probing failed")
        duration = auto_dur
    if duration <= 0:
        raise ValueError(f"Cover clip duration must be > 0 (got {duration})")
    vf = f"fade=t=in:st=0:d={fade},fade=t=out:st={max(0,duration-fade)}:d={fade},fps={fps},format=yuv420p"
    af = []
    inputs = ["ffmpeg", "-y", "-loop", "1", "-i", str(image)]
    if audio:
        inputs += ["-i", str(audio)]
        afade = f"afade=t=in:st=0:d={fade},afade=t=out:st={max(0,duration-fade)}:d={fade}"
        af = ["-filter:a", afade]
    else:
    # Synthesize silence (keeps concat stable with consistent streams)
        inputs += ["-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=48000"]
        afade = f"afade=t=in:st=0:d={fade},afade=t=out:st={max(0,duration-fade)}:d={fade}"
        af = ["-filter:a", afade]

    enc_args = ["-c:v", encoder]
    if encoder.startswith("libx"):
        enc_args += ["-crf", "18"]
        if encoder == "libx264":
            enc_args += ["-tune", "stillimage"]
    elif encoder == "libopenh264":
        enc_args += ["-b:v", "1M"]

    cmd = [
        *inputs,
        *enc_args,
        "-pix_fmt", "yuv420p",
        "-vf", vf,
        *af,
        "-c:a", "aac", "-b:a", "192k",
        "-t", f"{duration}",
        "-shortest",
        str(out_file)
    ]
    try:
        run(cmd, quiet=True)
        logger.verbose_msg(f"Created cover clip: {out_file}")
    except Exception as e:
        raise RuntimeError(f"Failed creating cover clip {out_file}: {e}")


def process_decade(args):
    root = Path.cwd()
    decade = args.decade
    fps = args.fps
    sadtalker_dir = Path(args.sadtalker).resolve()
    if not sadtalker_dir.exists():
        raise SystemExit(f"SadTalker folder not found: {sadtalker_dir}")

    decade_in = root / "inputs" / decade
    audio_dir = Path(args.audio_dir).resolve() if args.audio_dir else (decade_in / "audio").resolve()
    img_dir = (decade_in / "images").resolve()

    out_base = root / "outputs" / decade
    out_st_d = out_base / "sadtalker" / "daniel"
    out_st_a = out_base / "sadtalker" / "annabelle"
    out_final = out_base / "final"
    tmp_dir = out_base / ".tmp_prepared"

    # Resolve images and intro/outro
    daniel_img = Path(args.daniel_image).resolve() if args.daniel_image else (img_dir / "daniel.png")
    annabelle_img = Path(args.annabelle_image).resolve() if args.annabelle_image else (img_dir / "annabelle.png")
    # Optional intro/outro assets
    intro_img = Path(args.intro_image).resolve() if args.intro_image else None
    outro_img = Path(args.outro_image).resolve() if args.outro_image else None
    intro_audio = Path(args.intro_audio).resolve() if args.intro_audio else None
    outro_audio = Path(args.outro_audio).resolve() if args.outro_audio else None

    # Basic path & asset checks
    if not ffmpeg_exists():
        raise SystemExit("ffmpeg not found. Please install ffmpeg.")
    if not python_exists():
        raise SystemExit("python not found in PATH.")
    if not audio_dir.exists():
        raise SystemExit(f"Audio dir not found: {audio_dir}")
    if not daniel_img.exists():
        raise SystemExit(f"Daniel image not found: {daniel_img}")
    if not annabelle_img.exists():
        raise SystemExit(f"Annabelle image not found: {annabelle_img}")
    if intro_img and not intro_img.exists():
        raise SystemExit(f"Intro image not found: {intro_img}")
    if outro_img and not outro_img.exists():
        raise SystemExit(f"Outro image not found: {outro_img}")
    if intro_audio and not intro_audio.exists():
        raise SystemExit(f"Intro audio not found: {intro_audio}")
    if outro_audio and not outro_audio.exists():
        raise SystemExit(f"Outro audio not found: {outro_audio}")

    # Using images as provided without automatic verification/cropping.

    # Prepare dirs
    for p in [out_st_d, out_st_a, out_final, tmp_dir, audio_dir / "wav"]:
        ensure_dir(p)

    logger = Logger(verbose=args.verbose, quiet=args.quiet)

    # Gather all audio files (both daniel and annabelle)
    dan_files = sorted(audio_dir.glob("*_daniel.mp3"))
    ann_files = sorted(audio_dir.glob("*_annabelle.mp3"))
    all_audio_files = dan_files + ann_files
    
    if not all_audio_files:
        print(f"ℹ️  No *_daniel.mp3 or *_annabelle.mp3 files in {audio_dir}", flush=True)
        return

    py = py_exec()
    # ----------------------------------------------------------------------------------
    # Pre-flight: detect enhancer dependency breakage (torchvision API mismatch).
    # SadTalker enhancer stack (gfpgan/realesrgan) relies on basicsr expecting
    # torchvision.transforms.functional_tensor (removed in newer torchvision releases).
    # If import chain fails we auto-disable enhancers to avoid hard crash.
    # ----------------------------------------------------------------------------------
    enhancers_forced_off = False
    if not args.no_enhancers:
        try:
            # Do a lightweight import test in a throwaway subprocess to isolate errors.
            test_code = (
                "import importlib, json, sys;\n"
                "mods=['basicsr','gfpgan','realesrgan'];\n"
                "ok=True;\n"
                "errors={};\n"
                "import torch, torchvision;\n"
                "missing_attr=not hasattr(__import__('torchvision').transforms,'functional_tensor');\n"
                "for m in mods:\n"
                "  try: importlib.import_module(m)\n"
                "  except Exception as e: ok=False; errors[m]=str(e)\n"
                "print(json.dumps({'ok':ok,'errors':errors,'missing_attr':missing_attr}))"
            )
            out = subprocess.check_output([py, '-c', test_code], text=True)
            import json as _json
            probe = _json.loads(out)
            # Fallback condition: either import errors or functional_tensor missing AND basicsr is present (will blow up later)
            if (not probe.get('ok')) or probe.get('missing_attr'):
                enhancers_forced_off = True
        except Exception:
            # Any unexpected probe failure -> be conservative and disable enhancers.
            enhancers_forced_off = True

    if enhancers_forced_off:
        print("⚠️  Enhancer stack disabled automatically (incompatible torchvision/basicsr or missing packages).", flush=True)
        print("    -> Running without face/background enhancement. You can fix by installing compatible versions:", flush=True)
        print("       Suggested combo: torch==1.13.* / torchvision==0.14.* OR patch basicsr expecting new API.", flush=True)
        args.no_enhancers = True
    sadtalker_style = "--still" if args.style == "still" else "--pose"
    if args.no_enhancers:
        sadtalker_enh = []
        bg_enh_arg = []
    else:
        sadtalker_enh = ["--enhancer", args.enhancer] if args.enhancer != "none" else []
        bg_enh_arg = ["--background_enhancer", args.background_enhancer] if args.background_enhancer else []
    # Select encoder once
    global_video_encoder = select_video_encoder()
    logger.info(f"Selected video encoder: {global_video_encoder}")

    segment_count = 0
    annabelle_segments = 0
    skipped_segments = 0
    for audio_file in sorted(all_audio_files):
        # Determine speaker and segment info
        if audio_file.name.endswith("_daniel.mp3"):
            speaker = "daniel"
            base = str(audio_file)[:-len("_daniel.mp3")]
        elif audio_file.name.endswith("_annabelle.mp3"):
            speaker = "annabelle"
            base = str(audio_file)[:-len("_annabelle.mp3")]
        else:
            continue
            
        segname = Path(base).name
        segment_count += 1
        if speaker == "annabelle":
            annabelle_segments += 1
        logger.info(f"[{segment_count}] Segment: {segname} (speaker: {speaker})")

        # Convert main audio to WAV
        main_wav = as_wav(audio_file, audio_dir / "wav")
        
        # Create silent audio for the other speaker (same duration as main audio)
        silent_wav = audio_dir / "wav" / f"{segname}_{speaker}_silent_partner.wav"
        if not silent_wav.exists():
            # Create silent audio with same duration as main audio
            run([
                "ffmpeg", "-y",
                "-i", str(main_wav),
                "-af", "volume=0",
                "-ar", "16000", "-ac", "1",
                str(silent_wav)
            ], quiet=True)
        
        # Determine which audio goes to which speaker
        if speaker == "daniel":
            dan_wav = main_wav
            ann_wav = silent_wav
        else:  # speaker == "annabelle"
            dan_wav = silent_wav
            ann_wav = main_wav

        # Run animation engine for each side (or static if silent partner)
        dan_dir = out_st_d / segname; ensure_dir(dan_dir)
        ann_dir = out_st_a / segname; ensure_dir(ann_dir)
        dan_out = dan_dir / f"{segname}_daniel.mp4"
        ann_out = ann_dir / f"{segname}_annabelle.mp4"

        final_split = (Path(out_final) / f"{segname}_split_core.mp4")
        if args.skip_existing and dan_out.exists() and ann_out.exists() and final_split.exists():
            skipped_segments += 1
            logger.verbose_msg(f"Skip cached segment: {segname}")
            continue

        # Decide if we can shortcut with static video for silent partner
        global_enc = global_video_encoder
        if not dan_out.exists():
            if args.static_silent and dan_wav.name.endswith("_silent_partner.wav"):
                logger.verbose_msg("Daniel side is silent partner -> static image video")
                make_static_video(daniel_img, dan_wav, dan_out, fps, global_enc, logger)
            else:
                run([
                    py, "inference.py",
                    "--driven_audio", str(dan_wav),
                    "--source_image", str(daniel_img),
                    "--result_dir", str(dan_dir),
                    "--preprocess", args.preprocess,
                    sadtalker_style, *sadtalker_enh, *bg_enh_arg
                ], cwd=sadtalker_dir, quiet=args.quiet and not args.verbose, verbose=args.verbose)
                mp4s = sorted(dan_dir.glob("*.mp4"), key=lambda p: p.stat().st_mtime, reverse=True)
                if mp4s:
                    mp4s[0].rename(dan_out)

        if not ann_out.exists():
            if args.static_silent and ann_wav.name.endswith("_silent_partner.wav"):
                logger.verbose_msg("Annabelle side is silent partner -> static image video")
                make_static_video(annabelle_img, ann_wav, ann_out, fps, global_enc, logger)
            else:
                run([
                    py, "inference.py",
                    "--driven_audio", str(ann_wav),
                    "--source_image", str(annabelle_img),
                    "--result_dir", str(ann_dir),
                    "--preprocess", args.preprocess,
                    sadtalker_style, *sadtalker_enh, *bg_enh_arg
                ], cwd=sadtalker_dir, quiet=args.quiet and not args.verbose, verbose=args.verbose)
                mp4s = sorted(ann_dir.glob("*.mp4"), key=lambda p: p.stat().st_mtime, reverse=True)
                if mp4s:
                    mp4s[0].rename(ann_out)

    # Build split screen composition
        ln = loudnorm_filter(args.loudnorm)
        # Decide filter depending on whether we want double-wide output
        filter_split = build_split_filter(args.ducking)
        main_core = final_split

        # Ensure filter ends with a semicolon before appending more steps
        filter_core = filter_split if filter_split.endswith(';') else filter_split + ';'
        v_encoder = global_video_encoder
        ffmpeg_cmd = [
            "ffmpeg", "-y",
            "-i", str(dan_out), "-i", str(ann_out),
            "-filter_complex",
            (
                f"{filter_core}"
                f"[amix]{ln}[aL];"
                # For double-wide we keep the hstack size (3840x1080). For normal
                # mode the hstack is 1920x1080. Set fps in either case.
                f"[v]fps={fps}[v2]"
            ),
            "-map", "[v2]", "-map", "[aL]",
            "-c:v", v_encoder,
            *( ["-crf", "18"] if v_encoder.startswith("libx") else (["-b:v", "2M"] if v_encoder == "libopenh264" else []) ),
            "-r", str(fps),
            "-shortest",
            str(main_core)
        ]
        try:
            run(ffmpeg_cmd, quiet=True, verbose=logger.verbose)
        except Exception as e:
            logger.warn(f"Re-encode failed with encoder {v_encoder}: {e}; trying fallback encoder")
            # Fallback: nutze einen anderen Encoder, kein copy!
            fallback_encoders = ["libopenh264", "libx265", "libvpx-vp9", "mpeg4"]
            fallback_v = next((enc for enc in fallback_encoders if enc in subprocess.getoutput('ffmpeg -hide_banner -encoders')), None)
            if not fallback_v:
                raise RuntimeError("Kein alternativer Video-Encoder für Fallback gefunden!")
            logger.warn(f"Fallback encoder: {fallback_v}")
            fallback_core = [
                "ffmpeg", "-y",
                "-i", str(dan_out), "-i", str(ann_out),
                "-filter_complex",
                "[0:v]scale=960:1080:force_original_aspect_ratio=decrease,pad=960:1080:(960-iw):(1080-ih)/2:black[left];"
                "[1:v]scale=960:1080:force_original_aspect_ratio=decrease,pad=960:1080:0:(1080-ih)/2:black[right];"
                "[left][right]hstack=inputs=2[v];[0:a][1:a]amix=inputs=2[a]",
                "-map", "[v]", "-map", "[a]",
                "-c:v", fallback_v, "-c:a", "aac", "-shortest", str(main_core)
            ]
            try:
                run(fallback_core, quiet=True, verbose=logger.verbose)
            except Exception as e2:
                raise RuntimeError(f"Fallback ffmpeg failed with {fallback_v}: {e2}")

    # Core split video ready
        logger.info(f"OK {main_core}")

    if annabelle_segments == 0:
        logger.warn("No Annabelle segments detected – verify *_annabelle.mp3 files exist.")

    if segment_count == 0:
        logger.warn(f"No segments found in: {audio_dir} (expect *_daniel.mp3 or *_annabelle.mp3)")
    else:
        processed = segment_count - skipped_segments
        logger.info(f"Done: {segment_count} segment(s) (processed: {processed}, skipped: {skipped_segments}) -> {out_final}")

    # Optional: generate intro/outro cover clips
        global_enc = select_video_encoder()
        intro_clip = None
        outro_clip = None
        def _parse_duration(val: str) -> Union[float, str]:
            if isinstance(val, str) and val.lower() == 'auto':
                return 'auto'
            try:
                return float(val)
            except ValueError:
                raise SystemExit(f"Invalid duration value (expect float or 'auto'): {val}")

        intro_dur = _parse_duration(args.intro_duration)
        outro_dur = _parse_duration(args.outro_duration)

        if not args.no_intro and intro_img:
            intro_clip = out_final / "_intro.mp4"
            try:
                create_cover_clip(intro_img, intro_clip, intro_dur, args.fade, fps, global_enc, logger, audio=intro_audio)
            except Exception as e:
                logger.warn(f"Intro generation failed: {e}")
                intro_clip = None
        if not args.no_outro and outro_img:
            outro_clip = out_final / "_outro.mp4"
            try:
                create_cover_clip(outro_img, outro_clip, outro_dur, args.fade, fps, global_enc, logger, audio=outro_audio)
            except Exception as e:
                logger.warn(f"Outro generation failed: {e}")
                outro_clip = None

    # Concat all core segments + optional intro/outro into final episode
        finished_dir = out_base / "finished"
        ensure_dir(finished_dir)
        finished_file = finished_dir / f"{decade}.mp4"
        try:
            concat_final_segments(out_final, finished_file, fps, logger, intro_clip=intro_clip, outro_clip=outro_clip)
            logger.info(f"Finished video: {finished_file}")
        except Exception as e:
            logger.warn(f"Could not create finished video: {e}")


def build_arg_parser():
    p = argparse.ArgumentParser(description="MelodyMind Video Pipeline (Linux) – SadTalker only")
    p.add_argument("--decade", required=True, help="Decade folder under inputs/, e.g. 1950s, 1960s")
    group = p.add_mutually_exclusive_group()
    group.add_argument("--still", dest="style", action="store_const", const="still", help="Use still head motion (fewer movements)")
    group.add_argument("--pose", dest="style", action="store_const", const="pose", help="Use pose head motion")
    p.set_defaults(style="still")
    p.add_argument("--fps", type=int, default=25, help="Frame rate (default: 25)")
    p.add_argument("--no-enhancers", action="store_true", help="Disable all SadTalker enhancers (face/background)")

    p.add_argument("--ducking", action="store_true", help="Enable audio sidechain ducking")
    p.add_argument("--no-loudnorm", dest="loudnorm", action="store_false", help="Disable EBU R128 loudness normalization")
    # Intro / Outro Optionen
    p.add_argument("--intro-image", help="Pfad zu Intro Cover Bild (png/jpg)")
    p.add_argument("--intro-audio", help="Pfad zu Intro Musik (optional)")
    p.add_argument("--intro-duration", default="5.0", help="Intro duration seconds or 'auto' (match intro audio). Default: 5.0")
    p.add_argument("--outro-image", help="Pfad zu Outro Cover Bild (png/jpg)")
    p.add_argument("--outro-audio", help="Pfad zu Outro Musik (optional)")
    p.add_argument("--outro-duration", default="5.0", help="Outro duration seconds or 'auto' (match outro audio). Default: 5.0")
    p.add_argument("--fade", type=float, default=1.0, help="Fade duration for intro/outro video & audio (seconds, default: 1.0)")
    p.add_argument("--no-intro", action="store_true", help="Intro deaktivieren selbst wenn Pfad angegeben")
    p.add_argument("--no-outro", action="store_true", help="Outro deaktivieren selbst wenn Pfad angegeben")
    p.add_argument("--no-static-silent", dest="static_silent", action="store_false", help="Deaktiviere statische Videos für stumme Partner (immer SadTalker ausführen)")

    p.add_argument("--daniel-image", help="Override path to Daniel's portrait (png/jpg)")
    p.add_argument("--annabelle-image", help="Override path to Annabelle's portrait (png/jpg)")
    # --intro/--outro entfernt
    p.add_argument("--audio-dir", help="Override audio dir for the given decade")
    p.add_argument("--sadtalker", default="./SadTalker", help="Path to SadTalker repo (default: ./SadTalker)")
    p.add_argument("--preprocess", default="full", choices=["crop", "resize", "full"], help="SadTalker preprocess mode (crop, resize, full)")
    p.add_argument("--enhancer", default="gfpgan", choices=["gfpgan", "RestoreFormer", "none"], help="Face enhancer (default: gfpgan or RestoreFormer)")
    p.add_argument("--background-enhancer", dest="background_enhancer", choices=["realesrgan", "none"], default=None, help="Background enhancer for full image (requires realesrgan)")
    p.add_argument("--quiet", action="store_true", help="Minimal output (errors + essential info only)")
    p.add_argument("--verbose", action="store_true", help="Verbose output (echo commands & ffmpeg details)")
    p.add_argument("--skip-existing", action="store_true", help="Skip segment if cached outputs exist")

    p.set_defaults(loudnorm=True, static_silent=True)
    return p




def concat_final_segments(final_dir: Path, out_file: Path, fps: int, logger: Logger, intro_clip: Optional[Path] = None, outro_clip: Optional[Path] = None):
    """Concatenate all segment MP4s in final_dir into a single MP4 at out_file.

    Uses a robust re-encode concat method (makes a temporary list file).
    """
    segs = sorted(final_dir.glob("*_split_core.mp4"))
    ordered: list[Path] = []
    if intro_clip and intro_clip.exists():
        ordered.append(intro_clip)
    ordered.extend(segs)
    if outro_clip and outro_clip.exists():
        ordered.append(outro_clip)
    if not ordered:
        raise RuntimeError(f"No segment files (and no intro/outro) found in {final_dir}")
    if not segs:
        raise RuntimeError(f"No segment files found in {final_dir}")

    # Create a file list for ffmpeg concat demuxer
    list_file = final_dir / "_ffconcat_list.txt"
    with open(list_file, "w", encoding="utf-8") as f:
        for s in ordered:
            f.write(f"file '{s.as_posix()}'\n")

    # Use ffmpeg concat demuxer with a re-encode to ensure compatibility
    cmd = [
        "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(list_file),
        "-c:v", select_video_encoder(),
        *( ["-crf", "18"] if select_video_encoder().startswith("libx") else [] ),
        "-c:a", "aac", "-b:a", "192k",
        str(out_file)
    ]
    run(cmd, quiet=True, verbose=logger.verbose)
    try:
        list_file.unlink()
    except Exception:
        pass


def main():
    args = build_arg_parser().parse_args()
    try:
        process_decade(args)
    except Exception as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
