from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "vendor"))
sys.path.insert(0, r"C:\tmp\tcf_ffmpeg_vendor")

import download_tts as tts


ROOT = Path(__file__).resolve().parents[1]


def current_audio_tasks(level: str = "b2") -> list[Path]:
    out = tts.OUT if level == "c1" else tts.OUT / level
    paths: list[Path] = []
    for card_index, item in enumerate(tts.extract_templates(), start=1):
      card_slug = tts.legacy_name(item["title"])
      for sentence_index, sentence in enumerate(tts.split_french(tts.variant_for(item, level)), start=1):
          sentence_slug = tts.legacy_name(sentence) if level == "c1" else tts.safe_name(sentence)
          file_name = f"{item['type']}-{card_index:02d}-{card_slug}-{sentence_index:02d}-{sentence_slug}.mp3"
          paths.append(out / file_name)
    return paths


def ffmpeg_path() -> str:
    npm_ffmpeg = Path.home() / "node_modules" / "@ffmpeg-installer" / "win32-x64" / "ffmpeg.exe"
    if npm_ffmpeg.exists():
        return str(npm_ffmpeg)
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception as exc:
        raise SystemExit(
            "ffmpeg not found. Install it with: python -m pip install imageio-ffmpeg -t .\\vendor"
        ) from exc


def parse_loudnorm_json(stderr: str) -> dict[str, str]:
    match = re.search(r"\{\s*\"input_i\"[\s\S]*?\}", stderr)
    if not match:
        raise RuntimeError("Could not parse loudnorm analysis output.")
    return json.loads(match.group(0))


def normalize_one(ffmpeg: str, path: Path, target_i: float, target_tp: float, target_lra: float) -> None:
    if not path.exists():
        raise FileNotFoundError(path)
    analyze_filter = f"loudnorm=I={target_i}:TP={target_tp}:LRA={target_lra}:print_format=json"
    analysis = subprocess.run(
        [ffmpeg, "-hide_banner", "-nostats", "-i", str(path), "-af", analyze_filter, "-f", "null", "NUL"],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
    )
    if analysis.returncode != 0:
        raise RuntimeError(analysis.stderr[-1200:])
    measured = parse_loudnorm_json(analysis.stderr)
    normalize_filter = (
        f"loudnorm=I={target_i}:TP={target_tp}:LRA={target_lra}:"
        f"measured_I={measured['input_i']}:"
        f"measured_TP={measured['input_tp']}:"
        f"measured_LRA={measured['input_lra']}:"
        f"measured_thresh={measured['input_thresh']}:"
        f"offset={measured['target_offset']}:"
        "linear=true:print_format=summary"
    )
    tmp = path.with_suffix(".normalized.mp3")
    result = subprocess.run(
        [
            ffmpeg,
            "-hide_banner",
            "-nostats",
            "-y",
            "-i",
            str(path),
            "-af",
            normalize_filter,
            "-ar",
            "44100",
            "-b:a",
            "128k",
            str(tmp),
        ],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
    )
    if result.returncode != 0:
        if tmp.exists():
            tmp.unlink()
        raise RuntimeError(result.stderr[-1200:])
    tmp.replace(path)


def write_pathspec(paths: list[Path], output: Path) -> None:
    lines = ["index.html", "service-worker.js", "scripts/audio_standard.py"]
    lines.extend(str(path.relative_to(ROOT)).replace("\\", "/") for path in paths)
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Standardize current TCF audio loudness with ffmpeg loudnorm.")
    parser.add_argument("--level", choices=["b2", "a2", "c1"], default="b2")
    parser.add_argument("--target-i", type=float, default=-18.0, help="Integrated loudness target in LUFS.")
    parser.add_argument("--target-tp", type=float, default=-1.5, help="True peak target.")
    parser.add_argument("--target-lra", type=float, default=11.0, help="Loudness range target.")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--write-pathspec", type=Path)
    args = parser.parse_args()

    paths = current_audio_tasks(args.level)
    if args.limit:
        paths = paths[: args.limit]
    missing = [path for path in paths if not path.exists()]
    if missing:
        preview = "\n".join(str(path) for path in missing[:12])
        raise SystemExit(f"Missing {len(missing)} audio files. Generate TTS first.\n{preview}")
    if args.write_pathspec:
        write_pathspec(paths, args.write_pathspec)
    print(f"Ready: {len(paths)} {args.level.upper()} audio files")
    if args.dry_run:
        for path in paths:
            print(path)
        return

    ffmpeg = ffmpeg_path()
    for index, path in enumerate(paths, start=1):
        print(f"[{index}/{len(paths)}] loudnorm {path.name}")
        normalize_one(ffmpeg, path, args.target_i, args.target_tp, args.target_lra)


if __name__ == "__main__":
    main()
