from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
import unicodedata
from html import unescape
from pathlib import Path
from urllib import request, error


ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / "index.html"
OUT = ROOT / "audio"
CONFIG = ROOT / "tts_config.json"

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def js_string_to_text(value: str) -> str:
    return json.loads(f'"{value}"')


def extract_templates() -> list[dict[str, str]]:
    html = HTML.read_text(encoding="utf-8")
    blocks = re.findall(r"\{\s*type:\s*\"(.*?)\".*?title:\s*\"((?:[^\"\\]|\\.)*)\".*?fr:\s*\"((?:[^\"\\]|\\.)*)\"", html, re.S)
    templates = []
    for type_, title, fr in blocks:
        templates.append(
            {
                "type": js_string_to_text(type_),
                "title": js_string_to_text(title),
                "fr": js_string_to_text(fr),
            }
        )
    return templates


def split_french(text: str) -> list[str]:
    lines = []
    for part in re.split(r"\n+", text):
        part = part.strip()
        if not part:
            continue
        chunks = re.findall(r"[^.!?。！？]+[.!?。！？]?", part)
        lines.extend(chunk.strip() for chunk in chunks if chunk.strip())
    return lines


def safe_name(text: str, limit: int = 64) -> str:
    text = unicodedata.normalize("NFD", unescape(text))
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    return (text[:limit].strip("-") or "audio")


def legacy_name(text: str, limit: int = 64) -> str:
    legacy = text.encode("utf-8").decode("latin-1")
    return safe_name(legacy, limit)


def make_content(fr_lines) -> str:
    return "\n\n".join(fr_lines)


def normalize_key(text: str) -> str:
    normalized = unicodedata.normalize("NFD", text.lower())
    return "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")


def has_any(key: str, terms: list[str]) -> bool:
    return any(normalize_key(term) in key for term in terms)


_B2_FINAL_DRAFTS: dict[str, dict[str, list[str]]] | None = None


