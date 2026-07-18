"""Generate a grounded pitch SlideDeck with Azure OpenAI Structured Outputs."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

DEFAULT_API_VERSION = "2024-10-21"
SLIDE_IDS = ("title", "problem", "solution", "demo", "architecture", "next")
SUPPORTED_LANGS = frozenset({"ja", "en"})


def _slide_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "id": {"type": "string", "enum": list(SLIDE_IDS)},
            "heading_ja": {"type": "string"},
            "heading_en": {"type": "string"},
            "bullets_ja": {"type": "array", "items": {"type": "string"}, "maxItems": 4},
            "bullets_en": {"type": "array", "items": {"type": "string"}, "maxItems": 4},
            "image": {"anyOf": [{"type": "string"}, {"type": "null"}]},
            "arch_text": {"anyOf": [{"type": "string"}, {"type": "null"}]},
        },
        "required": ["id", "heading_ja", "heading_en", "bullets_ja", "bullets_en", "image", "arch_text"],
    }


SLIDE_DECK_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "title": {"type": "string"},
        "slides": {
            "type": "array",
            "items": _slide_schema(),
            "minItems": 6,
            "maxItems": 6,
        },
        "script_ja": {"type": "string"},
        "script_en": {"type": "string"},
    },
    "required": ["title", "slides", "script_ja", "script_en"],
}

SYSTEM_PROMPT = """You create a concise six-slide hackathon pitch deck.
Use only facts and feature or capability names explicitly present in the supplied
context. Treat the context as a closed world: every substantive claim must be a
direct restatement or close translation of text in the repository name, README,
commit subjects, source excerpts, or screenshot paths. Never infer, embellish, or
name an absent feature. Do not invent benefits, motivations, user pain, event
names, dates, future work, or quality claims. Do not describe bilingual output as
translation unless the context explicitly says translation. Return exactly these
slides in order: title, problem, solution, demo, architecture, next. Keep Japanese
script_ja at no more than 300 characters and English script_en at no more than 90
words. Each slide has at most four bullets per language. For an unrequested
language, return empty headings, empty bullet arrays, and an empty script. Use a
context screenshot path only on the demo slide; when none exists, set image to
null and provide a compact text architecture diagram in the demo slide's
arch_text. Set arch_text to null on every other slide. If the context does not
explicitly support a problem or next-step bullet, return an empty bullet array.
Scripts must summarize only the same explicit repository facts used on the slides.
"""


def _validate_deck(deck: Any, langs: list[str], context: dict) -> dict[str, Any]:
    if not isinstance(deck, dict) or set(deck) != {"title", "slides", "script_ja", "script_en"}:
        raise ValueError("response is not a SlideDeck object")
    slides = deck.get("slides")
    if not isinstance(slides, list) or len(slides) != 6:
        raise ValueError("SlideDeck must contain exactly six slides")
    if [slide.get("id") if isinstance(slide, dict) else None for slide in slides] != list(SLIDE_IDS):
        raise ValueError("SlideDeck slide ids are invalid or out of order")

    requested = set(langs)
    required = {"id", "heading_ja", "heading_en", "bullets_ja", "bullets_en", "image", "arch_text"}
    screenshot_paths = set(context.get("screenshots", []))
    for index, slide in enumerate(slides):
        if set(slide) != required:
            raise ValueError(f"slide {slide.get('id', '<unknown>')} has invalid fields")
        for lang in SUPPORTED_LANGS:
            heading = slide[f"heading_{lang}"]
            bullets = slide[f"bullets_{lang}"]
            if not isinstance(heading, str) or not isinstance(bullets, list):
                raise ValueError(f"slide {slide['id']} has invalid {lang} content")
            if len(bullets) > 4 or any(not isinstance(item, str) for item in bullets):
                raise ValueError(f"slide {slide['id']} has invalid {lang} bullets")
            if lang not in requested and (heading != "" or bullets != []):
                raise ValueError(f"unrequested language {lang} must be empty")
        if slide["image"] is not None and not isinstance(slide["image"], str):
            raise ValueError(f"slide {slide['id']} has invalid image")
        if slide["arch_text"] is not None and not isinstance(slide["arch_text"], str):
            raise ValueError(f"slide {slide['id']} has invalid arch_text")
        if index != 3 and (slide["image"] is not None or slide["arch_text"] is not None):
            raise ValueError("image and arch_text are allowed only on the demo slide")

    demo = slides[3]
    if demo["image"] is not None and demo["image"] not in screenshot_paths:
        raise ValueError("demo image is absent from context screenshots")
    if demo["image"] is None and not demo["arch_text"]:
        raise ValueError("demo slide requires arch_text when no image is selected")

    if not isinstance(deck["title"], str):
        raise ValueError("SlideDeck title must be a string")
    if not isinstance(deck["script_ja"], str) or not isinstance(deck["script_en"], str):
        raise ValueError("SlideDeck scripts must be strings")
    if len(deck["script_ja"]) > 300:
        raise ValueError("Japanese script exceeds 300 characters")
    if len(deck["script_en"].split()) > 90:
        raise ValueError("English script exceeds 90 words")
    for lang in SUPPORTED_LANGS - requested:
        if deck[f"script_{lang}"] != "":
            raise ValueError(f"unrequested language {lang} script must be empty")
    return deck


def _response_text(response: Any) -> str:
    try:
        text = response.choices[0].message.content
    except (AttributeError, IndexError, TypeError):
        text = None
    if not isinstance(text, str) or not text.strip():
        raise ValueError("Structured Outputs response contained no JSON text")
    return text


def _azure_config() -> tuple[str, str, str, str]:
    names = ("AZURE_OPENAI_ENDPOINT", "AZURE_OPENAI_API_KEY", "AZURE_OPENAI_DEPLOYMENT")
    missing = [name for name in names if not os.environ.get(name)]
    if missing:
        raise RuntimeError(f"missing Azure OpenAI configuration: {', '.join(missing)}")
    return (
        os.environ["AZURE_OPENAI_ENDPOINT"],
        os.environ["AZURE_OPENAI_API_KEY"],
        os.environ["AZURE_OPENAI_DEPLOYMENT"],
        os.environ.get("OPENAI_API_VERSION", DEFAULT_API_VERSION),
    )


def generate(
    context: dict,
    langs: list,
    client: Any | None = None,
    deployment: str | None = None,
) -> dict:
    """Return a SlideDeck; the only side effect is the injected API call."""
    normalized_langs = list(dict.fromkeys(langs))
    if not normalized_langs or set(normalized_langs) - SUPPORTED_LANGS:
        raise ValueError("langs must contain one or both of: ja, en")
    if not isinstance(context, dict):
        raise TypeError("context must be a dictionary")
    if client is None:
        endpoint, api_key, configured_deployment, api_version = _azure_config()
        from openai import AzureOpenAI

        client = AzureOpenAI(
            azure_endpoint=endpoint,
            api_key=api_key,
            api_version=api_version,
        )
        deployment = configured_deployment
    elif not deployment:
        deployment = os.environ.get("AZURE_OPENAI_DEPLOYMENT")
        if not deployment:
            raise RuntimeError("missing Azure OpenAI configuration: AZURE_OPENAI_DEPLOYMENT")

    user_prompt = json.dumps(
        {"requested_languages": normalized_langs, "context": context},
        ensure_ascii=False,
        separators=(",", ":"),
    )
    last_error: Exception | None = None
    for _attempt in range(2):
        response = client.chat.completions.create(
            model=deployment,
            temperature=0,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "slide_deck",
                    "strict": True,
                    "schema": SLIDE_DECK_SCHEMA,
                },
            },
        )
        try:
            return _validate_deck(
                json.loads(_response_text(response)), normalized_langs, context
            )
        except (json.JSONDecodeError, ValueError) as exc:
            last_error = exc
    raise ValueError(f"invalid SlideDeck response after 2 attempts: {last_error}") from last_error


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("context", type=Path, help="path to context.json")
    parser.add_argument("-o", "--output", required=True, type=Path, help="output deck.json path")
    parser.add_argument("--langs", default="ja,en", help="comma-separated languages: ja,en")
    args = parser.parse_args()
    with args.context.open(encoding="utf-8") as context_file:
        context = json.load(context_file)
    deck = generate(context, [lang.strip() for lang in args.langs.split(",") if lang.strip()])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as output_file:
        json.dump(deck, output_file, ensure_ascii=False, indent=2)
        output_file.write("\n")


if __name__ == "__main__":
    main()
