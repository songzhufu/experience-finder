#!/usr/bin/env python
"""Run a deterministic offline smoke test for normalization and rendering."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
RAW_PATH = SKILL_ROOT / "data" / "offline_test_raw_notes.jsonl"
NORMALIZED_PATH = SKILL_ROOT / "data" / "offline_test_normalized_notes.json"
MD_PATH = SKILL_ROOT / "output" / "offline_test_xhs_interview_summary.md"
TXT_PATH = SKILL_ROOT / "output" / "offline_test_xhs_interview_summary.txt"


SAMPLE_NOTES = [
    {
        "company_query": "字节跳动",
        "keyword": "字节跳动 后端 暑期实习 面经",
        "title": "字节后端暑期实习一面复盘",
        "author": "求职记录员",
        "publish_date": "2026-03-18",
        "body": "投递的是后端开发暑期实习。一面主要问了项目里的缓存设计、MySQL 索引、Redis 缓存击穿，以及一道简单算法题。",
        "image_urls": ["https://example.com/xhs/interview-question-1.jpg"],
        "url": "https://www.xiaohongshu.com/explore/sample-byte-backend",
    },
    {
        "company_query": "阿里巴巴",
        "keyword": "阿里 算法 秋招 面经",
        "title": "阿里算法秋招二面记录",
        "author": "算法备战中",
        "publish_date": "2026-08-02",
        "body": "淘宝算法岗秋招二面，主要聊推荐系统、召回排序、A/B 实验和项目指标。",
        "image_urls": [],
        "url": "https://www.xiaohongshu.com/explore/sample-ali-algo",
    },
    {
        "company_query": "阿里巴巴",
        "keyword": "阿里 算法 秋招 面经",
        "title": "阿里算法秋招二面记录",
        "author": "算法备战中",
        "publish_date": "2026-08-02",
        "body": "重复样例，应该被去重。",
        "image_urls": [],
        "url": "https://www.xiaohongshu.com/explore/sample-ali-algo",
    },
    {
        "company_query": "字节跳动",
        "keyword": "字节跳动 面经",
        "title": "字节跳动前端秋招一面经验",
        "author": "卡片作者",
        "publish_date": "",
        "body": "搜索结果卡片摘要：前端秋招一面，问了 React、浏览器缓存和项目难点。",
        "image_urls": [],
        "url": "https://www.xiaohongshu.com/explore/sample-byte-card-only",
        "access_status": "search_card_only",
        "skip_reason": "当前笔记暂时无法浏览",
    },
]


def run(cmd: list[str]) -> None:
    subprocess.run(cmd, cwd=SKILL_ROOT, check=True)


def main() -> int:
    RAW_PATH.parent.mkdir(parents=True, exist_ok=True)
    MD_PATH.parent.mkdir(parents=True, exist_ok=True)
    with RAW_PATH.open("w", encoding="utf-8") as f:
        for note in SAMPLE_NOTES:
            f.write(json.dumps(note, ensure_ascii=False) + "\n")

    run(
        [
            sys.executable,
            "scripts/normalize_data.py",
            "--raw-input",
            str(RAW_PATH),
            "--output",
            str(NORMALIZED_PATH),
            "--companies",
            "字节跳动,阿里巴巴",
            "--roles",
            "后端开发,算法",
        ]
    )
    run(
        [
            sys.executable,
            "scripts/generate_markdown.py",
            "--input",
            str(NORMALIZED_PATH),
            "--output",
            str(MD_PATH),
            "--txt",
            "--txt-output",
            str(TXT_PATH),
        ]
    )

    notes = json.loads(NORMALIZED_PATH.read_text(encoding="utf-8"))
    markdown = MD_PATH.read_text(encoding="utf-8")
    assert len(notes) == 3, f"expected deduped 3 notes, got {len(notes)}"
    assert "## 字节跳动" in markdown
    assert "## 阿里巴巴" in markdown
    assert "### 暑期实习" in markdown
    assert "### 秋招" in markdown
    assert "待识别" in markdown
    assert "详情页不可见" in markdown
    print(f"Offline smoke test passed -> {MD_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
