#!/usr/bin/env python
"""Semi-automatic Xiaohongshu one-note collector.

Connect to an already-open visible Chrome through CDP, navigate the current
page to Xiaohongshu search, wait for the user to click one note manually, then
extract the visible detail page or popup. The script does not bypass CAPTCHA,
sliders, risk controls, or platform restrictions.
"""

from __future__ import annotations

import argparse
import json
import re
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import quote
from urllib.request import urlopen


SKILL_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = SKILL_ROOT / "data"
OUTPUT_DIR = SKILL_ROOT / "output"
DEFAULT_STATE_PATH = DATA_DIR / "xhs_state.json"
DEFAULT_JSON_PATH = DATA_DIR / "manual_detail_note.json"
DEFAULT_MD_PATH = OUTPUT_DIR / "manual_detail_note.md"

RISK_PHRASES = ["安全限制", "IP存在风险", "300012", "返回首页"]
BLOCKED_PHRASES = RISK_PHRASES + ["当前笔记暂时无法浏览", "扫码查看", "登录后查看", "验证码", "滑块"]
LOGIN_PHRASES = ["登录后查看搜索结果", "手机号登录", "输入手机号", "获取验证码", "小红书或微信扫码"]


@dataclass
class ManualNote:
    keyword: str
    title: str = ""
    author: str = ""
    publish_date: str = ""
    body: str = ""
    image_urls: list[str] = field(default_factory=list)
    url: str = ""
    image_ocr_status: str = "待识别"
    collected_at: float = field(default_factory=time.time)


def resolve_skill_path(path_text: str) -> Path:
    path = Path(path_text)
    if path.is_absolute():
        return path
    return SKILL_ROOT / path


