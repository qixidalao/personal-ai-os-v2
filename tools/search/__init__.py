"""
搜索工具
"""
from __future__ import annotations

import re
from html import unescape
from urllib.parse import quote, urlparse, parse_qs, unquote

import httpx
from tools import ToolRegistry


UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 PersonalAIOS/2.0"


def _flatten_duckduckgo_topics(topics, max_results: int) -> list[dict]:
    results: list[dict] = []
    for topic in topics or []:
        if len(results) >= max_results:
            break
        if not isinstance(topic, dict):
            continue
        if "Topics" in topic:
            results.extend(_flatten_duckduckgo_topics(topic.get("Topics"), max_results - len(results)))
            continue
        text = topic.get("Text") or topic.get("Result") or ""
        url = topic.get("FirstURL") or ""
        if text or url:
            results.append({"title": str(text)[:220], "url": str(url), "snippet": str(text)[:500]})
    return results[:max_results]


def _strip_tags(value: str) -> str:
    value = re.sub(r"<script[\s\S]*?</script>", " ", value, flags=re.I)
    value = re.sub(r"<style[\s\S]*?</style>", " ", value, flags=re.I)
    value = re.sub(r"<[^>]+>", " ", value)
    value = unescape(value)
    return re.sub(r"\s+", " ", value).strip()


def _ddg_real_url(href: str) -> str:
    href = unescape(href)
    parsed = urlparse(href)
    if "duckduckgo.com" in parsed.netloc and parsed.path.startswith("/l/"):
        uddg = parse_qs(parsed.query).get("uddg", [""])[0]
        if uddg:
            return unquote(uddg)
    return href


def _parse_duckduckgo_html(html: str, max_results: int) -> list[dict]:
    results: list[dict] = []
    # DuckDuckGo html 结果大致为：<a rel="nofollow" class="result__a" href="...">title</a>
    for match in re.finditer(r'<a[^>]+class="[^"]*result__a[^"]*"[^>]+href="([^"]+)"[^>]*>([\s\S]*?)</a>', html, re.I):
        if len(results) >= max_results:
            break
        href, title = match.groups()
        title = _strip_tags(title)
        url = _ddg_real_url(href)
        if title or url:
            results.append({"title": title or url, "url": url, "snippet": ""})
    return results


def _parse_bing_html(html: str, max_results: int) -> list[dict]:
    results: list[dict] = []
    for block in re.findall(r'<li class="b_algo"[\s\S]*?</li>', html, re.I):
        if len(results) >= max_results:
            break
        m = re.search(r'<a[^>]+href="([^"]+)"[^>]*>([\s\S]*?)</a>', block, re.I)
        if not m:
            continue
        url, title = m.groups()
        title = _strip_tags(title)
        snippet_match = re.search(r'<p[^>]*>([\s\S]*?)</p>', block, re.I)
        snippet = _strip_tags(snippet_match.group(1)) if snippet_match else ""
        if title or url:
            results.append({"title": title or url, "url": unescape(url), "snippet": snippet})
    return results


def _http_get(url: str, timeout: int = 3) -> httpx.Response:
    last_exc: Exception | None = None
    # 先直连，再走环境代理。某些接口直连慢，某些代理 502，两个都试。
    for trust_env in (False, True):
        try:
            with httpx.Client(timeout=timeout, follow_redirects=True, trust_env=trust_env, headers={"User-Agent": UA}) as client:
                return client.get(url)
        except Exception as exc:
            last_exc = exc
    assert last_exc is not None
    raise last_exc


@ToolRegistry.register("web_search", "执行网络搜索", "search")
def web_search(query: str, max_results: int = 5) -> list:
    """多级兜底网页搜索：DuckDuckGo API → DuckDuckGo HTML → Bing HTML → 搜索入口。"""
    q = (query or "").strip()
    if not q:
        return [{"error": "搜索关键词不能为空"}]

    max_results = max(1, min(int(max_results or 5), 10))
    errors: list[str] = []

    # 1) DuckDuckGo Instant Answer API
    api_url = f"https://api.duckduckgo.com/?q={quote(q)}&format=json&no_html=1&skip_disambig=1"
    try:
        resp = _http_get(api_url, timeout=3)
        resp.raise_for_status()
        data = resp.json()
        results: list[dict] = []
        abstract = data.get("AbstractText") or data.get("Abstract")
        abstract_url = data.get("AbstractURL")
        heading = data.get("Heading") or q
        if abstract or abstract_url:
            results.append({"title": heading, "url": abstract_url or "", "snippet": abstract or ""})
        results.extend(_flatten_duckduckgo_topics(data.get("RelatedTopics"), max_results - len(results)))
        if results:
            return results[:max_results]
    except Exception as exc:
        errors.append(f"duckduckgo_api: {exc}")

    # 2) DuckDuckGo HTML
    ddg_html_url = f"https://duckduckgo.com/html/?q={quote(q)}"
    try:
        resp = _http_get(ddg_html_url, timeout=3)
        resp.raise_for_status()
        results = _parse_duckduckgo_html(resp.text, max_results)
        if results:
            return results[:max_results]
    except Exception as exc:
        errors.append(f"duckduckgo_html: {exc}")

    # 3) Bing HTML
    bing_url = f"https://www.bing.com/search?q={quote(q)}"
    try:
        resp = _http_get(bing_url, timeout=3)
        resp.raise_for_status()
        results = _parse_bing_html(resp.text, max_results)
        if results:
            return results[:max_results]
    except Exception as exc:
        errors.append(f"bing_html: {exc}")

    # 4) 最终可用兜底：返回搜索入口，不抛工具失败
    return [{
        "title": f"搜索入口：{q}",
        "url": f"https://duckduckgo.com/?q={quote(q)}",
        "snippet": "搜索引擎接口暂时没有返回可解析结果，已提供可点击搜索入口。" + ("；" + " | ".join(errors[-3:]) if errors else ""),
    }]