def load_b2_final_drafts() -> dict[str, dict[str, list[str]]]:
    global _B2_FINAL_DRAFTS
    if _B2_FINAL_DRAFTS is not None:
        return _B2_FINAL_DRAFTS
    js = r"""
const fs = require('fs');
const text = fs.readFileSync('index.html', 'utf8');
const start = text.indexOf('const b2FinalDrafts =');
const end = text.indexOf(';\n\nfunction lines', start);
if (start < 0 || end < 0) throw new Error('b2FinalDrafts not found');
const source = text.slice(start, end).replace('const b2FinalDrafts =', 'globalThis.b2FinalDrafts =');
eval(source);
process.stdout.write(JSON.stringify(globalThis.b2FinalDrafts));
"""
    try:
        result = subprocess.run(
            ["node", "-e", js],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        _B2_FINAL_DRAFTS = json.loads(result.stdout)
    except Exception:
        _B2_FINAL_DRAFTS = {}
    return _B2_FINAL_DRAFTS


def manual_variant_for(item: dict[str, str], level: str) -> str:
    if level == "c1":
        return item["fr"]
    if level == "b2":
        draft = load_b2_final_drafts().get(item["title"])
        if draft:
            return make_content(draft["fr"])
    title = normalize_key(f"{item['title']} {item.get('theme', '')}")
    type_ = item["type"]
    if level == "a2":
        if type_ == "tache1":
            if has_any(title, ["travail", "etudes"]):
                return make_content([
                    "J'ai étudié et travaillé dans plusieurs domaines.",
                    "J'aime apprendre de nouvelles choses.",
                    "Au Canada, je voudrais avoir un projet plus stable.",
                    "Pour cela, j'améliore mon français petit à petit.",
                ])
            if has_any(title, ["ville", "logement", "quartier"]):
                return make_content([
                    "J'habite dans un quartier assez calme.",
                    "J'aime cet endroit parce qu'il est pratique.",
                    "Il y a des transports, des magasins et des services.",
                    "Pour moi, c'est important d'avoir une vie simple et équilibrée.",
                ])
            if has_any(title, ["loisirs", "personnalite"]):
                return make_content([
                    "Pendant mon temps libre, j'aime apprendre le français.",
                    "J'aime aussi marcher et écouter des vidéos en français.",
                    "Ces activités m'aident à me concentrer.",
                    "Elles me permettent de progresser régulièrement.",
                ])
            if has_any(title, ["canada", "francais"]):
                return make_content([
                    "J'apprends le français parce que je vis au Canada.",
                    "Pour moi, c'est utile dans la vie quotidienne.",
                    "Le français m'aide à mieux comprendre les autres.",
                    "Je veux parler avec plus de confiance.",
                ])
            return make_content([
                "Bonjour, je m'appelle Patrick.",
                "Je viens de Chine et je vis maintenant au Canada.",
                "J'apprends le français pour mieux communiquer.",
                "Mon objectif est de parler plus clairement et plus naturellement.",
            ])
        if type_ in {"tache2", "questions"}:
            return make_content([
                "Bonjour, je voudrais avoir quelques informations.",
                "Pouvez-vous m'expliquer comment cela se passe ?",
                "Combien cela coûte-t-il et faut-il réserver à l'avance ?",
                "Merci, c'est clair. Je vais réfléchir et je vous recontacterai.",
            ])
        if type_ in {"tache3", "variations"}:
            return make_content([
                "À mon avis, c'est une question importante.",
                "Il y a des avantages, mais aussi des limites.",
                "Donc, je pense qu'il faut trouver un équilibre.",
            ])
        return make_content([
            "D'abord, je présente l'idée principale.",
            "Ensuite, je donne un exemple ou une raison.",
            "Enfin, je termine avec une conclusion simple.",
        ])

    if type_ == "tache1":
        if has_any(title, ["travail", "etudes"]):
            return make_content([
                "Mon parcours est assez varié, car j'ai toujours essayé d'apprendre de nouvelles compétences.",
                "Dans le travail, j'aime surtout résoudre des problèmes concrets et voir mes progrès.",
                "À moyen terme, je voudrais construire un projet plus stable au Canada.",
                "C'est aussi pour cette raison que je continue à améliorer mon français.",
            ])
        if has_any(title, ["ville", "logement", "quartier"]):
            return make_content([
                "J'habite dans un environnement plutôt calme, ce qui me convient bien.",
                "J'apprécie une ville quand elle est à la fois pratique, sûre et agréable à vivre.",
                "Pour moi, un bon quartier doit faciliter le travail, les déplacements et le repos.",
                "C'est important de trouver un équilibre entre efficacité et qualité de vie.",
            ])
        if has_any(title, ["loisirs", "personnalite"]):
            return make_content([
                "Pendant mon temps libre, je préfère les activités qui me permettent de progresser régulièrement.",
                "Par exemple, apprendre le français demande de la mémoire, de l'écoute et de la discipline.",
                "J'aime aussi marcher ou écouter des contenus en français.",
                "Ces habitudes m'aident à garder un rythme de vie plus équilibré.",
            ])
        if has_any(title, ["canada", "francais"]):
            return make_content([
                "J'apprends le français parce que je veux mieux communiquer dans la société où je vis.",
                "Au Canada, le français est une compétence utile dans la vie quotidienne et professionnelle.",
                "Il permet aussi de mieux comprendre une autre culture.",
                "Même si c'est parfois difficile, chaque progrès me donne plus de confiance.",
            ])
        return make_content([
            "Bonjour, je m'appelle Patrick et je viens de Chine.",
            "Je vis actuellement au Canada, où j'essaie de m'adapter progressivement.",
            "Sur le plan personnel et professionnel, je m'intéresse aux domaines qui exigent de bonnes compétences en communication et un vrai sens de l'organisation.",
            "Aujourd'hui, mon objectif est de parler français avec plus de clarté, de fluidité et de confiance.",
        ])
    if type_ == "tache2":
        if has_any(title, ["logement", "合租", "租房"]):
            return make_content([
                "Pour commencer, pourriez-vous me décrire le logement de manière concrète ?",
                "J'aimerais connaître la superficie, l'état général et les meubles disponibles.",
                "Qu'est-ce qui est inclus dans le loyer : chauffage, électricité et Internet ?",
                "Y a-t-il des règles particulières concernant le bruit, les invités ou les espaces communs ?",
            ])
        if has_any(title, ["activite", "cours", "课程", "协会", "文化"]):
            return make_content([
                "Avant de m'inscrire, j'aimerais comprendre le déroulement de l'activité.",
                "À quel public s'adresse-t-elle et quel niveau faut-il avoir ?",
                "Le programme est-il libre ou structuré avec des objectifs précis ?",
                "Est-il possible de faire une séance d'essai avant de s'engager ?",
            ])
        if has_any(title, ["voyage", "transport", "交通", "旅游", "租车"]):
            return make_content([
                "Pour organiser ce déplacement, pourriez-vous m'indiquer les options les plus pratiques ?",
                "Je voudrais comparer le prix, la durée du trajet et le niveau de confort.",
                "Y a-t-il des documents, une assurance ou des conditions d'annulation à prévoir ?",
                "Quelle option me conseilleriez-vous si mon budget est limité ?",
            ])
        return make_content([
            "Bonjour, merci de prendre un moment pour me renseigner.",
            "J'aimerais poser quelques questions précises avant de prendre ma décision.",
            "Pourriez-vous m'expliquer comment cela se passe en pratique ?",
            "Je voudrais aussi connaître le prix, les horaires et les conditions importantes.",
            "Merci, vos explications m'aident à y voir plus clair.",
        ])
    if type_ == "tache3":
        if has_any(title, ["technologie", "numerique", "科技", "internet", "ai"]):
            return make_content([
                "La technologie apporte beaucoup d'avantages, car elle facilite l'accès à l'information.",
                "Elle permet aussi de gagner du temps et de communiquer plus facilement.",
                "Cependant, elle peut réduire l'attention et créer une dépendance.",
                "À mon avis, le plus important est d'apprendre à l'utiliser comme un outil, sans perdre son esprit critique.",
            ])
        if has_any(title, ["ecole", "education", "学校", "教育"]):
            return make_content([
                "L'école joue un rôle essentiel, car elle donne des connaissances et des méthodes.",
                "Elle peut aussi réduire certaines inégalités de départ.",
                "Mais elle ne peut pas tout corriger seule.",
                "Il faut donc trouver un équilibre entre les résultats scolaires, la confiance et l'esprit critique.",
            ])
        return make_content([
            "À mon avis, cette question est importante et elle mérite une réponse nuancée.",
            "D'un côté, cette idée peut apporter des avantages concrets.",
            "D'un autre côté, elle peut aussi créer des difficultés si elle est mal appliquée.",
            "Par exemple, tout dépend du contexte et des personnes concernées.",
            "Je pense donc qu'il faut chercher un équilibre plutôt qu'une réponse trop simple.",
        ])
    if type_ == "questions":
        return make_content([
            "Pourriez-vous me dire comment cela se déroule concrètement ?",
            "Quels sont les horaires disponibles et faut-il réserver à l'avance ?",
            "Combien cela coûte-t-il au total ?",
            "Y a-t-il des frais supplémentaires ou des documents à prévoir ?",
            "Puis-je modifier ou annuler si mon emploi du temps change ?",
        ])
    if type_ == "variations":
        return make_content([
            "Cette idée peut être utile, mais elle a aussi des limites.",
            "À mon avis, il faut regarder les conditions concrètes.",
            "Par exemple, elle ne fonctionne pas de la même manière pour tout le monde.",
            "C'est pourquoi je préfère une solution équilibrée et progressive.",
        ])
    return make_content([
        "Pour nuancer, on peut dire que cela dit, il faut aussi reconnaître une limite.",
        "Pour argumenter, ce qui est important, c'est de donner un exemple clair.",
        "Pour conclure, en résumé, il faut trouver un équilibre.",
    ])


def choose_level_sentences(type_: str, fr_lines: list[str], target_count: int) -> list[tuple[int, str]]:
    if type_ not in {"tache3", "variations"}:
        return list(enumerate(fr_lines[:target_count]))
    first = list(enumerate(fr_lines[: max(target_count - 1, 0)]))
    last_index = len(fr_lines) - 1
    if fr_lines and (not first or last_index > first[-1][0]):
        first.append((last_index, fr_lines[last_index]))
    return first[:target_count]


def trim_complex_sentence(text: str, max_words: int) -> str:
    cleaned = re.sub(r"\s+", " ", text).strip()
    hard_stop = re.search(r"[;:]", cleaned)
    if hard_stop and hard_stop.start() > 48:
        cleaned = cleaned[: hard_stop.start()]
    comma_parts = re.split(r",\s+", cleaned)
    if len(comma_parts) > 2:
        cleaned = ", ".join(comma_parts[:2])
    words = cleaned.split()
    if len(words) > max_words:
        cleaned = " ".join(words[:max_words])
    return re.sub(r"\s+([,.!?;:])", r"\1", cleaned).strip()


def ensure_sentence_end(text: str) -> str:
    if not text:
        return ""
    return text if re.search(r"[.!?]$", text) else f"{text}."


def simplify_a2(line: str, type_: str) -> str:
    replacements = [
        (r"À mon sens|À mes yeux|Selon moi", "À mon avis"),
        (r"Il me semble indispensable de", "Je pense qu'il faut"),
        (r"ne devrait pas être confondue? avec", "n'est pas la même chose que"),
        (r"de manière assez concrète", "concrètement"),
        (r"le déroulement concret de", "comment se passe"),
        (r"éventuels frais supplémentaires", "frais en plus"),
        (r"conditions à respecter", "conditions importantes"),
        (r"une réponse nuancée", "une réponse simple mais équilibrée"),
        (r"l'enjeu n'est pas seulement de", "le plus important n'est pas seulement de"),
        (r"à condition de ne pas", "mais il ne faut pas"),
        (r"dans la mesure où", "parce que"),
        (r"toutefois", "mais"),
        (r"cependant", "mais"),
        (
            r"qui exigent à la fois d'excellentes compétences en communication, un sens de l'organisation et une grande capacité d'adaptation",
            "qui demandent de bien communiquer tout en sachant s'organiser et s'adapter",
        ),
        (
            r"m'exprimer avec plus de précision, de fluidité et de spontanéité",
            "m'exprimer avec plus de précision et plus de spontanéité",
        ),
        (
            r"qui demandent à la fois de la communication, de l'organisation et une bonne capacité d'adaptation",
            "qui demandent de communiquer tout en sachant s'organiser et s'adapter",
        ),
        (
            r"qui demandent à la fois de la communication$",
            "qui demandent de communiquer tout en sachant s'organiser et s'adapter",
        ),
    ]
    text = line
    for pattern, repl in replacements:
        text = re.sub(pattern, repl, text, flags=re.I)
    max_words = 24 if type_ in {"tache3", "variations"} else 20
    return ensure_sentence_end(trim_complex_sentence(text, max_words))


def simplify_b2(line: str, type_: str) -> str:
    replacements = [
        (r"À mon sens|À mes yeux", "À mon avis"),
        (r"Il me semble indispensable de", "Je pense qu'il est important de"),
        (r"ne devrait pas être confondue? avec", "ne doit pas être confondue avec"),
        (r"de manière assez concrète", "de manière concrète"),
        (r"éventuels frais supplémentaires", "frais supplémentaires"),
        (r"cela étant dit", "cela dit"),
        (
            r"qui exigent à la fois d'excellentes compétences en communication, un sens de l'organisation et une grande capacité d'adaptation",
            "qui demandent de bien communiquer tout en sachant s'organiser et s'adapter",
        ),
        (
            r"m'exprimer avec plus de précision, de fluidité et de spontanéité",
            "m'exprimer avec plus de précision ainsi qu'avec davantage de fluidité et de spontanéité",
        ),
        (
            r"qui demandent à la fois de la communication, de l'organisation et une bonne capacité d'adaptation",
            "qui demandent de communiquer tout en sachant s'organiser et s'adapter",
        ),
        (
            r"qui demandent à la fois de la communication$",
            "qui demandent de communiquer tout en sachant s'organiser et s'adapter",
        ),
    ]
    text = line
    for pattern, repl in replacements:
        text = re.sub(pattern, repl, text, flags=re.I)
    max_words = 34 if type_ in {"tache3", "variations"} else 30
    return ensure_sentence_end(trim_complex_sentence(text, max_words))


def variant_for(item: dict[str, str], level: str) -> str:
    return manual_variant_for(item, level)


def load_config() -> dict[str, str]:
    if CONFIG.exists():
        return json.loads(CONFIG.read_text(encoding="utf-8"))
    sample = {
        "provider": "elevenlabs",
        "api_key": "PASTE_YOUR_ELEVENLABS_API_KEY_HERE",
        "voice_id": "PASTE_YOUR_VOICE_ID_HERE",
        "speed": 0.82,
    }
    CONFIG.write_text(json.dumps(sample, ensure_ascii=False, indent=2), encoding="utf-8")
    raise SystemExit(f"Created {CONFIG}. Fill in api_key and voice_id, then run again.")


def elevenlabs_tts(text: str, config: dict[str, str]) -> bytes:
    voice_id = str(config["voice_id"]).strip()
    api_key = str(config["api_key"]).strip()
    speed = float(config.get("speed", 0.82))
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}?output_format=mp3_44100_128"
    payload = json.dumps(
        {
            "text": text,
            "model_id": "eleven_multilingual_v2",
            "language_code": "fr",
            "voice_settings": {
                "stability": 0.62,
                "similarity_boost": 0.78,
                "style": 0.12,
                "use_speaker_boost": True,
                "speed": speed,
            },
        }
    ).encode("utf-8")
    req = request.Request(
        url,
        data=payload,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "xi-api-key": api_key,
        },
    )
    last_error: Exception | None = None
    for attempt in range(1, 4):
        try:
            with request.urlopen(req, timeout=90) as response:
                return response.read()
        except error.HTTPError as exc:
            details = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"ElevenLabs error {exc.code}: {details}") from exc
        except Exception as exc:
            last_error = exc
            if attempt < 3:
                time.sleep(2.5 * attempt)
    raise RuntimeError(f"ElevenLabs request failed after 3 attempts: {last_error}") from last_error


