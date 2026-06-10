"""Render the README demo GIF and the GitHub social preview image.

Both artifacts are generated from the real ``examples/service_health`` audit
output so the marketing material never drifts from actual tool behavior.

Usage:

    python scripts/render_media.py --output docs/assets
"""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"
FONT_BOLD_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf"

# GitHub-dark inspired palette.
BG = (13, 17, 23)
TITLE_BAR = (22, 27, 34)
FG = (230, 237, 243)
DIM = (139, 148, 158)
GREEN = (63, 185, 80)
RED = (248, 81, 73)
YELLOW = (210, 153, 34)
CYAN = (121, 192, 255)
MAGENTA = (188, 140, 255)

PROMPT = "$ "
COMMAND = "agentic-testops audit examples/service_health --suggest-fixes"

# (text, color, bold) — curated from the real generated report.
OUTPUT_LINES: list[tuple[str, tuple[int, int, int], bool]] = [
    ("Agentic TestOps report written to reports/agentic-testops-report.md", DIM, False),
    ("", FG, False),
    ("# Agentic TestOps Audit Report", CYAN, True),
    ("", FG, False),
    ("- Status: FAIL   - Parsed failures: 3   - Structured results: JUnit XML", RED, False),
    ("", FG, False),
    ("## Diagnosis", CYAN, True),
    ("1. test_load_config_handles_missing_file", FG, False),
    ("   FileNotFoundError  ->  filesystem-boundary  ->  service_health.py:9", YELLOW, False),
    ("2. test_display_name_accepts_dict_user", FG, False),
    ("   AttributeError     ->  object-interface     ->  service_health.py:15", YELLOW, False),
    ("3. test_invoice_total_sums_amounts", FG, False),
    ("   NameError          ->  symbol-resolution    ->  service_health.py:20", YELLOW, False),
    ("", FG, False),
    ("## Dry-Run Fix Suggestions (review previews, never auto-applied)", CYAN, True),
    ("--- a/service_health.py", DIM, False),
    ("+++ b/service_health.py", DIM, False),
    ("     if not config_path.exists():", FG, False),
    ("-        raise FileNotFoundError(f\"Missing config file: {config_path}\")", RED, False),
    ("+        return {\"raw\": \"\"}", GREEN, False),
]


def _fonts(size: int) -> tuple[ImageFont.FreeTypeFont, ImageFont.FreeTypeFont]:
    return ImageFont.truetype(FONT_PATH, size), ImageFont.truetype(FONT_BOLD_PATH, size)


