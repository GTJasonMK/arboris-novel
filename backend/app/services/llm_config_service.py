import logging
import time
from datetime import datetime, timezone
from typing import Optional

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import LLMConfig
from ..repositories.llm_config_repository import LLMConfigRepository
from ..schemas.llm_config import LLMConfigCreate, LLMConfigRead, LLMConfigUpdate, LLMConfigTestResponse
from ..utils.llm_tool import ChatMessage, LLMClient

logger = logging.getLogger(__name__)


class LLMConfigService:
    """用户自定义 LLM 配置服务，支持多配置管理和测试。"""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = LLMConfigRepository(session)

    async def list_configs(self, user_id: int) -> list[LLMConfigRead]:
        """获取用户的所有LLM配置列表。"""
        configs = await self.repo.list_by_user(user_id)
        return [LLMConfigRead.from_orm_with_mask(config) for config in configs]

    async def get_config(self, config_id: int, user_id: int) -> LLMConfigRead:
        """获取指定ID的配置。"""
        config = await self.repo.get_by_id(config_id, user_id)
        if not config:
            raise HTTPException(status_code=404, detail="配置不存在或无权访问")
        return LLMConfigRead.from_orm_with_mask(config)

    async def get_active_config(self, user_id: int) -> Optional[LLMConfigRead]:
        """获取用户当前激活的配置。"""
        config = await self.repo.get_active_config(user_id)
        return LLMConfigRead.from_orm_with_mask(config) if config else None

    async def create_config(self, user_id: int, payload: LLMConfigCreate) -> LLMConfigRead:
        """创建新的LLM配置。"""
        # 检查配置名称是否重复
        existing = await self.repo.get_by_name(user_id, payload.config_name)
        if existing:
            raise HTTPException(status_code=400, detail=f"配置名称 '{payload.config_name}' 已存在")

        data = payload.model_dump(exclude_unset=True)
        if "llm_provider_url" in data and data["llm_provider_url"] is not None:
            data["llm_provider_url"] = str(data["llm_provider_url"])

        # 如果用户没有任何配置，则将新配置设为激活
        configs = await self.repo.list_by_user(user_id)
        is_first_config = len(configs) == 0

        instance = LLMConfig(
            user_id=user_id,
            is_active=is_first_config,  # 第一个配置自动激活
            **data,
        )
        await self.repo.add(instance)
        await self.session.commit()
        await self.session.refresh(instance)
        return LLMConfigRead.from_orm_with_mask(instance)

    async def update_config(self, config_id: int, user_id: int, payload: LLMConfigUpdate) -> LLMConfigRead:
        """更新LLM配置。"""
        config = await self.repo.get_by_id(config_id, user_id)
        if not config:
            raise HTTPException(status_code=404, detail="配置不存在或无权访问")

        data = payload.model_dump(exclude_unset=True)

        # 检查配置名称是否与其他配置重复
        if "config_name" in data:
            existing = await self.repo.get_by_name(user_id, data["config_name"])
            if existing and existing.id != config_id:
                raise HTTPException(status_code=400, detail=f"配置名称 '{data['config_name']}' 已被其他配置使用")

        if "llm_provider_url" in data and data["llm_provider_url"] is not None:
            data["llm_provider_url"] = str(data["llm_provider_url"])

        # 如果更新了配置信息，则重置验证状态
        if any(key in data for key in ["llm_provider_url", "llm_provider_api_key", "llm_provider_model"]):
            data["is_verified"] = False
            data["test_status"] = None
            data["test_message"] = None

        await self.repo.update_fields(config, **data)
        await self.session.commit()
        await self.session.refresh(config)
        return LLMConfigRead.from_orm_with_mask(config)

    async def activate_config(self, config_id: int, user_id: int) -> LLMConfigRead:
        """激活指定配置。"""
        config = await self.repo.get_by_id(config_id, user_id)
        if not config:
            raise HTTPException(status_code=404, detail="配置不存在或无权访问")

        await self.repo.activate_config(config_id, user_id)
        await self.session.commit()
        await self.session.refresh(config)
        return LLMConfigRead.from_orm_with_mask(config)

    async def delete_config(self, config_id: int, user_id: int) -> bool:
        """删除LLM配置。"""
        config = await self.repo.get_by_id(config_id, user_id)
        if not config:
            raise HTTPException(status_code=404, detail="配置不存在或无权访问")

        # 不允许删除激活的配置
        if config.is_active:
            raise HTTPException(status_code=400, detail="无法删除当前激活的配置，请先切换到其他配置")

        await self.repo.delete(config)
        await self.session.commit()
        return True

    async def test_config(self, config_id: int, user_id: int) -> LLMConfigTestResponse:
        """测试LLM配置是否可用。"""
        config = await self.repo.get_by_id(config_id, user_id)
        if not config:
            raise HTTPException(status_code=404, detail="配置不存在或无权访问")

        # 检查必需字段
        if not config.llm_provider_api_key or not config.llm_provider_api_key.strip():
            return LLMConfigTestResponse(
                success=False,
                message="配置缺少 API Key",
            )

        # 验证 API Key 格式（基本检查）
        api_key = config.llm_provider_api_key.strip()
        if len(api_key) < 10:
            return LLMConfigTestResponse(
                success=False,
                message="API Key 格式不正确（长度过短）",
            )

        # 使用配置进行测试调用
        try:
            start_time = time.time()

            # 创建测试用的 LLM 客户端
            # 重要：使用严格模式和浏览器模拟，确保不回退到环境变量且能绕过 Cloudflare
            test_api_key = api_key
            test_base_url = config.llm_provider_url.strip() if config.llm_provider_url and config.llm_provider_url.strip() else None
            test_model = config.llm_provider_model.strip() if config.llm_provider_model and config.llm_provider_model.strip() else "gpt-3.5-turbo"

            logger.info("测试配置 %s: api_key长度=%d, base_url=%s, model=%s",
                       config.config_name, len(test_api_key), test_base_url, test_model)

            client = LLMClient(
                api_key=test_api_key,
                base_url=test_base_url,
                strict_mode=True,  # 启用严格模式，不回退到环境变量
                simulate_browser=True,  # 启用浏览器模拟，绕过 Cloudflare 检测
            )

            # 发送简单的测试请求
            messages = [ChatMessage(role="user", content="测试连接，请回复'连接成功'")]

            response_text = ""
            chunk_count = 0
            async for chunk in client.stream_chat(
                messages=messages,
                model=test_model,
                temperature=0.1,
                max_tokens=50,
                timeout=30,  # 测试超时30秒
            ):
                if chunk.get("content"):
                    response_text += chunk["content"]
                chunk_count += 1

            end_time = time.time()
            response_time_ms = (end_time - start_time) * 1000

            # 检查是否收到了有效响应
            if chunk_count == 0 or not response_text.strip():
                raise ValueError("未收到有效响应，可能 API Key 或 Base URL 配置错误")

            # 更新配置的测试状态
            await self.repo.update_fields(
                config,
                is_verified=True,
                test_status="success",
                test_message="连接测试成功",
                last_test_at=datetime.now(timezone.utc),
            )
            await self.session.commit()

            logger.info("用户 %s 的配置 %s 测试成功，响应时间: %.2f ms", user_id, config.config_name, response_time_ms)

            return LLMConfigTestResponse(
                success=True,
                message="连接测试成功",
                response_time_ms=round(response_time_ms, 2),
                model_info=config.llm_provider_model or "默认模型",
            )

        except Exception as exc:
            error_message = str(exc)
            logger.error("用户 %s 的配置 %s 测试失败: %s", user_id, config.config_name, error_message, exc_info=True)

            # 更新配置的测试状态
            await self.repo.update_fields(
                config,
                is_verified=False,
                test_status="failed",
                test_message=error_message[:500],  # 限制错误信息长度
                last_test_at=datetime.now(timezone.utc),
            )
            await self.session.commit()

            return LLMConfigTestResponse(
                success=False,
                message=f"连接测试失败: {error_message}",
            )

    # 保留旧方法以兼容现有代码
    async def upsert_config(self, user_id: int, payload: LLMConfigCreate) -> LLMConfigRead:
        """兼容旧API：创建或更新用户的第一个配置。"""
        configs = await self.repo.list_by_user(user_id)
        if configs:
            # 更新第一个配置
            return await self.update_config(configs[0].id, user_id, LLMConfigUpdate(**payload.model_dump()))
        else:
            # 创建新配置
            return await self.create_config(user_id, payload)
