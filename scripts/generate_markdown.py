#!/usr/bin/env python
"""Generate Markdown/TXT summaries from normalized Xiaohongshu notes."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any


SKILL_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT_PATH = SKILL_ROOT / "data" / "normalized_notes.json"
DEFAULT_MD_PATH = SKILL_ROOT / "output" / "xhs_interview_summary.md"
DEFAULT_TXT_PATH = SKILL_ROOT / "output" / "xhs_interview_summary.txt"


def load_config(path: str | None) -> dict[str, Any]:
    if not path:
        return {}
    with Path(path).open("r", encoding="utf-8") as f:
        return json.load(f)


def clean(value: Any, default: str = "未知") -> str:
    text = str(value or "").strip()
    return text if text else default


def load_notes(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError("Normalized input must be a JSON list.")
    return data


def group_notes(notes: list[dict[str, Any]]) -> dict[str, dict[str, list[dict[str, Any]]]]:
    grouped: dict[str, dict[str, list[dict[str, Any]]]] = defaultdict(lambda: defaultdict(list))
    for note in notes:
        grouped[clean(note.get("company"), "未识别公司")][clean(note.get("recruitment_type"), "未识别")].append(note)
    return grouped


def render_markdown(notes: list[dict[str, Any]]) -> str:
    lines: list[str] = ["# 小红书求职面经汇总", ""]
    grouped = group_notes(notes)
    for company in sorted(grouped.keys()):
        lines.extend([f"## {company}", ""])
        for recruitment_type in sorted(grouped[company].keys()):
            lines.extend([f"### {recruitment_type}", ""])
            for note in grouped[company][recruitment_type]:
                lines.extend(
                    [
                        f"#### {clean(note.get('title'), '无标题')}",
                        "",
                        f"* 发布日期：{clean(note.get('publish_date'))}",
                        f"* 作者：{clean(note.get('author'))}",
                        f"* 岗位：{clean(note.get('role'), '未识别')}",
                        f"* 面试轮次：{clean(note.get('interview_round'), '未识别')}",
                        f"* 原文链接：{clean(note.get('url'), '无')}",
                        "",
                        "##### 面经内容",
                        "",
                    ]
                )
                body = clean(note.get("body"), "正文未采集到。")
                lines.extend([body, ""])
                if note.get("access_status") == "search_card_only":
                    lines.extend(["##### 采集状态", "", f"详情页不可见，已保留搜索结果卡片信息。原因：{clean(note.get('skip_reason'))}", ""])
                image_questions = note.get("image_questions") or []
                image_urls = note.get("image_urls") or []
                if image_questions:
                    lines.extend(["##### 图片识别面试题", ""])
                    for question in image_questions:
                        lines.append(f"- {question}")
                    lines.append("")
                elif image_urls:
                    lines.extend(["##### 图片文字识别", "", "待识别", ""])
                if image_urls:
                    lines.extend(["##### 图片链接", ""])
                    for image_url in image_urls:
                        lines.append(f"- {image_url}")
                    lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def markdown_to_txt(markdown: str) -> str:
    lines: list[str] = []
    for line in markdown.splitlines():
        stripped = line.lstrip("#").strip()
        if stripped.startswith("* "):
            stripped = stripped[2:]
        elif stripped.startswith("- "):
            stripped = "  " + stripped[2:]
        lines.append(stripped)
    return "\n".join(lines).strip() + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate grouped Markdown/TXT summary.")
    parser.add_argument("--config", help="JSON config path.")
    parser.add_argument("--input", default=str(DEFAULT_INPUT_PATH), help="Normalized JSON input path.")
    parser.add_argument("--output", default=str(DEFAULT_MD_PATH), help="Markdown output path.")
    parser.add_argument("--txt-output", default=str(DEFAULT_TXT_PATH), help="TXT output path.")
    parser.add_argument("--txt", action="store_true", help="Also generate TXT.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = load_config(args.config)
    input_path = Path(args.input)
    output_path = Path(args.output)
    txt_path = Path(args.txt_output)
    if not input_path.is_absolute():
        input_path = SKILL_ROOT / input_path
    if not output_path.is_absolute():
        output_path = SKILL_ROOT / output_path
    if not txt_path.is_absolute():
        txt_path = SKILL_ROOT / txt_path

    notes = load_notes(input_path)
    markdown = render_markdown(notes)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(markdown, encoding="utf-8")

    formats = config.get("formats", [])
    need_txt = args.txt or "txt" in formats
    if need_txt:
        txt_path.parent.mkdir(parents=True, exist_ok=True)
        txt_path.write_text(markdown_to_txt(markdown), encoding="utf-8")
        print(f"Generated Markdown and TXT -> {output_path}, {txt_path}")
    else:
        print(f"Generated Markdown -> {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
