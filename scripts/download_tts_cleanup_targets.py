from __future__ import annotations

import time
from pathlib import Path

import download_tts as base


TARGETS = [
    ("c1", 6, 2),
    ("c1", 9, 1),
    ("c1", 10, 2),
    ("c1", 11, 1),
    ("c1", 15, 3),
    ("c1", 15, 4),
    ("c1", 16, 2),
    ("c1", 17, 3),
    ("c1", 18, 1),
    ("c1", 21, 2),
    ("c1", 37, 1),
    ("c1", 37, 2),
    ("c1", 37, 3),
    ("b2", 6, 2),
    ("b2", 15, 3),
    ("b2", 16, 2),
    ("b2", 37, 1),
    ("b2", 37, 2),
    ("b2", 37, 3),
    ("a2", 37, 1),
    ("a2", 37, 2),
    ("a2", 37, 3),
]


def audio_path(item: dict[str, str], level: str, card_index: int, sentence_index: int, sentence: str) -> Path:
    level_out = base.OUT if level == "c1" else base.OUT / level
    level_out.mkdir(parents=True, exist_ok=True)
    card_slug = base.legacy_name(item["title"])
    sentence_slug = base.legacy_name(sentence) if level == "c1" else base.safe_name(sentence)
    file_name = f"{item['type']}-{card_index:02d}-{card_slug}-{sentence_index:02d}-{sentence_slug}.mp3"
    return level_out / file_name


def main() -> None:
    config = base.load_config()
    templates = base.extract_templates()
    tasks = []
    for level, card_index, sentence_index in TARGETS:
      item = templates[card_index - 1]
      sentences = base.split_french(base.variant_for(item, level))
      sentence = sentences[sentence_index - 1]
      tasks.append((level, card_index, sentence_index, item, sentence, audio_path(item, level, card_index, sentence_index, sentence)))

    print(f"Ready: {len(tasks)} cleaned sentence files")
    for index, (level, card_index, sentence_index, item, sentence, path) in enumerate(tasks, start=1):
        print(f"[{index}/{len(tasks)}] {level} card {card_index:02d} sentence {sentence_index:02d}: {path.name}")
        path.write_bytes(base.elevenlabs_tts(sentence, config))
        time.sleep(0.45)


if __name__ == "__main__":
    main()
