import logging
import os
from typing import Any, Dict, List, Optional

import httpx
from fastapi import HTTPException, status
from openai import APIConnectionError, APITimeoutError, AsyncOpenAI, InternalServerError

from ..core.config import settings
from ..repositories.llm_config_repository import LLMConfigRepository
from ..repositories.system_config_repository import SystemConfigRepository
from ..repositories.user_repository import UserRepository
from ..services.admin_setting_service import AdminSettingService
from ..services.prompt_service import PromptService
from ..services.usage_service import UsageService
from ..utils.llm_tool import ChatMessage, LLMClient

logger = logging.getLogger(__name__)

try:  # pragma: no cover - 运行环境未安装时兼容
    from ollama import AsyncClient as OllamaAsyncClient
except ImportError:  # pragma: no cover - Ollama 为可选依赖
    OllamaAsyncClient = None


class LLMService:
    """封装与大模型交互的所有逻辑，包括配额控制与配置选择。"""

    def __init__(self, session):
        self.session = session
        self.llm_repo = LLMConfigRepository(session)
        self.system_config_repo = SystemConfigRepository(session)
        self.user_repo = UserRepository(session)
        self.admin_setting_service = AdminSettingService(session)
        self.usage_service = UsageService(session)
        self._embedding_dimensions: Dict[str, int] = {}

    async def get_llm_response(
        self,
        system_prompt: str,
        conversation_history: List[Dict[str, str]],
        *,
        temperature: float = 0.7,
        user_id: Optional[int] = None,
        timeout: float = 300.0,
        response_format: Optional[str] = "json_object",
        max_tokens: Optional[int] = None,
        skip_usage_tracking: bool = False,
        skip_daily_limit_check: bool = False,
        cached_config: Optional[Dict[str, Optional[str]]] = None,
    ) -> str:
        messages = [{"role": "system", "content": system_prompt}, *conversation_history]
        return await self._stream_and_collect(
            messages,
            temperature=temperature,
            user_id=user_id,
            timeout=timeout,
            response_format=response_format,
            max_tokens=max_tokens,
            skip_usage_tracking=skip_usage_tracking,
            skip_daily_limit_check=skip_daily_limit_check,
            cached_config=cached_config,
        )

    async def get_summary(
        self,
        chapter_content: str,
        *,
        temperature: float = 0.2,
        user_id: Optional[int] = None,
        timeout: float = 180.0,
        system_prompt: Optional[str] = None,
    ) -> str:
        if not system_prompt:
            prompt_service = PromptService(self.session)
            system_prompt = await prompt_service.get_prompt("extraction")
        if not system_prompt:
            raise HTTPException(status_code=500, detail="未配置摘要提示词")
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": chapter_content},
        ]
        return await self._stream_and_collect(messages, temperature=temperature, user_id=user_id, timeout=timeout)

    async def _stream_and_collect(
        self,
        messages: List[Dict[str, str]],
        *,
        temperature: float,
        user_id: Optional[int],
        timeout: float,
        response_format: Optional[str] = None,
        max_tokens: Optional[int] = None,
        max_retries: int = 2,
        skip_usage_tracking: bool = False,
        skip_daily_limit_check: bool = False,
        cached_config: Optional[Dict[str, Optional[str]]] = None,
    ) -> str:
        """流式收集 LLM 响应，支持自动重试网络错误

        Args:
            max_retries: 最大重试次数（默认2次，总共最多3次尝试）
            skip_usage_tracking: 跳过 API 请求计数（用于并行模式）
            skip_daily_limit_check: 跳过每日限额检查（用于并行模式）
            cached_config: 缓存的 LLM 配置（用于并行模式，避免并发数据库查询）
        """
        import asyncio
        task_id = id(asyncio.current_task())
        logger.info("[Task %s] _stream_and_collect 开始 (cached_config=%s)", task_id, bool(cached_config))

        # 使用缓存配置或实时查询配置
        if cached_config:
            config = cached_config
            logger.info("[Task %s] 使用缓存配置，跳过数据库查询", task_id)
        else:
            logger.info("[Task %s] 开始调用 _resolve_llm_config", task_id)
            config = await self._resolve_llm_config(user_id, skip_daily_limit_check=skip_daily_limit_check)
            logger.info("[Task %s] _resolve_llm_config 完成", task_id)

        last_error: Optional[Exception] = None

        for attempt in range(max_retries + 1):
            try:
                # 使用浏览器头模拟，避免被 Cloudflare 等防护拦截（与测试配置保持一致）
                client = LLMClient(
                    api_key=config["api_key"],
                    base_url=config.get("base_url"),
                    simulate_browser=True
                )
                chat_messages = [ChatMessage(role=msg["role"], content=msg["content"]) for msg in messages]

                full_response = ""
                finish_reason = None

                if attempt > 0:
                    logger.warning(
                        "Retrying LLM request: attempt=%d/%d model=%s user_id=%s",
                        attempt + 1,
                        max_retries + 1,
                        config.get("model"),
                        user_id,
                    )
                else:
                    logger.info(
                        "Streaming LLM response: model=%s user_id=%s messages=%d max_tokens=%s",
                        config.get("model"),
                        user_id,
                        len(messages),
                        max_tokens,
                    )

                async for part in client.stream_chat(
                    messages=chat_messages,
                    model=config.get("model"),
                    temperature=temperature,
                    timeout=int(timeout),
                    response_format=response_format,
                    max_tokens=max_tokens,
                ):
                    if part.get("content"):
                        full_response += part["content"]
                    if part.get("finish_reason"):
                        finish_reason = part["finish_reason"]

                # 成功完成，跳出重试循环
                logger.debug(
                    "LLM response collected: model=%s user_id=%s finish_reason=%s preview=%s",
                    config.get("model"),
                    user_id,
                    finish_reason,
                    full_response[:500],
                )

                if finish_reason == "length":
                    logger.warning(
                        "LLM response truncated: model=%s user_id=%s",
                        config.get("model"),
                        user_id,
                    )
                    raise HTTPException(status_code=500, detail="AI 响应被截断，请缩短输入或调整参数")

                if not full_response:
                    logger.error(
                        "LLM returned empty response: model=%s user_id=%s",
                        config.get("model"),
                        user_id,
                    )
                    raise HTTPException(status_code=500, detail="AI 未返回有效内容")

                # 仅在非跳过模式下更新使用量统计（避免并发 session 冲突）
                if not skip_usage_tracking:
                    await self.usage_service.increment("api_request_count")

                logger.info(
                    "LLM response success: model=%s user_id=%s chars=%d attempts=%d",
                    config.get("model"),
                    user_id,
                    len(full_response),
                    attempt + 1,
                )
                return full_response

            except InternalServerError as exc:
                detail = "AI 服务内部错误，请稍后重试"
                response = getattr(exc, "response", None)
                if response is not None:
                    try:
                        payload = response.json()
                        error_data = payload.get("error", {}) if isinstance(payload, dict) else {}
                        detail = error_data.get("message_zh") or error_data.get("message") or detail
                    except Exception:
                        detail = str(exc) or detail
                else:
                    detail = str(exc) or detail
                logger.error(
                    "LLM stream internal error: model=%s user_id=%s attempt=%d/%d detail=%s",
                    config.get("model"),
                    user_id,
                    attempt + 1,
                    max_retries + 1,
                    detail,
                    exc_info=exc,
                )
                # 内部错误不重试，直接抛出
                raise HTTPException(status_code=503, detail=detail)

            except (httpx.RemoteProtocolError, httpx.ReadTimeout, APIConnectionError, APITimeoutError) as exc:
                last_error = exc

                if isinstance(exc, httpx.RemoteProtocolError):
                    detail = "AI 服务连接被意外中断"
                elif isinstance(exc, (httpx.ReadTimeout, APITimeoutError)):
                    detail = "AI 服务响应超时"
                else:
                    detail = "无法连接到 AI 服务"

                logger.error(
                    "LLM stream failed: model=%s user_id=%s attempt=%d/%d detail=%s",
                    config.get("model"),
                    user_id,
                    attempt + 1,
                    max_retries + 1,
                    detail,
                    exc_info=exc,
                )

                # 如果还有重试机会，继续重试
                if attempt < max_retries:
                    import asyncio
                    # 指数退避：第1次重试等待2秒，第2次等待4秒
                    wait_time = 2 ** (attempt + 1)
                    logger.info("Waiting %d seconds before retry...", wait_time)
                    await asyncio.sleep(wait_time)
                    continue

                # 已达到最大重试次数，抛出错误
                retry_hint = f"（已尝试 {max_retries + 1} 次）"
                raise HTTPException(
                    status_code=503,
                    detail=f"{detail}，请稍后重试 {retry_hint}"
                ) from exc

        # 理论上不应该到达这里，但为了代码完整性保留
        if last_error:
            raise HTTPException(
                status_code=503,
                detail="AI 服务连接失败，请检查网络或稍后重试"
            ) from last_error

        raise HTTPException(status_code=500, detail="未知错误")

    async def _resolve_llm_config(self, user_id: Optional[int], skip_daily_limit_check: bool = False) -> Dict[str, Optional[str]]:
        import asyncio
        task_id = id(asyncio.current_task())
        logger.info("[Task %s] _resolve_llm_config 开始 (user_id=%s, skip_daily_limit_check=%s)", task_id, user_id, skip_daily_limit_check)

        if user_id:
            logger.info("[Task %s] 开始查询用户 LLM 配置: user_id=%s", task_id, user_id)
            try:
                # 使用激活的配置而不是第一个配置
                config = await self.llm_repo.get_active_config(user_id)
                logger.info("[Task %s] 用户 LLM 配置查询完成", task_id)
            except Exception as exc:
                logger.error("[Task %s] 查询用户 LLM 配置失败: %s", task_id, exc, exc_info=True)
                raise

            if config and config.llm_provider_api_key:
                logger.info("[Task %s] 使用用户自定义 LLM 配置", task_id)
                return {
                    "api_key": config.llm_provider_api_key,
                    "base_url": config.llm_provider_url,
                    "model": config.llm_provider_model,
                }

        # 检查每日使用次数限制（仅在非跳过模式下）
        if user_id and not skip_daily_limit_check:
            logger.info("[Task %s] 开始执行 daily limit 检查", task_id)
            await self._enforce_daily_limit(user_id)
            logger.info("[Task %s] daily limit 检查完成", task_id)

        api_key = await self._get_config_value("llm.api_key")
        base_url = await self._get_config_value("llm.base_url")
        model = await self._get_config_value("llm.model")

        if not api_key:
            raise HTTPException(status_code=500, detail="未配置默认 LLM API Key")

        return {"api_key": api_key, "base_url": base_url, "model": model}

    async def get_embedding(
        self,
        text: str,
        *,
        user_id: Optional[int] = None,
        model: Optional[str] = None,
    ) -> List[float]:
        """生成文本向量，用于章节 RAG 检索，支持 openai 与 ollama 双提供方。"""
        provider = settings.embedding_provider
        target_model = model or (
            settings.ollama_embedding_model if provider == "ollama" else settings.embedding_model
        )

        if provider == "ollama":
            if OllamaAsyncClient is None:
                logger.error("未安装 ollama 依赖，无法调用本地嵌入模型。")
                raise HTTPException(status_code=500, detail="缺少 Ollama 依赖，请先安装 ollama 包。")

            base_url_any = settings.ollama_embedding_base_url or settings.embedding_base_url
            base_url = str(base_url_any) if base_url_any else None
            client = OllamaAsyncClient(host=base_url)
            try:
                response = await client.embeddings(model=target_model, prompt=text)
            except Exception as exc:  # pragma: no cover - 本地服务调用失败
                logger.warning(
                    "Ollama 嵌入请求失败: model=%s error=%s",
                    target_model,
                    exc,
                )
                return []
            embedding: Optional[List[float]]
            if isinstance(response, dict):
                embedding = response.get("embedding")
            else:
                embedding = getattr(response, "embedding", None)
            if not embedding:
                logger.warning("Ollama 返回空向量: model=%s", target_model)
                return []
            if not isinstance(embedding, list):
                embedding = list(embedding)
        else:
            config = await self._resolve_llm_config(user_id)
            api_key = settings.embedding_api_key or config["api_key"]
            base_url_setting = settings.embedding_base_url or config.get("base_url")
            base_url = str(base_url_setting) if base_url_setting else None
            client = AsyncOpenAI(api_key=api_key, base_url=base_url)
            try:
                response = await client.embeddings.create(
                    input=text,
                    model=target_model,
                )
            except Exception as exc:  # pragma: no cover - 网络或鉴权失败
                logger.warning(
                    "OpenAI 嵌入请求失败: model=%s user_id=%s error=%s",
                    target_model,
                    user_id,
                    exc,
                )
                return []
            if not response.data:
                logger.warning("OpenAI 嵌入请求返回空数据: model=%s user_id=%s", target_model, user_id)
                return []
            embedding = response.data[0].embedding

        if not isinstance(embedding, list):
            embedding = list(embedding)

        dimension = len(embedding)
        if not dimension and settings.embedding_model_vector_size:
            dimension = settings.embedding_model_vector_size
        if dimension:
            self._embedding_dimensions[target_model] = dimension
        return embedding

    def get_embedding_dimension(self, model: Optional[str] = None) -> Optional[int]:
        """获取嵌入向量维度，优先返回缓存结果，其次读取配置。"""
        target_model = model or (
            settings.ollama_embedding_model if settings.embedding_provider == "ollama" else settings.embedding_model
        )
        if target_model in self._embedding_dimensions:
            return self._embedding_dimensions[target_model]
        return settings.embedding_model_vector_size

    async def _enforce_daily_limit(self, user_id: int) -> None:
        limit_str = await self.admin_setting_service.get("daily_request_limit", "100")
        limit = int(limit_str or 10)
        used = await self.user_repo.get_daily_request(user_id)
        if used >= limit:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="今日请求次数已达上限，请明日再试或设置自定义 API Key。",
            )
        await self.user_repo.increment_daily_request(user_id)
        await self.session.commit()

    async def _get_config_value(self, key: str) -> Optional[str]:
        record = await self.system_config_repo.get_by_key(key)
        if record:
            return record.value
        # 兼容环境变量，首次迁移时无需立即写入数据库
        env_key = key.upper().replace(".", "_")
        return os.getenv(env_key)