def unique(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        clean = str(item or "").strip()
        if clean and clean not in seen:
            seen.add(clean)
            out.append(clean)
    return out


def page_text(page, timeout: int = 3000) -> str:
    try:
        return page.locator("body").inner_text(timeout=timeout)
    except Exception:
        return ""


def find_phrase(text: str, phrases: list[str]) -> str:
    for phrase in phrases:
        if phrase in text:
            return phrase
    return ""


def has_search_result_link(page) -> bool:
    try:
        return page.locator('a[href*="/explore/"]').count() > 0
    except Exception:
        return False


def wait_for_login_if_needed(page, wait_seconds: int) -> bool:
    text = page_text(page, timeout=5000)
    login_phrase = find_phrase(text, LOGIN_PHRASES)
    if not login_phrase:
        return True

    print(f"Login is required on the search page: {login_phrase}", flush=True)
    print(f"Please scan-login in the opened browser. Waiting up to {wait_seconds} seconds...", flush=True)
    deadline = time.time() + wait_seconds
    while time.time() < deadline:
        text = page_text(page, timeout=3000)
        if find_phrase(text, RISK_PHRASES):
            return True
        if not find_phrase(text, LOGIN_PHRASES) or has_search_result_link(page):
            print("Login prompt appears to be gone or search results are visible.", flush=True)
            return True
        time.sleep(1)
    return False


def save_diagnostics(page, prefix: str, reason: str) -> dict[str, str]:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d_%H%M%S")
    base = DATA_DIR / f"{prefix}_{stamp}"
    html_path = base.with_suffix(".html")
    screenshot_path = base.with_suffix(".png")
    meta_path = base.with_suffix(".json")
    try:
        html_path.write_text(page.content(), encoding="utf-8")
    except Exception:
        html_path.write_text("", encoding="utf-8")
    try:
        page.screenshot(path=str(screenshot_path), full_page=True)
    except Exception:
        screenshot_path.write_bytes(b"")
    meta = {
        "reason": reason,
        "url": page.url,
        "html": str(html_path),
        "screenshot": str(screenshot_path),
    }
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return meta


def safe_goto(page, url: str, prefix: str) -> bool:
    try:
        page.goto(url, wait_until="commit", timeout=60000)
        return True
    except Exception as exc:
        message = str(exc)
        if "Timeout" in message:
            meta = save_diagnostics(page, prefix, "navigation_timeout")
            print(f"Navigation timed out while opening {url}.")
            print(json.dumps(meta, ensure_ascii=False, indent=2))
            return bool(page.url and page.url != "about:blank")
        raise


def looks_like_detail(page) -> bool:
    url = page.url
    if "/explore/" in url or "/discovery/item/" in url:
        return True
    for selector in ["#detail-title", "#detail-desc", "[class*=note-detail]", "[class*=comments-container]"]:
        try:
            if page.locator(selector).count() > 0:
                return True
        except Exception:
            pass
    return False


def page_has_detail_content(page) -> bool:
    text = page_text(page, timeout=1200)
    if find_phrase(text, RISK_PHRASES):
        return True
    signals = 0
    if first_text(page, ["#detail-title", "h1", "[class*=title]"], timeout=800):
        signals += 1
    if first_text(page, ["#detail-desc", "[class*=desc]", "[class*=content]", "article"], timeout=800):
        signals += 1
    if first_text(page, [".author .name", "[class*=author] [class*=name]", "[class*=user] [class*=name]"], timeout=800):
        signals += 1
    if extract_publish_date(text):
        signals += 1
    return signals >= 2


def choose_detail_page(pages_before: list[Any], pages_after: list[Any], initial_urls: dict[int, str]) -> Any | None:
    before_ids = {id(page) for page in pages_before}
    new_pages = [page for page in pages_after if id(page) not in before_ids]
    for page in reversed(new_pages):
        if looks_like_detail(page):
            return page
    for page in reversed(pages_after):
        old_url = initial_urls.get(id(page), "")
        url_changed = bool(old_url and page.url != old_url)
        if looks_like_detail(page):
            return page
    return None


def wait_for_detail_page(context, pages_before: list[Any], initial_urls: dict[int, str], wait_seconds: int) -> Any | None:
    deadline = time.time() + wait_seconds
    while time.time() < deadline:
        for candidate in context.pages:
            try:
                candidate.bring_to_front()
            except Exception:
                pass
            text = page_text(candidate, timeout=800)
            risk = find_phrase(text, RISK_PHRASES)
            if risk:
                meta = save_diagnostics(candidate, "manual_detail_risk", risk)
                raise RuntimeError(f"Risk page detected: {risk}. Diagnostics: {meta}")
        detail_page = choose_detail_page(pages_before, context.pages, initial_urls)
        if detail_page is not None:
            return detail_page
        time.sleep(1)
    return None


def first_text(page, selectors: list[str], timeout: int = 1800) -> str:
    for selector in selectors:
        try:
            text = page.locator(selector).first.inner_text(timeout=timeout).strip()
            if text:
                return text
        except Exception:
            pass
    return ""


def extract_publish_date(text: str) -> str:
    patterns = [
        r"\d{4}[-/.年]\d{1,2}[-/.月]\d{1,2}日?",
        r"\d{1,2}[-/.月]\d{1,2}日?",
        r"(?:编辑于|发布于)\s*\S+",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(0)
    return ""


def extract_note(page, keyword: str) -> ManualNote:
    text = page_text(page, timeout=5000)
    reason = find_phrase(text, RISK_PHRASES)
    if reason:
        meta = save_diagnostics(page, "manual_detail_risk", reason)
        raise RuntimeError(f"Risk page detected: {reason}. Diagnostics: {meta}")

    title = first_text(page, ["#detail-title", "h1", "[class*=title]"])
    body = first_text(page, ["#detail-desc", "[class*=desc]", "[class*=content]", "article"])
    author = first_text(page, [".author .name", "[class*=author] [class*=name]", "[class*=user] [class*=name]"])
    publish_date = extract_publish_date(text)

    image_urls: list[str] = []
    try:
        image_urls = page.locator("img").evaluate_all(
            """imgs => imgs
              .map(img => img.currentSrc || img.src)
              .filter(Boolean)
              .filter(src => !src.toLowerCase().includes('avatar'))"""
        )
    except Exception:
        pass

    blocked = find_phrase("\n".join([title, body, text[:1000]]), BLOCKED_PHRASES)
    if blocked:
        meta = save_diagnostics(page, "manual_detail_blocked", blocked)
        raise RuntimeError(f"Blocked or inaccessible page detected: {blocked}. Diagnostics: {meta}")

    return ManualNote(
        keyword=keyword,
        title=title or "无标题",
        author=author or "未知",
        publish_date=publish_date or "未知",
        body=body or text[:3000],
        image_urls=unique(image_urls)[:30],
        url=page.url,
    )


def save_note_json(note: ManualNote, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(note), ensure_ascii=False, indent=2), encoding="utf-8")


def render_markdown(note: ManualNote) -> str:
    lines = [
        "# 小红书手动点击面经采集",
        "",
        f"## {note.title}",
        "",
        f"* 搜索关键词：{note.keyword}",
        f"* 发布日期：{note.publish_date}",
        f"* 作者：{note.author}",
        f"* 原文链接：{note.url}",
        "",
        "### 面经内容",
        "",
        note.body or "正文未采集到。",
        "",
        "### 图片文字识别",
        "",
        "待识别" if note.image_urls else "无图片",
        "",
    ]
    if note.image_urls:
        lines.extend(["### 图片链接", ""])
        for image_url in note.image_urls:
            lines.append(f"- {image_url}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def save_note_markdown(note: ManualNote, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_markdown(note), encoding="utf-8")


def run_self_test(json_path: Path, md_path: Path) -> int:
    note = ManualNote(
        keyword="字节跳动面经",
        title="字节后端暑期实习一面复盘",
        author="手动点击测试作者",
        publish_date="2026-03-18",
        body="一面问了 Redis 缓存、MySQL 索引、项目限流和一道算法题。",
        image_urls=["https://example.com/xhs/manual-image.jpg"],
        url="https://www.xiaohongshu.com/explore/manual-test",
    )
    save_note_json(note, json_path)
    save_note_markdown(note, md_path)
    markdown = md_path.read_text(encoding="utf-8")
    assert "字节后端暑期实习一面复盘" in markdown
    assert "待识别" in markdown
    print(f"Self test passed -> {json_path}, {md_path}")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Semi-automatic one-note Xiaohongshu collector.")
    parser.add_argument("--keyword", default="字节跳动面经", help="Search keyword. Default: 字节跳动面经.")
    parser.add_argument("--json-output", default=str(DEFAULT_JSON_PATH), help="Raw JSON output path.")
    parser.add_argument("--markdown-output", default=str(DEFAULT_MD_PATH), help="Simple Markdown output path.")
    parser.add_argument("--cdp-url", default="http://127.0.0.1:9222", help="Chrome DevTools Protocol URL for the already-open visible Chrome.")
    parser.add_argument("--cdp-timeout-ms", type=int, default=15000, help="How long to wait when connecting to visible Chrome.")
    parser.add_argument("--login-wait-seconds", type=int, default=120, help="How long to wait for manual scan-login if the search page asks for login.")
    parser.add_argument("--detail-wait-seconds", type=int, default=120, help="How long to poll for the manually clicked note detail page.")
    parser.add_argument("--self-test", action="store_true", help="Generate deterministic sample JSON/Markdown without launching a browser.")
    return parser.parse_args()


def check_cdp_endpoint(cdp_url: str) -> tuple[bool, str]:
    try:
        with urlopen(cdp_url.rstrip("/") + "/json/version", timeout=3) as response:
            payload = json.loads(response.read().decode("utf-8"))
        return True, payload.get("webSocketDebuggerUrl", "")
    except Exception as exc:
        return False, str(exc)


def connect_visible_chrome(playwright, cdp_url: str, timeout_ms: int):
    print(f"Connecting to visible Chrome over CDP: {cdp_url}", flush=True)
    reachable, detail = check_cdp_endpoint(cdp_url)
    if reachable:
        print(f"CDP endpoint is reachable. WebSocket: {detail}", flush=True)
    else:
        print(f"CDP endpoint is not reachable: {detail}", flush=True)
        print("Please start visible Chrome first:", flush=True)
        print("  powershell -ExecutionPolicy Bypass -File scripts/open_visible_chrome.ps1 -Port 9222", flush=True)
        raise RuntimeError("Chrome DevTools endpoint is not reachable.")

    try:
        browser = playwright.chromium.connect_over_cdp(cdp_url, timeout=timeout_ms)
    except Exception as exc:
        print(f"Chrome DevTools is reachable, but Playwright CDP handshake failed: {exc}", flush=True)
        print("Close extra Chrome debugging sessions or retry with a larger --cdp-timeout-ms, for example 30000.", flush=True)
        raise

    contexts = browser.contexts
    if not contexts:
        raise RuntimeError("Connected to Chrome, but no existing browser context was found.")

    context = contexts[0]
    pages = context.pages
    print(f"Connected page count: {len(pages)}", flush=True)
    for index, existing_page in enumerate(pages, start=1):
        print(f"Page {index}: {existing_page.url}", flush=True)
    print(f"Using browser context: index=1 id={id(context)}", flush=True)

    if not pages:
        raise RuntimeError("Connected to Chrome, but no existing page was found. Open a tab in Chrome and rerun.")

    page = pages[-1]
    page.bring_to_front()
    return browser, context, page


def save_state_only(context) -> None:
    try:
        context.storage_state(path=str(DEFAULT_STATE_PATH))
    except Exception:
        pass


def main() -> int:
    args = parse_args()
    json_path = resolve_skill_path(args.json_output)
    md_path = resolve_skill_path(args.markdown_output)
    if args.self_test:
        return run_self_test(json_path, md_path)

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("Playwright is not installed. Install it with:")
        print("  python -m pip install -r requirements.txt")
        print("  python -m playwright install chromium")
        return 2

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    search_url = f"https://www.xiaohongshu.com/search_result?keyword={quote(args.keyword)}"

    with sync_playwright() as p:
        try:
            browser, context, page = connect_visible_chrome(p, args.cdp_url, args.cdp_timeout_ms)
        except Exception as exc:
            print(f"Could not connect to visible Chrome: {exc}", flush=True)
            return 7

        print(f"Opening search page: {search_url}", flush=True)
        if not safe_goto(page, search_url, "manual_search_timeout"):
            save_state_only(context)
            return 3
        page.wait_for_timeout(5000)
        try:
            latest = page.get_by_text(chr(26368) + chr(26032), exact=True)
            if latest.count() > 0:
                latest.first.click(timeout=2000)
                page.wait_for_timeout(1200)
        except Exception:
            pass

        text = page_text(page, timeout=5000)
        risk = find_phrase(text, RISK_PHRASES)
        if risk:
            meta = save_diagnostics(page, "manual_search_risk", risk)
            print(f"Stopped because the search page triggered a risk page: {risk}")
            print(json.dumps(meta, ensure_ascii=False, indent=2))
            save_state_only(context)
            return 4

        if not wait_for_login_if_needed(page, args.login_wait_seconds):
            meta = save_diagnostics(page, "manual_search_login_timeout", "login_timeout")
            print("Login prompt did not disappear before timeout.")
            print(json.dumps(meta, ensure_ascii=False, indent=2))
            save_state_only(context)
            return 8

        text = page_text(page, timeout=5000)
        risk = find_phrase(text, RISK_PHRASES)
        if risk:
            meta = save_diagnostics(page, "manual_search_risk", risk)
            print(f"Stopped because the search page triggered a risk page after login wait: {risk}")
            print(json.dumps(meta, ensure_ascii=False, indent=2))
            save_state_only(context)
            return 4

        print("\nSearch page is open.")
        print("Please manually click exactly one target note in the browser.")
        print("If a new tab opens, leave it open. If the same tab changes, keep it there.")
        pages_before = list(context.pages)
        initial_urls = {id(existing_page): existing_page.url for existing_page in pages_before}
        print(f"Polling up to {args.detail_wait_seconds} seconds for a detail page. No terminal input is needed.", flush=True)
        try:
            detail_page = wait_for_detail_page(context, pages_before, initial_urls, args.detail_wait_seconds)
        except RuntimeError as exc:
            print(str(exc))
            save_state_only(context)
            return 6
        if detail_page is None:
            meta = save_diagnostics(page, "manual_no_detail", "detail_page_not_detected")
            print("Could not detect a note detail page after your manual click.")
            print(json.dumps(meta, ensure_ascii=False, indent=2))
            save_state_only(context)
            return 5

        detail_page.bring_to_front()
        detail_page.wait_for_timeout(2500)
        try:
            note = extract_note(detail_page, args.keyword)
        except RuntimeError as exc:
            print(str(exc))
            save_state_only(context)
            return 6

        save_note_json(note, json_path)
        save_note_markdown(note, md_path)
        save_state_only(context)
        print(f"Saved JSON -> {json_path}")
        print(f"Saved Markdown -> {md_path}")
        print("Chrome was left open.", flush=True)
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