def main() -> None:
    parser = argparse.ArgumentParser(description="Download TCF sentence-level TTS mp3 files.")
    parser.add_argument("--types", nargs="*", help="Only download selected types, e.g. tache1 questions variations")
    parser.add_argument("--level", choices=["a2", "b2", "c1", "all"], default="c1", help="Audio level to download")
    parser.add_argument("--limit", type=int, help="Limit number of sentences for testing")
    parser.add_argument("--overwrite", action="store_true", help="Regenerate files that already exist")
    parser.add_argument("--dry-run", action="store_true", help="List planned files without calling the TTS API")
    args = parser.parse_args()

    config = load_config()
    if "PASTE_" in str(config.get("api_key", "")) or "PASTE_" in str(config.get("voice_id", "")):
        raise SystemExit(f"Fill in api_key and voice_id in {CONFIG}.")

    tasks = []
    levels = ["a2", "b2", "c1"] if args.level == "all" else [args.level]
    for level in levels:
        level_out = OUT if level == "c1" else OUT / level
        level_out.mkdir(parents=True, exist_ok=True)
        for card_index, item in enumerate(extract_templates(), start=1):
            if args.types and item["type"] not in args.types:
                continue
            card_slug = legacy_name(item["title"])
            for sentence_index, sentence in enumerate(split_french(variant_for(item, level)), start=1):
                sentence_slug = legacy_name(sentence) if level == "c1" else safe_name(sentence)
                file_name = f"{item['type']}-{card_index:02d}-{card_slug}-{sentence_index:02d}-{sentence_slug}.mp3"
                tasks.append((sentence, level_out / file_name))

    if args.limit:
        tasks = tasks[: args.limit]

    print(f"Ready: {len(tasks)} sentence files -> {OUT}")
    if args.dry_run:
        for index, (_, path) in enumerate(tasks, start=1):
            print(f"[{index}/{len(tasks)}] plan {path}")
        return
    for index, (sentence, path) in enumerate(tasks, start=1):
        if path.exists() and not args.overwrite:
            print(f"[{index}/{len(tasks)}] skip {path.name}")
            continue
        print(f"[{index}/{len(tasks)}] download {path.name}")
        path.write_bytes(elevenlabs_tts(sentence, config))
        time.sleep(0.45)


if __name__ == "__main__":
    main()
