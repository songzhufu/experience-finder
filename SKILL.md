---
name: xiaohongshu-interview-research
description: Collect, cache, normalize, and summarize Xiaohongshu job-search interview experience notes with Playwright. Use when Codex needs to manually-login to Xiaohongshu, search campus hiring or internship interview posts by company/role/recruitment type, extract note metadata/text/image links, classify company aliases, roles, autumn recruiting or summer internship type, interview rounds, OCR/vision status, deduplicate notes, and generate grouped Markdown or TXT interview-experience reports.
---

# Xiaohongshu Interview Research

## Overview

Use this skill to gather a small, compliant sample of Xiaohongshu interview-experience notes and turn cached raw notes into structured Markdown/TXT summaries. The workflow never attempts to bypass CAPTCHA, sliders, risk controls, or login checks; pause for manual user action whenever the site requires it.

## Workflow

1. Check the environment:
   - Run `python --version`.
   - Run `python -m pip show playwright`.
   - If Playwright is missing, tell the user to install it with `python -m pip install playwright` and then `python -m playwright install chromium`.
2. Prepare inputs:
   - Use command-line flags or a JSON config.
   - Companies, roles, recruitment types, keywords, max notes per keyword, and output formats are supported.
3. Collect notes:
   - Run `scripts/playwright_collect.py`.
   - First run opens Xiaohongshu in a visible browser. Ask the user to scan-login and press Enter in the terminal.
   - Reuse `data/browser_profile/` and `data/xhs_state.json` on later runs.
   - Save raw notes to `data/raw_notes.jsonl`.
   - If a note says `当前笔记暂时无法浏览`, `扫码查看`, or similar, complete the manual scan/verification in the visible browser. If it still cannot be viewed, save only the search-result card title/summary/link with `access_status=search_card_only`.
4. Normalize cached notes:
   - Run `scripts/normalize_data.py`.
   - Load company aliases from `references/company_aliases.md`.
   - Deduplicate by URL, title, and author.
   - Infer role, recruitment type, and interview round with simple rules.
   - If no vision/OCR JSON is supplied, keep image links and mark image questions as `待识别`.
5. Generate documents:
   - Run `scripts/generate_markdown.py`.
   - Output grouped Markdown to `output/xhs_interview_summary.md`.
   - Optionally output TXT with `--txt`.

## Commands

Minimal one-company run:

```bash
python -m pip install -r requirements.txt
python -m playwright install chromium
python scripts/playwright_collect.py --companies "字节跳动" --keywords "字节 后端 暑期实习 面经" --max-per-keyword 10
python scripts/normalize_data.py --companies "字节跳动"
python scripts/generate_markdown.py --txt
```

Config-file run:

```json
{
  "companies": ["字节跳动", "阿里巴巴"],
  "roles": ["后端开发", "算法"],
  "recruitment_types": ["秋招", "暑期实习"],
  "keywords": ["面经", "一面", "二面"],
  "max_per_keyword": 10,
  "formats": ["md", "txt"]
}
```

```bash
python scripts/playwright_collect.py --config config.json
python scripts/normalize_data.py --config config.json
python scripts/generate_markdown.py --config config.json
```

Offline smoke test:

```bash
python scripts/run_offline_test.py
```

Semi-automatic one-note MVP:

```bash
python scripts/manual_detail_collect.py --keyword "字节跳动面经" --json-output data/manual_detail_note.json --markdown-output output/manual_detail_note.md --cdp-url http://127.0.0.1:9222 --detail-wait-seconds 120
```

If Codex opens a headed browser that the user cannot see, start a visible Chrome from the user's PowerShell and connect over CDP:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/open_visible_chrome.ps1 -Port 9222
python scripts/manual_detail_collect.py --keyword "字节跳动面经" --json-output data/manual_detail_note.json --markdown-output output/manual_detail_note.md --cdp-url http://127.0.0.1:9222 --detail-wait-seconds 120
```

Use this flow when automatic detail-page navigation triggers Xiaohongshu risk controls but manual clicking from the visible search page works. The script opens the search results page, waits for manual scan-login if a login modal appears, then polls for the user's manual note click without terminal input. It detects same-page URL changes, new tabs/popups, detail selectors, and detail-like page text, extracts one note, and stops immediately if a risk page appears.

## Vision/OCR Handling

Do not fabricate text from images. If the current environment exposes a vision model, use it outside the collector and save recognized results as JSON:

```json
{
  "https://www.xiaohongshu.com/explore/example": [
    "Redis 缓存击穿怎么处理？",
    "讲一下项目中的分库分表方案。"
  ]
}
```

Then pass it to normalization:

```bash
python scripts/normalize_data.py --vision-json data/vision_ocr.json
```

If no vision model is callable, keep image links and mark image-question extraction as `待识别`.

## Classification Rules

- Company aliases live in `references/company_aliases.md`.
- Recruitment type is inferred from terms such as `秋招`, `校招`, `暑期实习`, `日常实习`, and year-like phrases.
- Roles are inferred from supplied roles first, then built-in keywords such as 后端、前端、算法、客户端、测试、产品、运营、数据、Java、C++、Go.
- Interview rounds are inferred from `一面`, `二面`, `三面`, `HR面`, `主管面`, `终面`, `笔试`, and similar phrases.
- Preserve uncertain fields as `未识别`; do not overclaim.

## Safety And Scope

- Keep collection small. Default to 10 notes per keyword.
- Use a visible browser by default.
- Never bypass CAPTCHA, sliders, login walls, or platform risk controls.
- Stop and ask for manual action if the page requests verification or if selectors stop matching.
- Do not normalize notes whose title/body is an access error such as `当前笔记暂时无法浏览`, unless they are explicitly marked `access_status=search_card_only` with search-card fallback text.
- Prefer cached data in `data/raw_notes.jsonl` and `data/normalized_notes.json`; avoid re-visiting pages unnecessarily.
- Respect platform terms and user privacy. Do not collect private messages, comments requiring extra access, or unrelated personal data.
