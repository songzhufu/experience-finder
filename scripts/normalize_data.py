#!/usr/bin/env python
"""Normalize cached Xiaohongshu raw notes."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


SKILL_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RAW_PATH = SKILL_ROOT / "data" / "raw_notes.jsonl"
DEFAULT_OUTPUT_PATH = SKILL_ROOT / "data" / "normalized_notes.json"
DEFAULT_ALIASES_PATH = SKILL_ROOT / "references" / "company_aliases.md"


BUILTIN_ROLES = [
    "后端开发", "后端", "Java", "Golang", "Go", "C++", "前端开发", "前端",
    "算法", "机器学习", "推荐算法", "客户端", "Android", "iOS", "测试开发",
    "数据分析", "数据开发", "产品经理", "产品", "运营", "安全", "大数据",
]

ROUND_PATTERNS = [
    ("笔试", r"笔试|测评|在线编程"),
    ("一面", r"一面|1面|初面|技术一面"),
    ("二面", r"二面|2面|技术二面"),
    ("三面", r"三面|3面"),
    ("主管面", r"主管面|leader面|Leader面|老板面"),
    ("HR面", r"HR面|hr面|人事面"),
    ("终面", r"终面|总监面|offer面"),
]

RECRUITMENT_PATTERNS = [
    ("2026 暑期实习", r"2026.{0,6}(暑期实习|暑实)|暑期实习.{0,6}2026"),
    ("2025 暑期实习", r"2025.{0,6}(暑期实习|暑实)|暑期实习.{0,6}2025"),
    ("2026 秋招", r"2026.{0,6}(秋招|校招)|秋招.{0,6}2026"),
    ("2025 秋招", r"2025.{0,6}(秋招|校招)|秋招.{0,6}2025"),
    ("暑期实习", r"暑期实习|暑实|summer intern|Summer Intern"),
    ("秋招", r"秋招|校招|应届|提前批"),
    ("日常实习", r"日常实习|日常|实习生"),
]


def split_csv(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in re.split(r"[,，]", value) if item.strip()]


def load_config(path: str | None) -> dict[str, Any]:
    if not path:
        return {}
    with Path(path).open("r", encoding="utf-8") as f:
        return json.load(f)


def load_aliases(path: Path) -> dict[str, list[str]]:
    aliases: dict[str, list[str]] = {}
    current = ""
    if not path.exists():
        return aliases
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if line.startswith("## "):
            current = line[3:].strip()
            aliases.setdefault(current, [current])
        elif current and line.startswith("- "):
            aliases.setdefault(current, [])
            aliases[current].append(line[2:].strip())
    return aliases


def note_text(note: dict[str, Any]) -> str:
    return "\n".join(
        str(note.get(key, "") or "")
        for key in ["company_query", "keyword", "title", "author", "publish_date", "body", "url"]
    )


def canonical_company(note: dict[str, Any], aliases: dict[str, list[str]], requested: list[str]) -> str:
    text = note_text(note).lower()
    candidates = requested or list(aliases.keys())
    for company in candidates:
        names = aliases.get(company, [company])
        if any(alias.lower() in text for alias in names if alias):
            return company
    query = note.get("company_query")
    return str(query or "未识别公司")


def infer_first(text: str, patterns: list[tuple[str, str]], default: str = "未识别") -> str:
    for label, pattern in patterns:
        if re.search(pattern, text, flags=re.IGNORECASE):
            return label
    return default


def infer_role(text: str, configured_roles: list[str]) -> str:
    for role in configured_roles:
        if role and role.lower() in text.lower():
            return role
    for role in BUILTIN_ROLES:
        if role.lower() in text.lower():
            return role
    return "未识别"


def load_vision(path: str | None) -> dict[str, list[str]]:
    if not path:
        return {}
    with Path(path).open("r", encoding="utf-8") as f:
        data = json.load(f)
    normalized: dict[str, list[str]] = {}
    for key, value in data.items():
        if isinstance(value, list):
            normalized[key] = [str(item).strip() for item in value if str(item).strip()]
        elif isinstance(value, str) and value.strip():
            normalized[key] = [value.strip()]
    return normalized


def load_raw(path: Path) -> list[dict[str, Any]]:
    notes: list[dict[str, Any]] = []
    if not path.exists():
        return notes
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                notes.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return notes


def dedupe_key(note: dict[str, Any]) -> tuple[str, str, str]:
    return (
        str(note.get("url") or "").strip(),
        str(note.get("title") or "").strip(),
        str(note.get("author") or "").strip(),
    )


def is_inaccessible(note: dict[str, Any]) -> bool:
    if note.get("access_status") == "search_card_only":
        return False
    if note.get("access_status") == "blocked":
        return True
    text = note_text(note)
    blocked_phrases = ["当前笔记暂时无法浏览", "扫码查看", "登录后查看"]
    return any(phrase in text for phrase in blocked_phrases)


def normalize_notes(raw_notes: list[dict[str, Any]], aliases: dict[str, list[str]], companies: list[str], roles: list[str], vision: dict[str, list[str]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str, str]] = set()
    normalized: list[dict[str, Any]] = []
    for note in raw_notes:
        if is_inaccessible(note):
            continue
        key = dedupe_key(note)
        if key in seen:
            continue
        seen.add(key)
        text = note_text(note)
        url = str(note.get("url") or "")
        image_questions = vision.get(url, [])
        normalized.append(
            {
                "company": canonical_company(note, aliases, companies),
                "title": note.get("title") or "无标题",
                "author": note.get("author") or "未知",
                "publish_date": note.get("publish_date") or "未知",
                "role": infer_role(text, roles),
                "recruitment_type": infer_first(text, RECRUITMENT_PATTERNS),
                "interview_round": infer_first(text, ROUND_PATTERNS),
                "body": note.get("body") or "",
                "image_urls": note.get("image_urls") or [],
                "image_questions": image_questions,
                "image_ocr_status": "已识别" if image_questions else "待识别",
                "url": url,
                "keyword": note.get("keyword") or "",
                "access_status": note.get("access_status") or "ok",
                "skip_reason": note.get("skip_reason") or "",
            }
        )
    normalized.sort(key=lambda item: (item["company"], item["recruitment_type"], item["title"]))
    return normalized


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Normalize Xiaohongshu raw note cache.")
    parser.add_argument("--config", help="JSON config path.")
    parser.add_argument("--raw-input", default=str(DEFAULT_RAW_PATH), help="Raw JSONL input path.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT_PATH), help="Normalized JSON output path.")
    parser.add_argument("--aliases", default=str(DEFAULT_ALIASES_PATH), help="Company aliases markdown path.")
    parser.add_argument("--companies", help="Comma-separated canonical company names.")
    parser.add_argument("--roles", help="Comma-separated role names.")
    parser.add_argument("--vision-json", help="Optional URL-to-recognized-image-questions JSON.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = load_config(args.config)
    raw_path = Path(args.raw_input)
    output_path = Path(args.output)
    aliases_path = Path(args.aliases)
    if not raw_path.is_absolute():
        raw_path = SKILL_ROOT / raw_path
    if not output_path.is_absolute():
        output_path = SKILL_ROOT / output_path
    if not aliases_path.is_absolute():
        aliases_path = SKILL_ROOT / aliases_path

    companies = split_csv(args.companies) or config.get("companies", [])
    roles = split_csv(args.roles) or config.get("roles", [])
    aliases = load_aliases(aliases_path)
    vision = load_vision(args.vision_json)
    normalized = normalize_notes(load_raw(raw_path), aliases, companies, roles, vision)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(normalized, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Normalized {len(normalized)} notes -> {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
