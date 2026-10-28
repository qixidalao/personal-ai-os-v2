"""
搜索工具 — 仅保留 Bing，快速稳定
"""
from __future__ import annotations

import re
from html import unescape
from urllib.parse import quote, unquote

import httpx
from tools import ToolRegistry


UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 PersonalAIOS/2.0"


def _strip_tags(value: str) -> str:
    value = re.sub(r"<script[\s\S]*?</script>", " ", value, flags=re.I)
    value = re.sub(r"<style[\s\S]*?</style>", " ", value, flags=re.I)
    value = re.sub(r"<[^>]+>", " ", value)
    value = unescape(value)
    return re.sub(r"\s+", " ", value).strip()


def _http_get(url: str, timeout: int = 2) -> httpx.Response:
    with httpx.Client(timeout=timeout, follow_redirects=True, trust_env=False, headers={"User-Agent": UA}) as client:
        return client.get(url)


@ToolRegistry.register("web_search", "执行网络搜索", "search")
def web_search(query: str, max_results: int = 5) -> list:
    """Bing 搜索，2s 超时，过滤广告/导航结果"""
    q = (query or "").strip()
    if not q:
        return [{"error": "搜索关键词不能为空"}]
    max_results = max(1, min(int(max_results or 5), 10))

    bing_url = f"https://www.bing.com/search?q={quote(q)}"
    try:
        resp = _http_get(bing_url, timeout=2)
        resp.raise_for_status()
    except Exception as exc:
        return [{"title": f"搜索失败: {exc}", "url": bing_url, "snippet": ""}]

    results = []
    for block in re.findall(r'<li class="b_algo"[\s\S]*?</li>', resp.text, re.I):
        if len(results) >= max_results:
            break
        m = re.search(r'<a[^>]+href="([^"]+)"[^>]*>([\s\S]*?)</a>', block, re.I)
        if not m:
            continue
        url, title = m.groups()
        title = _strip_tags(title)
        snippet_match = re.search(r'<p[^>]*>([\s\S]*?)</p>', block, re.I)
        snippet = _strip_tags(snippet_match.group(1)) if snippet_match else ""
        if not url or "bing.com" in url.lower() or "microsoft.com" in url.lower():
            continue
        if title or url:
            results.append({"title": title or url, "url": unescape(url), "snippet": snippet})
    return results[:max_results]
