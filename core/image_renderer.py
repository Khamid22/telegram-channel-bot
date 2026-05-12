from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

from config.settings import BASE_DIR, get_settings
from database.models import Word


@dataclass
class TextBox:
    x: int
    y: int
    width: int
    font_path: str
    font_size: int
    min_font_size: int
    color: str
    line_spacing: int = 8
    max_lines: int | None = None
    prefix: str = ""
    suffix: str = ""
    uppercase: bool = False


def _resolve_path(path: str | Path) -> Path:
    candidate = Path(path)
    return candidate if candidate.is_absolute() else BASE_DIR / candidate


def _safe_slug(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9_-]+", "-", value.lower()).strip("-")
    return slug or "word"


class VocabularyImageRenderer:
    def __init__(self, template_config_path: str | Path | None = None) -> None:
        self.settings = get_settings()
        self.template_config_path = _resolve_path(template_config_path or self.settings.template_config_dir / "default.json")

    def render(self, word: Word, template_config_path: str | Path | None = None) -> Path:
        config_path = _resolve_path(template_config_path or self.template_config_path)
        config = json.loads(config_path.read_text(encoding="utf-8"))
        background_path = _resolve_path(config["background_image"])
        image = Image.open(background_path).convert("RGB")
        draw = ImageDraw.Draw(image)

        payload = {
            "word": word.word,
            "word_type": getattr(word, "word_type", "") or "",
            "phonetic": word.phonetic or "",
            "definition": word.definition,
            "example": word.example or "",
            "level": word.level or "",
        }

        for field_name, box_config in config["fields"].items():
            text = payload.get(field_name, "")
            if not text:
                continue
            box = TextBox(**box_config)
            self._draw_text_box(draw, text, box)

        output_dir = self.settings.generated_image_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"{word.id}-{_safe_slug(word.word)}.png"
        image.save(output_path, "PNG", optimize=True)
        return output_path

    def preview(self, payload: dict[str, Any], template_config_path: str | Path | None = None) -> Path:
        class PreviewWord:
            id = 0
            word = payload.get("word", "serendipity")
            word_type = payload.get("word_type", "noun")
            phonetic = payload.get("phonetic", "/ˌser.ənˈdɪp.ə.ti/")
            definition = payload.get("definition", "The chance discovery of something valuable or pleasant.")
            example = payload.get("example", "Finding that book in the tiny shop was pure serendipity.")
            level = payload.get("level", "C1")

        return self.render(PreviewWord(), template_config_path)

    def _font(self, box: TextBox, size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
        font_path = _resolve_path(box.font_path)
        if font_path.exists():
            return ImageFont.truetype(str(font_path), size=size)

        requested = str(box.font_path).lower()
        wants_serif = any(token in requested for token in ("georgia", "times", "serif"))
        wants_bold = "bold" in requested
        wants_italic = "italic" in requested

        serif_fallbacks = (
            "/System/Library/Fonts/Supplemental/Georgia.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf",
            "/System/Library/Fonts/Supplemental/Georgia Bold Italic.ttf",
            "/System/Library/Fonts/Supplemental/Georgia Bold.ttf",
            "/System/Library/Fonts/Supplemental/Georgia Italic.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSerif-BoldItalic.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Italic.ttf",
        )
        sans_fallbacks = (
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
            "/Library/Fonts/Arial.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-BoldOblique.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Oblique.ttf",
        )

        def matches_style(path: str) -> bool:
            lower = path.lower()
            has_bold = "bold" in lower
            has_italic = "italic" in lower or "oblique" in lower
            return has_bold == wants_bold and has_italic == wants_italic

        ordered = serif_fallbacks if wants_serif else sans_fallbacks
        for fallback in tuple(path for path in ordered if matches_style(path)) + ordered + sans_fallbacks:
            if Path(fallback).exists():
                return ImageFont.truetype(fallback, size=size)
        return ImageFont.load_default()

    def _draw_text_box(self, draw: ImageDraw.ImageDraw, text: str, box: TextBox) -> None:
        text = text.upper() if box.uppercase else text
        text = f"{box.prefix}{text}{box.suffix}"
        size = box.font_size
        while size >= box.min_font_size:
            font = self._font(box, size)
            lines = self._wrap_text(draw, text, font, box.width)
            if box.max_lines and len(lines) > box.max_lines:
                size -= 2
                continue
            break
        else:
            font = self._font(box, box.min_font_size)
            lines = self._wrap_text(draw, text, font, box.width)

        if box.max_lines and len(lines) > box.max_lines:
            lines = lines[: box.max_lines]
            lines[-1] = lines[-1].rstrip(". ") + "..."

        y = box.y
        for line in lines:
            draw.text((box.x, y), line, font=font, fill=box.color)
            bbox = draw.textbbox((box.x, y), line, font=font)
            y += (bbox[3] - bbox[1]) + box.line_spacing

    def _wrap_text(self, draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, max_width: int) -> list[str]:
        words = text.split()
        if not words:
            return []

        lines: list[str] = []
        current = words[0]
        for word in words[1:]:
            candidate = f"{current} {word}"
            if self._text_width(draw, candidate, font) <= max_width:
                current = candidate
            else:
                lines.extend(self._split_long_word(draw, current, font, max_width))
                current = word
        lines.extend(self._split_long_word(draw, current, font, max_width))
        return lines

    def _split_long_word(self, draw: ImageDraw.ImageDraw, word: str, font: ImageFont.ImageFont, max_width: int) -> list[str]:
        if self._text_width(draw, word, font) <= max_width:
            return [word]

        chunks: list[str] = []
        current = ""
        for char in word:
            if self._text_width(draw, current + char, font) <= max_width:
                current += char
            else:
                if current:
                    chunks.append(current)
                current = char
        if current:
            chunks.append(current)
        return chunks

    @staticmethod
    def _text_width(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont) -> int:
        bbox = draw.textbbox((0, 0), text, font=font)
        return bbox[2] - bbox[0]
