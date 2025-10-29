import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.dependencies import get_current_user
from ...db.session import get_session
from ...schemas.llm_config import (
    LLMConfigCreate,
    LLMConfigRead,
    LLMConfigUpdate,
    LLMConfigTestRequest,
    LLMConfigTestResponse,
)
from ...schemas.user import UserInDB
from ...services.llm_config_service import LLMConfigService


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/llm-config", tags=["LLM Configuration"])


def get_llm_config_service(session: AsyncSession = Depends(get_session)) -> LLMConfigService:
    return LLMConfigService(session)


# ========== 旧版API（兼容性保留） ==========


@router.get("", response_model=LLMConfigRead, deprecated=True)
async def read_llm_config(
    service: LLMConfigService = Depends(get_llm_config_service),
    current_user: UserInDB = Depends(get_current_user),
) -> LLMConfigRead:
    """获取用户的第一个LLM配置（兼容旧版）。建议使用 GET /api/llm-config/configs 获取所有配置。"""
    config = await service.get_active_config(current_user.id)
    if not config:
        logger.warning("用户 %s 尚未设置 LLM 配置", current_user.id)
        raise HTTPException(status_code=404, detail="尚未设置自定义配置")
    logger.info("用户 %s 获取 LLM 配置", current_user.id)
    return config


@router.put("", response_model=LLMConfigRead, deprecated=True)
async def upsert_llm_config(
    payload: LLMConfigCreate,
    service: LLMConfigService = Depends(get_llm_config_service),
    current_user: UserInDB = Depends(get_current_user),
) -> LLMConfigRead:
    """创建或更新用户的第一个LLM配置（兼容旧版）。建议使用新版多配置API。"""
    logger.info("用户 %s 更新 LLM 配置", current_user.id)
    return await service.upsert_config(current_user.id, payload)


@router.delete("", status_code=status.HTTP_204_NO_CONTENT, deprecated=True)
async def delete_llm_config(
    service: LLMConfigService = Depends(get_llm_config_service),
    current_user: UserInDB = Depends(get_current_user),
) -> None:
    """删除用户的第一个LLM配置（兼容旧版）。建议使用 DELETE /api/llm-config/configs/{config_id}。"""
    configs = await service.list_configs(current_user.id)
    if not configs:
        logger.warning("用户 %s 删除 LLM 配置失败，未找到记录", current_user.id)
        raise HTTPException(status_code=404, detail="未找到配置")

    # 优先删除非激活的配置，避免删除当前正在使用的配置
    non_active_configs = [c for c in configs if not c.is_active]
    if non_active_configs:
        # 删除第一个非激活配置
        deleted = await service.delete_config(non_active_configs[0].id, current_user.id)
        if not deleted:
            logger.warning("用户 %s 删除 LLM 配置失败", current_user.id)
            raise HTTPException(status_code=404, detail="删除失败")
        logger.info("用户 %s 删除 LLM 配置（非激活）", current_user.id)
    else:
        # 所有配置都是激活状态（实际上只能有一个激活），提示用户使用新版API
        logger.warning("用户 %s 尝试删除激活配置，建议使用新版API", current_user.id)
        raise HTTPException(
            status_code=400,
            detail="无法删除当前激活的配置，请先在设置中切换到其他配置，或使用新版API管理多个配置"
        )


# ========== 新版多配置管理API ==========


@router.get("/configs", response_model=list[LLMConfigRead])
async def list_llm_configs(
    service: LLMConfigService = Depends(get_llm_config_service),
    current_user: UserInDB = Depends(get_current_user),
) -> list[LLMConfigRead]:
    """获取用户的所有LLM配置列表。"""
    logger.info("用户 %s 查询 LLM 配置列表", current_user.id)
    return await service.list_configs(current_user.id)


@router.get("/configs/active", response_model=LLMConfigRead)
async def get_active_config(
    service: LLMConfigService = Depends(get_llm_config_service),
    current_user: UserInDB = Depends(get_current_user),
) -> LLMConfigRead:
    """获取用户当前激活的LLM配置。"""
    config = await service.get_active_config(current_user.id)
    if not config:
        logger.warning("用户 %s 没有激活的 LLM 配置", current_user.id)
        raise HTTPException(status_code=404, detail="没有激活的配置")
    logger.info("用户 %s 获取激活的 LLM 配置: %s", current_user.id, config.config_name)
    return config


