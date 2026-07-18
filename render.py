#!/usr/bin/env python3
"""Render a SlideDeck JSON document as a themed Marp HTML deck."""

from __future__ import annotations

import argparse
import html
import json
import subprocess
from pathlib import Path
from typing import Any, Sequence


SLIDE_IDS = ("title", "problem", "solution", "demo", "architecture", "next")
THEME_PATH = Path(__file__).resolve().parent / "theme" / "pitch.css"


def _language_content(slide: dict[str, Any], language: str) -> list[str]:
    heading = str(slide.get(f"heading_{language}", "")).strip()
    bullets = [
        str(item).strip()
        for item in slide.get(f"bullets_{language}", [])
        if str(item).strip()
    ]
    if not heading and not bullets:
        return []

    if language == "en":
        parts = ['<div class="en">']
        if heading:
            parts.append(f"<h2>{html.escape(heading)}</h2>")
        if bullets:
            parts.append("<ul>")
            parts.extend(f"<li>{html.escape(item)}</li>" for item in bullets)
            parts.append("</ul>")
        parts.append("</div>")
        return parts

    parts = [f"# {heading}"] if heading else []
    parts.extend(f"- {item}" for item in bullets)
    return parts


def _demo_visual(slide: dict[str, Any]) -> list[str]:
    if slide.get("id") != "demo":
        return []
    image = slide.get("image")
    if image:
        return [f"![Demo screenshot]({image})"]
    arch_text = slide.get("arch_text")
    if arch_text:
        return ["```text", str(arch_text).rstrip(), "```"]
    return []


def _slides_markdown(deck: dict[str, Any], langs: Sequence[str]) -> str:
    slides = deck.get("slides")
    if not isinstance(slides, list) or len(slides) != len(SLIDE_IDS):
        raise ValueError("SlideDeck must contain exactly 6 slides")
    ids = tuple(slide.get("id") for slide in slides)
    if ids != SLIDE_IDS:
        raise ValueError(f"SlideDeck slide order must be: {', '.join(SLIDE_IDS)}")

    rendered: list[str] = []
    for slide in slides:
        content: list[str] = []
        for language in langs:
            content.extend(_language_content(slide, language))
            if content and content[-1] != "":
                content.append("")
        content.extend(_demo_visual(slide))
        rendered.append("\n".join(content).rstrip())

    front_matter = "---\nmarp: true\ntheme: pitch\npaginate: true\n---"
    return front_matter + "\n\n" + "\n\n---\n\n".join(rendered) + "\n"


def render(deck: dict[str, Any], out_dir: str | Path, langs: Sequence[str]) -> None:
    """Write Marp Markdown, requested scripts, and the terminal HTML artifact."""
    requested = list(dict.fromkeys(langs))
    if not requested or any(language not in {"ja", "en"} for language in requested):
        raise ValueError("langs must contain ja and/or en")

    output = Path(out_dir)
    output.mkdir(parents=True, exist_ok=True)
    slides_path = output / "slides.md"
    slides_path.write_text(_slides_markdown(deck, requested), encoding="utf-8")

    for language in ("ja", "en"):
        script_path = output / f"script_{language}.md"
        script = str(deck.get(f"script_{language}", "")).strip()
        if language in requested and script:
            script_path.write_text(script + "\n", encoding="utf-8")
        elif script_path.exists():
            script_path.unlink()

    subprocess.run(
        [
            "npx",
            "@marp-team/marp-cli",
            str(slides_path),
            "-o",
            str(output / "deck.html"),
            "--theme",
            str(THEME_PATH),
        ],
        check=True,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("deck", type=Path, help="SlideDeck JSON input")
    parser.add_argument("-o", "--out-dir", type=Path, required=True)
    parser.add_argument(
        "--langs",
        default=None,
        help="Comma-separated languages (default: infer non-empty scripts)",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    deck = json.loads(args.deck.read_text(encoding="utf-8"))
    if args.langs:
        langs = [item.strip() for item in args.langs.split(",") if item.strip()]
    else:
        langs = [language for language in ("ja", "en") if deck.get(f"script_{language}")]
    render(deck, args.out_dir, langs)


if __name__ == "__main__":
    main()
