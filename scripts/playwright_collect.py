#!/usr/bin/env python
"""Small-scope Xiaohongshu interview-note collector using Playwright.

This script uses a visible browser, supports manual login, saves browser state,
and caches raw note records as JSONL. It intentionally does not bypass CAPTCHA,
sliders, login walls, or risk controls.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Iterable
from urllib.parse import quote


SKILL_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = SKILL_ROOT / "data"
DEFAULT_RAW_PATH = DATA_DIR / "raw_notes.jsonl"
DEFAULT_STATE_PATH = DATA_DIR / "xhs_state.json"
DEFAULT_PROFILE_DIR = DATA_DIR / "browser_profile"
DEFAULT_BLOCKED_PATH = DATA_DIR / "blocked_notes.jsonl"

BLOCKED_PHRASES = [
    "当前笔记暂时无法浏览",
    "扫码查看",
    "登录后查看",
    "验证码",
    "滑块",
    "安全验证",
    "操作频繁",
]

NETWORK_ERROR_MARKERS = [
    "ERR_NETWORK_ACCESS_DENIED",
    "ERR_TUNNEL_CONNECTION_FAILED",
    "ERR_PROXY_CONNECTION_FAILED",
    "ERR_INTERNET_DISCONNECTED",
]


@dataclass
class RawNote:
    company_query: str
    keyword: str
    title: str = ""
    author: str = ""
    publish_date: str = ""
    body: str = ""
    image_urls: list[str] = field(default_factory=list)
    url: str = ""
    access_status: str = "ok"
    skip_reason: str = ""
    collected_at: float = field(default_factory=time.time)


def split_csv(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in re.split(r"[,，]", value) if item.strip()]


def load_config(path: str | None) -> dict:
    if not path:
        return {}
    config_path = Path(path)
    with config_path.open("r", encoding="utf-8") as f:
        return json.load(f)


def unique(items: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        clean = item.strip()
        if clean and clean not in seen:
            seen.add(clean)
            out.append(clean)
    return out


def build_search_terms(args: argparse.Namespace, config: dict) -> list[tuple[str, str]]:
    companies = split_csv(args.companies) or config.get("companies", [])
    roles = split_csv(args.roles) or config.get("roles", [])
    recruitment_types = split_csv(args.recruitment_types) or config.get("recruitment_types", [])
    keywords = split_csv(args.keywords) or config.get("keywords", [])

    if not companies:
        raise SystemExit("Please provide at least one company with --companies or config.companies.")

    terms: list[tuple[str, str]] = []
    if keywords:
        for company in companies:
            for keyword in keywords:
                if company in keyword:
                    terms.append((company, keyword))
                else:
                    terms.append((company, f"{company} {keyword}"))
        return terms

    role_part = roles or [""]
    type_part = recruitment_types or [""]
    for company in companies:
        for role in role_part:
            for recruitment_type in type_part:
                pieces = [company, role, recruitment_type, "面经"]
                terms.append((company, " ".join(piece for piece in pieces if piece)))
    return terms


def append_jsonl(path: Path, note: RawNote) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(asdict(note), ensure_ascii=False) + "\n")


def is_network_block_error(exc: Exception) -> bool:
    text = str(exc)
    return any(marker in text for marker in NETWORK_ERROR_MARKERS)


def print_network_block_help(url: str) -> None:
    print(f"\nNetwork access was denied while opening: {url}")
    print("This usually means Codex's sandbox cannot access the public web from Playwright.")
    print("Run the same command in your local PowerShell, or enable network access for this Codex session if your client supports it.")


def existing_urls(path: Path) -> set[str]:
    urls: set[str] = set()
    if not path.exists():
        return urls
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if obj.get("url"):
                urls.add(obj["url"])
    return urls


def find_blocked_phrase(text: str) -> str:
    for phrase in BLOCKED_PHRASES:
        if phrase in text:
            return phrase
    return ""


def looks_blocked(page) -> bool:
    text = ""
    try:
        text = page.locator("body").inner_text(timeout=3000)
    except Exception:
        return False
    return bool(find_blocked_phrase(text))


def inaccessible_reason(page) -> str:
    try:
        text = page.locator("body").inner_text(timeout=3000)
    except Exception:
        return ""
    return find_blocked_phrase(text)


def collect_note(page, url: str, company: str, keyword: str) -> RawNote:
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=60000)
    except Exception as exc:
        if is_network_block_error(exc):
            print_network_block_help(url)
            return RawNote(
                company_query=company,
                keyword=keyword,
                url=url,
                access_status="blocked",
                skip_reason="network_access_denied",
            )
        raise
    page.wait_for_timeout(2500)
    reason = inaccessible_reason(page)
    if reason:
        print(f"\nXiaohongshu requires manual action on this note: {reason}")
        input("Please complete it manually in the opened browser, then press Enter to continue...")
        page.wait_for_timeout(1500)
        reason = inaccessible_reason(page)
        if reason:
            return RawNote(
                company_query=company,
                keyword=keyword,
                url=url,
                access_status="blocked",
                skip_reason=reason,
            )

    title = ""
    for selector in ["#detail-title", ".title", "h1", "[class*=title]"]:
        try:
            title = page.locator(selector).first.inner_text(timeout=2000).strip()
            if title:
                break
        except Exception:
            pass

    body = ""
    for selector in ["#detail-desc", ".desc", "[class*=desc]", "[class*=content]", "article"]:
        try:
            body = page.locator(selector).first.inner_text(timeout=2000).strip()
            if body:
                break
        except Exception:
            pass

    author = ""
    for selector in [".author .name", "[class*=author] [class*=name]", "[class*=user] [class*=name]"]:
        try:
            author = page.locator(selector).first.inner_text(timeout=2000).strip()
            if author:
                break
        except Exception:
            pass

    publish_date = ""
    try:
        body_text = page.locator("body").inner_text(timeout=3000)
        date_match = re.search(r"(\d{4}[-/.年]\d{1,2}[-/.月]\d{1,2}日?|\d{1,2}[-/.月]\d{1,2}日?|编辑于\s*\S+|发布于\s*\S+)", body_text)
        if date_match:
            publish_date = date_match.group(1)
    except Exception:
        pass

    image_urls: list[str] = []
    try:
        srcs = page.locator("img").evaluate_all(
            "(imgs) => imgs.map(img => img.currentSrc || img.src).filter(Boolean)"
        )
        image_urls = unique(src for src in srcs if "avatar" not in src.lower())[:20]
    except Exception:
        pass

    return RawNote(
        company_query=company,
        keyword=keyword,
        title=title,
        author=author,
        publish_date=publish_date,
        body=body,
        image_urls=image_urls,
        url=url,
    )


def extract_search_cards(page) -> list[dict[str, str]]:
    """Best-effort extraction from search result cards without opening details."""
    script = """
    () => {
      const links = Array.from(document.querySelectorAll('a[href*="/explore/"]'));
      const rows = [];
      const seen = new Set();
      for (const link of links) {
        const url = link.href;
        if (!url || seen.has(url)) continue;
        seen.add(url);
        let node = link;
        let text = "";
        for (let i = 0; i < 4 && node; i++) {
          text = (node.innerText || "").trim();
          if (text.length > 8) break;
          node = node.parentElement;
        }
        const lines = text.split(/\\n+/).map(s => s.trim()).filter(Boolean);
        rows.push({
          url,
          title: lines[0] || (link.getAttribute("title") || "").trim(),
          author: lines.length > 1 ? lines[lines.length - 1] : "",
          body: lines.join("\\n")
        });
      }
      return rows;
    }
    """
    try:
        cards = page.evaluate(script)
    except Exception:
        return []
    out: list[dict[str, str]] = []
    for card in cards:
        if isinstance(card, dict) and card.get("url"):
            out.append({key: str(card.get(key) or "") for key in ["url", "title", "author", "body"]})
    return out


def collect_search_results(context, company: str, keyword: str, max_count: int, raw_path: Path) -> int:
    page = context.new_page()
    search_url = f"https://www.xiaohongshu.com/search_result?keyword={quote(keyword)}"
    print(f"\nSearching: {keyword}")
    try:
        page.goto(search_url, wait_until="domcontentloaded", timeout=60000)
    except Exception as exc:
        if is_network_block_error(exc):
            print_network_block_help(search_url)
            return 0
        raise
    page.wait_for_timeout(4000)

    if looks_blocked(page):
        print("\nXiaohongshu requires login or manual verification before search results are available.")
        input("Please finish the manual step in the opened browser, then press Enter to continue...")
        page.wait_for_timeout(2500)

    known_urls = existing_urls(raw_path)
    cards_by_url: dict[str, dict[str, str]] = {}
    urls: list[str] = []
    for _ in range(4):
        try:
            hrefs = page.locator('a[href*="/explore/"]').evaluate_all(
                "(links) => links.map(a => a.href).filter(Boolean)"
            )
            urls = unique(urls + hrefs)
            for card in extract_search_cards(page):
                cards_by_url[card["url"]] = card
        except Exception:
            pass
        if len(urls) >= max_count:
            break
        page.mouse.wheel(0, 1800)
        page.wait_for_timeout(1200)

    if not urls:
        print("No note links found. The page structure may have changed, or login/verification is still blocking access.")
        return 0

    count = 0
    for url in urls:
        if count >= max_count:
            break
        if url in known_urls:
            continue
        try:
            note = collect_note(page, url, company, keyword)
        except Exception as exc:
            print(f"Skipped note due to collection error: {url} ({exc})")
            continue
        if note.access_status != "ok":
            card = cards_by_url.get(url, {})
            partial = RawNote(
                company_query=company,
                keyword=keyword,
                title=card.get("title") or "详情待人工查看",
                author=card.get("author") or "",
                body=card.get("body") or f"详情页不可见：{note.skip_reason}",
                image_urls=[],
                url=url,
                access_status="search_card_only",
                skip_reason=note.skip_reason,
            )
            append_jsonl(raw_path, partial)
            append_jsonl(DEFAULT_BLOCKED_PATH, note)
            known_urls.add(url)
            count += 1
            print(f"Collected partial {count}/{max_count}: {partial.title} ({note.skip_reason})")
            page.wait_for_timeout(1000)
            continue
        extracted_text = "\n".join([note.title, note.body])
        reason = find_blocked_phrase(extracted_text)
        if reason:
            note.access_status = "blocked"
            note.skip_reason = reason
            card = cards_by_url.get(url, {})
            partial = RawNote(
                company_query=company,
                keyword=keyword,
                title=card.get("title") or "详情待人工查看",
                author=card.get("author") or "",
                body=card.get("body") or f"详情页不可见：{reason}",
                image_urls=[],
                url=url,
                access_status="search_card_only",
                skip_reason=reason,
            )
            append_jsonl(raw_path, partial)
            append_jsonl(DEFAULT_BLOCKED_PATH, note)
            known_urls.add(url)
            count += 1
            print(f"Collected partial {count}/{max_count}: {partial.title} ({reason})")
            page.wait_for_timeout(1000)
            continue
        append_jsonl(raw_path, note)
        known_urls.add(url)
        count += 1
        print(f"Collected {count}/{max_count}: {note.title or url}")
        page.wait_for_timeout(1000)

    page.close()
    return count


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Collect Xiaohongshu interview notes with manual login.")
    parser.add_argument("--config", help="JSON config path.")
    parser.add_argument("--companies", help="Comma-separated company names.")
    parser.add_argument("--roles", help="Comma-separated roles.")
    parser.add_argument("--recruitment-types", help="Comma-separated recruitment types.")
    parser.add_argument("--keywords", help="Comma-separated search keywords.")
    parser.add_argument("--max-per-keyword", type=int, default=None, help="Default: 10.")
    parser.add_argument("--raw-output", default=str(DEFAULT_RAW_PATH), help="Raw JSONL output path.")
    parser.add_argument("--headless", action="store_true", help="Run headless. Avoid this for first login.")
    parser.add_argument("--login-only", action="store_true", help="Open browser for manual login and save state.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = load_config(args.config)
    max_count = args.max_per_keyword or int(config.get("max_per_keyword", 10))
    raw_path = Path(args.raw_output)
    if not raw_path.is_absolute():
        raw_path = SKILL_ROOT / raw_path

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("Playwright is not installed. Install it with:")
        print("  python -m pip install playwright")
        print("  python -m playwright install chromium")
        return 2

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    DEFAULT_PROFILE_DIR.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=str(DEFAULT_PROFILE_DIR),
            headless=args.headless,
            viewport={"width": 1365, "height": 900},
            locale="zh-CN",
        )
        page = context.new_page()
        try:
            page.goto("https://www.xiaohongshu.com/", wait_until="domcontentloaded", timeout=60000)
        except Exception as exc:
            if is_network_block_error(exc):
                print_network_block_help("https://www.xiaohongshu.com/")
                context.close()
                return 3
            raise
        page.wait_for_timeout(3000)
        if args.login_only or looks_blocked(page):
            print("\nPlease scan-login or complete any visible verification in the browser.")
            input("When Xiaohongshu is usable, press Enter here to save login state...")
            context.storage_state(path=str(DEFAULT_STATE_PATH))
            print(f"Saved login state to {DEFAULT_STATE_PATH}")
            if args.login_only:
                context.close()
                return 0
        page.close()

        terms = build_search_terms(args, config)
        total = 0
        for company, keyword in terms:
            total += collect_search_results(context, company, keyword, max_count, raw_path)
            context.storage_state(path=str(DEFAULT_STATE_PATH))

        context.close()
    print(f"\nDone. Newly collected notes: {total}. Raw cache: {raw_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