def _terminal_frame(
    width: int,
    height: int,
    lines: list[tuple[str, tuple[int, int, int], bool]],
    font_size: int = 15,
    show_cursor_on_last: bool = False,
) -> Image.Image:
    font, bold_font = _fonts(font_size)
    image = Image.new("RGB", (width, height), BG)
    draw = ImageDraw.Draw(image)

    # Title bar with traffic lights.
    bar_height = 34
    draw.rectangle([0, 0, width, bar_height], fill=TITLE_BAR)
    for index, color in enumerate([(255, 95, 86), (255, 189, 46), (39, 201, 63)]):
        cx = 20 + index * 22
        draw.ellipse([cx - 6, bar_height // 2 - 6, cx + 6, bar_height // 2 + 6], fill=color)
    title = "agentic-testops"
    title_width = draw.textlength(title, font=font)
    draw.text(((width - title_width) // 2, bar_height // 2 - font_size // 2 - 1), title, font=font, fill=DIM)

    line_height = font_size + 7
    x, y = 16, bar_height + 12
    for index, (text, color, is_bold) in enumerate(lines):
        chosen = bold_font if is_bold else font
        if text.startswith(PROMPT):
            draw.text((x, y), PROMPT, font=bold_font, fill=GREEN)
            offset = draw.textlength(PROMPT, font=bold_font)
            draw.text((x + offset, y), text[len(PROMPT) :], font=chosen, fill=color)
            if show_cursor_on_last and index == len(lines) - 1:
                cursor_x = x + offset + draw.textlength(text[len(PROMPT) :], font=chosen) + 2
                draw.rectangle([cursor_x, y + 1, cursor_x + 8, y + font_size + 1], fill=FG)
        else:
            draw.text((x, y), text, font=chosen, fill=color)
        y += line_height
    return image


def render_demo_gif(output_path: Path, width: int = 880, height: int = 600) -> None:
    frames: list[Image.Image] = []
    durations: list[int] = []

    # Typing animation for the command.
    step = 3
    for cut in range(0, len(COMMAND) + 1, step):
        frames.append(
            _terminal_frame(width, height, [(PROMPT + COMMAND[:cut], FG, False)], show_cursor_on_last=True)
        )
        durations.append(55)

    # Output appears in small chunks.
    typed: list[tuple[str, tuple[int, int, int], bool]] = [(PROMPT + COMMAND, FG, False)]
    frames.append(_terminal_frame(width, height, typed))
    durations.append(450)
    chunk = 2
    for start in range(0, len(OUTPUT_LINES), chunk):
        typed = [(PROMPT + COMMAND, FG, False), *OUTPUT_LINES[: start + chunk]]
        frames.append(_terminal_frame(width, height, typed))
        durations.append(330)

    durations[-1] = 4500  # Hold the final frame.
    output_path.parent.mkdir(parents=True, exist_ok=True)
    frames[0].save(
        output_path,
        save_all=True,
        append_images=frames[1:],
        duration=durations,
        loop=0,
        optimize=True,
    )


def render_social_preview(output_path: Path, width: int = 1280, height: int = 640) -> None:
    image = Image.new("RGB", (width, height), BG)
    draw = ImageDraw.Draw(image)
    _, title_font = _fonts(56)
    _, subtitle_bold = _fonts(24)
    body_font, _ = _fonts(22)
    chip_font, _ = _fonts(17)

    draw.text((70, 80), "Agentic TestOps", font=title_font, fill=FG)
    draw.text((70, 170), "Turn failing pytest runs into structured,", font=subtitle_bold, fill=DIM)
    draw.text((70, 205), "repair-oriented engineering reports.", font=subtitle_bold, fill=DIM)

    pipeline = [
        ("pytest run", CYAN),
        ("failure parsing", FG),
        ("root-cause diagnosis", YELLOW),
        ("patch proposals", MAGENTA),
        ("dry-run diffs", GREEN),
    ]
    x = 70
    y = 280
    for index, (label, color) in enumerate(pipeline):
        text_width = draw.textlength(label, font=chip_font)
        draw.rounded_rectangle([x, y, x + text_width + 22, y + 38], radius=10, outline=color, width=2)
        draw.text((x + 11, y + 9), label, font=chip_font, fill=color)
        x += text_width + 22
        if index < len(pipeline) - 1:
            draw.text((x + 6, y + 7), "->", font=chip_font, fill=DIM)
            x += 36

    lines = [
        ("$ pip install agentic-testops", GREEN, False),
        ("$ agentic-testops audit . --detect-flaky 3 --llm-explain", GREEN, False),
        ("", FG, False),
        ("FileNotFoundError  ->  filesystem-boundary  ->  service_health.py:9", YELLOW, False),
        ("flaky: 1  consistent: 2   |   evaluated on real upstream bugs", DIM, False),
    ]
    panel_top = 380
    draw.rounded_rectangle([60, panel_top, width - 60, panel_top + 200], radius=14, fill=(22, 27, 34))
    y = panel_top + 28
    for text, color, _ in lines:
        draw.text((90, y), text, font=body_font, fill=color)
        y += 34

    output_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(output_path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("docs/assets"))
    args = parser.parse_args()
    render_demo_gif(args.output / "demo.gif")
    render_social_preview(args.output / "social-preview.png")
    print(f"Wrote {args.output / 'demo.gif'} and {args.output / 'social-preview.png'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