@router.get("/configs/{config_id}", response_model=LLMConfigRead)
async def get_llm_config_by_id(
    config_id: int,
    service: LLMConfigService = Depends(get_llm_config_service),
    current_user: UserInDB = Depends(get_current_user),
) -> LLMConfigRead:
    """获取指定ID的LLM配置。"""
    logger.info("用户 %s 查询 LLM 配置 ID=%s", current_user.id, config_id)
    return await service.get_config(config_id, current_user.id)


@router.post("/configs", response_model=LLMConfigRead, status_code=status.HTTP_201_CREATED)
async def create_llm_config(
    payload: LLMConfigCreate,
    service: LLMConfigService = Depends(get_llm_config_service),
    current_user: UserInDB = Depends(get_current_user),
) -> LLMConfigRead:
    """创建新的LLM配置。"""
    logger.info("用户 %s 创建 LLM 配置: %s", current_user.id, payload.config_name)
    return await service.create_config(current_user.id, payload)


@router.put("/configs/{config_id}", response_model=LLMConfigRead)
async def update_llm_config(
    config_id: int,
    payload: LLMConfigUpdate,
    service: LLMConfigService = Depends(get_llm_config_service),
    current_user: UserInDB = Depends(get_current_user),
) -> LLMConfigRead:
    """更新指定ID的LLM配置。"""
    logger.info("用户 %s 更新 LLM 配置 ID=%s", current_user.id, config_id)
    return await service.update_config(config_id, current_user.id, payload)


@router.post("/configs/{config_id}/activate", response_model=LLMConfigRead)
async def activate_llm_config(
    config_id: int,
    service: LLMConfigService = Depends(get_llm_config_service),
    current_user: UserInDB = Depends(get_current_user),
) -> LLMConfigRead:
    """激活指定ID的LLM配置。"""
    logger.info("用户 %s 激活 LLM 配置 ID=%s", current_user.id, config_id)
    return await service.activate_config(config_id, current_user.id)


@router.delete("/configs/{config_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_llm_config_by_id(
    config_id: int,
    service: LLMConfigService = Depends(get_llm_config_service),
    current_user: UserInDB = Depends(get_current_user),
) -> None:
    """删除指定ID的LLM配置。"""
    logger.info("用户 %s 删除 LLM 配置 ID=%s", current_user.id, config_id)
    await service.delete_config(config_id, current_user.id)


@router.post("/configs/{config_id}/test", response_model=LLMConfigTestResponse)
async def test_llm_config(
    config_id: int,
    service: LLMConfigService = Depends(get_llm_config_service),
    current_user: UserInDB = Depends(get_current_user),
) -> LLMConfigTestResponse:
    """测试指定ID的LLM配置是否可用。"""
    logger.info("用户 %s 测试 LLM 配置 ID=%s", current_user.id, config_id)
    return await service.test_config(config_id, current_user.id)


# ========== 导入导出功能 ==========


@router.get("/configs/{config_id}/export")
async def export_llm_config(
    config_id: int,
    service: LLMConfigService = Depends(get_llm_config_service),
    current_user: UserInDB = Depends(get_current_user),
):
    """导出单个LLM配置为JSON文件。"""
    logger.info("用户 %s 导出 LLM 配置 ID=%s", current_user.id, config_id)
    export_data = await service.export_config(config_id, current_user.id)

    # 返回JSON文件下载
    from fastapi.responses import JSONResponse
    filename = f"llm_config_{config_id}.json"
    return JSONResponse(
        content=export_data,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"'
        }
    )


@router.get("/configs/export/all")
async def export_all_llm_configs(
    service: LLMConfigService = Depends(get_llm_config_service),
    current_user: UserInDB = Depends(get_current_user),
):
    """导出用户的所有LLM配置为JSON文件。"""
    logger.info("用户 %s 导出所有 LLM 配置", current_user.id)
    export_data = await service.export_all_configs(current_user.id)

    # 返回JSON文件下载
    from fastapi.responses import JSONResponse
    from datetime import datetime
    filename = f"llm_configs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    return JSONResponse(
        content=export_data,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"'
        }
    )


@router.post("/configs/import")
async def import_llm_configs(
    import_data: dict,
    service: LLMConfigService = Depends(get_llm_config_service),
    current_user: UserInDB = Depends(get_current_user),
):
    """导入LLM配置。"""
    logger.info("用户 %s 导入 LLM 配置", current_user.id)
    result = await service.import_configs(current_user.id, import_data)
    return result

