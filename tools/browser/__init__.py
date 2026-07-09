"""
浏览器工具
"""
import httpx
from tools import ToolRegistry


@ToolRegistry.register("browser_open", "打开网页获取内容", "browser")
def browser_open(url: str, timeout: int = 30) -> dict:
    try:
        response = httpx.get(url, timeout=timeout, follow_redirects=True)
        return {
            "url": str(response.url),
            "status_code": response.status_code,
            "content": response.text[:10000],  # 限制内容长度
            "headers": dict(response.headers),
        }
    except Exception as e:
        return {"error": str(e)}
