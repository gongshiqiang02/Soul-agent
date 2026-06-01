"""Web请求工具"""
import json
import urllib.request
import urllib.error
from urllib.parse import urlencode

from soul_agent.tools.base import Tool, ToolResult

MAX_RESPONSE_LENGTH = 10000


class WebRequestTool(Tool):
    name = "web_request"
    description = "发送HTTP请求（支持GET和POST）"
    parameters = {
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "请求的URL",
            },
            "method": {
                "type": "string",
                "enum": ["GET", "POST"],
                "description": "HTTP方法，默认 GET",
                "default": "GET",
            },
            "headers": {
                "type": "object",
                "description": "请求头（键值对）",
                "additionalProperties": {"type": "string"},
            },
            "body": {
                "type": "string",
                "description": "请求体（POST时使用）",
            },
        },
        "required": ["url"],
    }

    async def execute(self, **kwargs) -> ToolResult:
        url = kwargs["url"]
        method = kwargs.get("method", "GET").upper()
        headers = kwargs.get("headers", {})
        body = kwargs.get("body")

        try:
            data = None
            if body is not None:
                data = body.encode("utf-8")
                if "Content-Type" not in headers:
                    headers["Content-Type"] = "application/json"

            req = urllib.request.Request(url, data=data, headers=headers, method=method)
            with urllib.request.urlopen(req, timeout=30) as response:
                status = response.status
                content_type = response.headers.get("Content-Type", "")
                body_bytes = response.read()

            body_text = body_bytes.decode("utf-8", errors="replace")
            if len(body_text) > MAX_RESPONSE_LENGTH:
                body_text = body_text[:MAX_RESPONSE_LENGTH] + "\n...(响应被截断)"

            output = f"状态码: {status}\nContent-Type: {content_type}\n\n{body_text}"
            return ToolResult(success=True, output=output)

        except urllib.error.HTTPError as e:
            error_body = ""
            try:
                error_body = e.read().decode("utf-8", errors="replace")
                if len(error_body) > MAX_RESPONSE_LENGTH:
                    error_body = error_body[:MAX_RESPONSE_LENGTH] + "\n...(响应被截断)"
            except Exception:
                pass
            return ToolResult(
                success=False,
                output=error_body,
                error=f"HTTP {e.code}: {e.reason}",
            )
        except urllib.error.URLError as e:
            return ToolResult(success=False, output="", error=f"请求失败: {e.reason}")
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))
