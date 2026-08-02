#!/usr/bin/env python3
"""Transcribe B2 audio and compare it with the expected French text."""

from __future__ import annotations

import argparse
import csv
import difflib
import json
import re
import unicodedata
from pathlib import Path

from faster_whisper import WhisperModel


def normalize(text: str) -> list[str]:
    text = unicodedata.normalize("NFKD", text.lower())
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = text.replace("’", "'").replace("œ", "oe")
    return re.findall(r"[a-z]+", text)


def word_changes(expected: list[str], actual: list[str]) -> tuple[list[str], list[str]]:
    missing: list[str] = []
    extra: list[str] = []
    matcher = difflib.SequenceMatcher(a=expected, b=actual, autojunk=False)
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag in {"delete", "replace"}:
            missing.extend(expected[i1:i2])
        if tag in {"insert", "replace"}:
            extra.extend(actual[j1:j2])
    return missing, extra


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="small")
    parser.add_argument("--manifest", default="audit/b2_expected_manifest.json")
    parser.add_argument("--output", default="audit-results")
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    manifest = json.loads((root / args.manifest).read_text(encoding="utf-8"))
    output = root / args.output
    output.mkdir(parents=True, exist_ok=True)
    model = WhisperModel(args.model, device="cpu", compute_type="int8")
    rows: list[dict[str, object]] = []

    for number, item in enumerate(manifest, 1):
        audio = root / item["repo_path"]
        expected_text = item["expected"]
        print(f"[{number}/{len(manifest)}] {audio}", flush=True)
        segments, info = model.transcribe(
            str(audio), language="fr", beam_size=5, vad_filter=True,
            condition_on_previous_text=False,
        )
        actual_text = " ".join(segment.text.strip() for segment in segments).strip()
        expected_words = normalize(expected_text)
        actual_words = normalize(actual_text)
        missing, extra = word_changes(expected_words, actual_words)
        distance = sum(
            max(i2 - i1, j2 - j1)
            for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(
                a=expected_words, b=actual_words, autojunk=False
            ).get_opcodes()
            if tag != "equal"
        )
        wer = distance / max(1, len(expected_words))
        if not missing and not extra:
            status = "PASS"
        elif wer <= 0.08 and len(missing) <= 1 and len(extra) <= 1:
            status = "REVIEW"
        else:
            status = "SUSPECT"
        rows.append({
            "status": status,
            "source": item["source"],
            "repo_path": item["repo_path"],
            "wer": round(wer, 4),
            "language_probability": round(float(info.language_probability), 4),
            "missing_words": " ".join(missing),
            "extra_words": " ".join(extra),
            "expected": expected_text,
            "transcript": actual_text,
        })

    rows.sort(key=lambda row: (row["status"] == "PASS", -float(row["wer"])))
    fields = list(rows[0])
    with (output / "b2_audio_audit.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    (output / "b2_audio_audit.json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    counts = {status: sum(row["status"] == status for row in rows) for status in ("PASS", "REVIEW", "SUSPECT")}
    report = [
        "# B2 audio audit",
        "",
        f"- Files checked: {len(rows)}",
        f"- Pass: {counts['PASS']}",
        f"- Review: {counts['REVIEW']}",
        f"- Suspect: {counts['SUSPECT']}",
        "",
        "## Suspect and review files",
        "",
        "| Status | Source | WER | Missing | Extra | File |",
        "|---|---|---:|---|---|---|",
    ]
    for row in rows:
        if row["status"] == "PASS":
            continue
        safe = lambda value: str(value).replace("|", "\\|")
        report.append(
            f"| {row['status']} | {safe(row['source'])} | {row['wer']:.1%} | "
            f"{safe(row['missing_words'])} | {safe(row['extra_words'])} | `{row['repo_path']}` |"
        )
    (output / "README.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    print(json.dumps(counts), flush=True)


if __name__ == "__main__":
    main()
