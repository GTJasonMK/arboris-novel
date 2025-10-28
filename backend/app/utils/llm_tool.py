# -*- coding: utf-8 -*-
"""OpenAI 兼容型 LLM 工具封装，保持与旧项目一致的接口体验。"""

import os
from dataclasses import asdict, dataclass
from typing import AsyncGenerator, Dict, List, Optional

from openai import AsyncOpenAI


@dataclass
class ChatMessage:
    role: str
    content: str

    def to_dict(self) -> Dict[str, str]:
        return asdict(self)


class LLMClient:
    """异步流式调用封装，兼容 OpenAI SDK。"""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        strict_mode: bool = False,
        simulate_browser: bool = False
    ):
        """
        初始化 LLM 客户端。

        Args:
            api_key: API Key，如果为 None 且非严格模式，会回退到环境变量
            base_url: API Base URL，如果为 None 且非严格模式，会回退到环境变量
            strict_mode: 严格模式，为 True 时不回退到环境变量（用于测试配置）
            simulate_browser: 是否模拟浏览器请求头，用于绕过 Cloudflare 检测
        """
        if strict_mode:
            # 严格模式：不回退到环境变量，必须明确提供参数
            if not api_key:
                raise ValueError("严格模式下必须提供 API Key")
            key = api_key
            url = base_url  # 可以是 None，由 OpenAI SDK 使用默认值
        else:
            # 兼容模式：回退到环境变量
            key = api_key or os.environ.get("OPENAI_API_KEY")
            if not key:
                raise ValueError("缺少 OPENAI_API_KEY 配置，请在数据库或环境变量中补全。")
            url = base_url or os.environ.get("OPENAI_API_BASE")

        # 如果需要模拟浏览器，添加浏览器请求头
        default_headers = {}
        if simulate_browser:
            default_headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
                "Accept": "application/json, text/plain, */*",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                "Accept-Encoding": "gzip, deflate, br",
                "DNT": "1",
                "Connection": "keep-alive",
                "Sec-Fetch-Dest": "empty",
                "Sec-Fetch-Mode": "cors",
                "Sec-Fetch-Site": "same-origin",
            }

        self._client = AsyncOpenAI(
            api_key=key,
            base_url=url,
            default_headers=default_headers if default_headers else None
        )

    async def stream_chat(
        self,
        messages: List[ChatMessage],
        model: Optional[str] = None,
        response_format: Optional[str] = None,
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
        max_tokens: Optional[int] = None,
        timeout: int = 120,
        **kwargs,
    ) -> AsyncGenerator[Dict[str, str], None]:
        payload = {
            "model": model or os.environ.get("MODEL", "gpt-3.5-turbo"),
            "messages": [msg.to_dict() for msg in messages],
            "stream": True,
            **kwargs,
        }
        if response_format:
            payload["response_format"] = {"type": response_format}
        if temperature is not None:
            payload["temperature"] = temperature
        if top_p is not None:
            payload["top_p"] = top_p
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens

        # 使用 with_options() 设置超时，而不是放在payload中
        # 这是OpenAI SDK v1.x的标准做法，兼容newapi等代理服务
        stream = await self._client.with_options(timeout=float(timeout)).chat.completions.create(**payload)
        async for chunk in stream:
            if not chunk.choices:
                continue
            choice = chunk.choices[0]
            yield {
                "content": choice.delta.content,
                "finish_reason": choice.finish_reason,
            }
