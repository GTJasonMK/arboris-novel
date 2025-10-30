import asyncio
import json
import logging
import os
import time
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.config import settings
from ...core.state_machine import ProjectStatus
from ...core.dependencies import get_current_user
from ...db.session import get_session
from ...models.novel import Chapter, ChapterOutline
from ...schemas.novel import (
    DeleteChapterRequest,
    EditChapterRequest,
    EvaluateChapterRequest,
    GenerateChapterRequest,
    GenerateOutlineRequest,
    GeneratePartOutlinesRequest,
    GeneratePartChaptersRequest,
    BatchGenerateChaptersRequest,
    PartOutlineGenerationProgress,
    NovelProject as NovelProjectSchema,
    RetryVersionRequest,
    SelectVersionRequest,
    UpdateChapterOutlineRequest,
)
from ...schemas.user import UserInDB
from ...services.chapter_context_service import ChapterContextService
from ...services.chapter_ingest_service import ChapterIngestionService
from ...services.llm_service import LLMService
from ...services.novel_service import NovelService
from ...services.part_outline_service import PartOutlineService
from ...services.prompt_service import PromptService
from ...services.usage_service import UsageService
from ...services.vector_store_service import VectorStoreService
from ...utils.json_utils import remove_think_tags, unwrap_markdown_json
from ...repositories.system_config_repository import SystemConfigRepository

router = APIRouter(prefix="/api/writer", tags=["Writer"])
logger = logging.getLogger(__name__)

# 模块加载测试日志
logger.info("=" * 80)
logger.info("writer.py 模块已加载，logger 名称: %s", __name__)
logger.info("=" * 80)


async def _load_project_schema(service: NovelService, project_id: str, user_id: int) -> NovelProjectSchema:
    return await service.get_project_schema(project_id, user_id)


def _extract_tail_excerpt(text: Optional[str], limit: int = 500) -> str:
    """截取章节结尾文本，默认保留 500 字。"""
    if not text:
        return ""
    stripped = text.strip()
    if len(stripped) <= limit:
        return stripped
    return stripped[-limit:]


@router.post("/novels/{project_id}/chapters/generate", response_model=NovelProjectSchema)
async def generate_chapter(
    project_id: str,
    request: GenerateChapterRequest,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> NovelProjectSchema:
    logger.info("=" * 100)
    logger.info("!!! 收到章节生成请求 !!!")
    logger.info("project_id=%s, chapter_number=%s, user_id=%s", project_id, request.chapter_number, current_user.id)
    logger.info("=" * 100)

    novel_service = NovelService(session)
    prompt_service = PromptService(session)
    llm_service = LLMService(session)

    project = await novel_service.ensure_project_owner(project_id, current_user.id)
    logger.info("用户 %s 开始为项目 %s 生成第 %s 章", current_user.id, project_id, request.chapter_number)

    # 如果项目还未进入写作状态，更新为writing
    if project.status == ProjectStatus.CHAPTER_OUTLINES_READY.value:
        await novel_service.transition_project_status(project, ProjectStatus.WRITING.value)
        logger.info("项目 %s 状态更新为 %s", project_id, ProjectStatus.WRITING.value)

    # 在并行模式下，提前执行一次 daily limit 检查（避免并发冲突）
    version_count = await _resolve_version_count(session)
    if settings.writer_parallel_generation and version_count > 1:
        # 手动执行一次 daily limit 检查并增量
        await llm_service._enforce_daily_limit(current_user.id)
        logger.info(
            "项目 %s 第 %s 章（并行模式）已完成 daily limit 检查",
            project_id,
            request.chapter_number,
        )

    outline = await novel_service.get_outline(project_id, request.chapter_number)
    if not outline:
        logger.warning("项目 %s 未找到第 %s 章纲要，生成流程终止", project_id, request.chapter_number)
        raise HTTPException(status_code=404, detail="蓝图中未找到对应章节纲要")

    chapter = await novel_service.get_or_create_chapter(project_id, request.chapter_number)
    chapter.real_summary = None
    chapter.selected_version_id = None
    chapter.status = "generating"
    await session.commit()

    outlines_map = {item.chapter_number: item for item in project.outlines}
    # 收集所有可用的历史章节摘要，便于在 Prompt 中提供前情背景
    completed_chapters = []
    latest_prev_number = -1
    previous_summary_text = ""
    previous_tail_excerpt = ""
    for existing in project.chapters:
        if existing.chapter_number >= request.chapter_number:
            continue
        if existing.selected_version is None or not existing.selected_version.content:
            continue
        if not existing.real_summary:
            try:
                summary = await llm_service.get_summary(
                    existing.selected_version.content,
                    temperature=0.15,
                    user_id=current_user.id,
                    timeout=180.0,
                )
                existing.real_summary = remove_think_tags(summary)
                await session.commit()
            except Exception as exc:
                logger.warning(
                    "项目 %s 第 %s 章摘要生成失败，将使用空摘要继续: %s",
                    project_id,
                    existing.chapter_number,
                    exc
                )
                # 摘要生成失败不影响章节生成，使用空摘要或默认文本
                existing.real_summary = "摘要生成失败，请稍后手动生成"
        completed_chapters.append(
            {
                "chapter_number": existing.chapter_number,
                "title": outlines_map.get(existing.chapter_number).title if outlines_map.get(existing.chapter_number) else f"第{existing.chapter_number}章",
                "summary": existing.real_summary,
            }
        )
        if existing.chapter_number > latest_prev_number:
            latest_prev_number = existing.chapter_number
            previous_summary_text = existing.real_summary or ""
            previous_tail_excerpt = _extract_tail_excerpt(existing.selected_version.content)

    project_schema = await novel_service._serialize_project(project)
    blueprint_dict = project_schema.blueprint.model_dump()

    if "relationships" in blueprint_dict and blueprint_dict["relationships"]:
        for relation in blueprint_dict["relationships"]:
            if "character_from" in relation:
                relation["from"] = relation.pop("character_from")
            if "character_to" in relation:
                relation["to"] = relation.pop("character_to")

    # 蓝图中禁止携带章节级别的细节信息，避免重复传输大段场景或对话内容
    banned_blueprint_keys = {
        "chapter_outline",
        "chapter_summaries",
        "chapter_details",
        "chapter_dialogues",
        "chapter_events",
        "conversation_history",
        "character_timelines",
    }
    for key in banned_blueprint_keys:
        if key in blueprint_dict:
            blueprint_dict.pop(key, None)

    writer_prompt = await prompt_service.get_prompt("writing")
    if not writer_prompt:
        raise HTTPException(status_code=500, detail="缺少写作提示词")

    # 初始化向量检索服务，若未配置则自动降级为纯提示词生成
    vector_store: Optional[VectorStoreService]
    if not settings.vector_store_enabled:
        vector_store = None
    else:
        try:
            vector_store = VectorStoreService()
        except RuntimeError as exc:
            logger.warning("向量库初始化失败，RAG 检索被禁用: %s", exc)
            vector_store = None
    context_service = ChapterContextService(llm_service=llm_service, vector_store=vector_store)

    outline_title = outline.title or f"第{outline.chapter_number}章"
    outline_summary = outline.summary or "暂无摘要"
    query_parts = [outline_title, outline_summary]
    if request.writing_notes:
        query_parts.append(request.writing_notes)
    rag_query = "\n".join(part for part in query_parts if part)
    rag_context = await context_service.retrieve_for_generation(
        project_id=project_id,
        query_text=rag_query or outline.title or outline.summary or "",
        user_id=current_user.id,
    )
    chunk_count = len(rag_context.chunks) if rag_context and rag_context.chunks else 0
    summary_count = len(rag_context.summaries) if rag_context and rag_context.summaries else 0
    logger.info(
        "项目 %s 第 %s 章检索到 %s 个剧情片段和 %s 条摘要",
        project_id,
        request.chapter_number,
        chunk_count,
        summary_count,
    )
    # print("rag_context:",rag_context)
    # 将蓝图、前情、RAG 检索结果拼装成结构化段落，供模型理解
    blueprint_text = json.dumps(blueprint_dict, ensure_ascii=False, indent=2)
    completed_lines = [
        f"- 第{item['chapter_number']}章 - {item['title']}:{item['summary']}"
        for item in completed_chapters
    ]
    previous_summary_text = previous_summary_text or "暂无可用摘要"
    previous_tail_excerpt = previous_tail_excerpt or "暂无上一章结尾内容"
    completed_section = "\n".join(completed_lines) if completed_lines else "暂无前情摘要"
    rag_chunks_text = "\n\n".join(rag_context.chunk_texts()) if rag_context.chunks else "未检索到章节片段"
    rag_summaries_text = "\n".join(rag_context.summary_lines()) if rag_context.summaries else "未检索到章节摘要"
    writing_notes = request.writing_notes or "无额外写作指令"

    prompt_sections = [
        ("[世界蓝图](JSON)", blueprint_text),
        # ("[前情摘要]", completed_section),
        ("[上一章摘要]", previous_summary_text),
        ("[上一章结尾]", previous_tail_excerpt),
        ("[检索到的剧情上下文](Markdown)", rag_chunks_text),
        ("[检索到的章节摘要]", rag_summaries_text),
        (
            "[当前章节目标]",
            f"标题：{outline_title}\n摘要：{outline_summary}\n写作要求：{writing_notes}",
        ),
    ]
    prompt_input = "\n\n".join(f"{title}\n{content}" for title, content in prompt_sections if content)
    logger.debug("章节写作提示词：%s\n%s", writer_prompt, prompt_input)

    # 在并行模式下跳过 usage tracking，避免数据库 session 冲突
    skip_usage_tracking = settings.writer_parallel_generation

    # 在并行模式下，预先获取 LLM 配置并缓存，避免并行任务中的数据库查询导致 autoflush 冲突
    llm_config: Optional[Dict[str, Optional[str]]] = None
    if skip_usage_tracking:
        llm_config = await llm_service._resolve_llm_config(current_user.id, skip_daily_limit_check=True)
        logger.info(
            "项目 %s 第 %s 章（并行模式）已缓存 LLM 配置",
            project_id,
            request.chapter_number,
        )

    async def _generate_single_version(idx: int) -> Dict:
        import asyncio
        task_id = id(asyncio.current_task())
        logger.info("[Task %s] 开始生成版本 %s", task_id, idx + 1)
        try:
            response = await llm_service.get_llm_response(
                system_prompt=writer_prompt,
                conversation_history=[{"role": "user", "content": prompt_input}],
                temperature=0.9,
                user_id=current_user.id,
                timeout=600.0,
                skip_usage_tracking=skip_usage_tracking,
                skip_daily_limit_check=skip_usage_tracking,
                cached_config=llm_config,
            )
            logger.info("[Task %s] 版本 %s LLM 响应获取成功", task_id, idx + 1)
            cleaned = remove_think_tags(response)
            normalized = unwrap_markdown_json(cleaned)
            try:
                return json.loads(normalized)
            except json.JSONDecodeError:
                return {"content": normalized}
        except Exception as exc:
            import traceback
            error_details = traceback.format_exc()
            logger.exception(
                "[Task %s] 项目 %s 生成第 %s 章第 %s 个版本时发生异常\n异常类型: %s\n异常信息: %s\n完整堆栈:\n%s",
                task_id,
                project_id,
                request.chapter_number,
                idx + 1,
                type(exc).__name__,
                exc,
                error_details,
            )
            # 检查是否是 session flushing 错误
            if "Session is already flushing" in str(exc) or "already flushing" in str(exc).lower():
                logger.error(
                    "[Task %s] !!!!! 检测到 Session flushing 冲突 !!!!!\n"
                    "当前任务ID: %s\n"
                    "版本索引: %s\n"
                    "cached_config 是否存在: %s\n"
                    "skip_usage_tracking: %s\n"
                    "完整异常: %s",
                    task_id,
                    task_id,
                    idx,
                    bool(llm_config),
                    skip_usage_tracking,
                    error_details,
                )
            return {"content": f"生成失败: {exc}"}

    version_count = await _resolve_version_count(session)
    logger.info(
        "项目 %s 第 %s 章计划生成 %s 个版本（并行模式：%s）",
        project_id,
        request.chapter_number,
        version_count,
        settings.writer_parallel_generation,
    )

    # 并行生成所有版本
    start_time = time.time()

    if settings.writer_parallel_generation:
        # 并行模式：使用 Semaphore 控制最大并发数
        logger.info(
            "项目 %s 第 %s 章进入并行生成模式\n"
            "  - 版本数: %s\n"
            "  - 最大并发数: %s\n"
            "  - cached_config 是否存在: %s\n"
            "  - skip_usage_tracking: %s\n"
            "  - session.autoflush: %s",
            project_id,
            request.chapter_number,
            version_count,
            settings.writer_max_parallel_requests,
            bool(llm_config),
            skip_usage_tracking,
            session.autoflush,
        )

        semaphore = asyncio.Semaphore(settings.writer_max_parallel_requests)

        async def _generate_with_semaphore(idx: int) -> Dict:
            """带并发控制的生成函数"""
            async with semaphore:
                logger.info(
                    "项目 %s 第 %s 章开始生成版本 %s/%s",
                    project_id,
                    request.chapter_number,
                    idx + 1,
                    version_count,
                )
                result = await _generate_single_version(idx)
                logger.info(
                    "项目 %s 第 %s 章版本 %s/%s 生成完成",
                    project_id,
                    request.chapter_number,
                    idx + 1,
                    version_count,
                )
                return result

        # 创建所有任务并并行执行
        # 使用 no_autoflush 禁用自动 flush，避免并发查询时的隐式 flush 冲突
        logger.info("项目 %s 第 %s 章开始并行执行，进入 no_autoflush 上下文", project_id, request.chapter_number)
        with session.no_autoflush:
            logger.info("session.no_autoflush 已启用，session.autoflush=%s", session.autoflush)
            tasks = [_generate_with_semaphore(idx) for idx in range(version_count)]
            logger.info("项目 %s 第 %s 章创建了 %s 个并行任务，开始执行 gather", project_id, request.chapter_number, len(tasks))
            raw_versions = await asyncio.gather(*tasks, return_exceptions=True)
            logger.info("项目 %s 第 %s 章 gather 执行完成，退出 no_autoflush 上下文", project_id, request.chapter_number)

        # 处理异常结果
        processed_versions = []
        for idx, result in enumerate(raw_versions):
            if isinstance(result, Exception):
                logger.error(
                    "项目 %s 第 %s 章版本 %s 生成失败: %s",
                    project_id,
                    request.chapter_number,
                    idx + 1,
                    result,
                )
                processed_versions.append({"content": f"生成失败: {result}"})
            else:
                processed_versions.append(result)
        raw_versions = processed_versions
    else:
        # 串行模式（向后兼容）
        raw_versions = []
        for idx in range(version_count):
            logger.info(
                "项目 %s 第 %s 章开始生成版本 %s/%s（串行模式）",
                project_id,
                request.chapter_number,
                idx + 1,
                version_count,
            )
            raw_versions.append(await _generate_single_version(idx))

    elapsed_time = time.time() - start_time
    logger.info(
        "项目 %s 第 %s 章所有版本生成完成，耗时 %.2f 秒（并行模式：%s）",
        project_id,
        request.chapter_number,
        elapsed_time,
        settings.writer_parallel_generation,
    )

    # 在并行模式下，统一更新 usage tracking（避免并发冲突）
    if skip_usage_tracking:
        # 计算成功生成的版本数
        successful_count = sum(
            1 for v in raw_versions
            if isinstance(v, dict) and not (isinstance(v.get("content"), str) and v.get("content", "").startswith("生成失败:"))
        )
        if successful_count > 0:
            usage_service = UsageService(session)
            for _ in range(successful_count):
                await usage_service.increment("api_request_count")
            logger.info(
                "项目 %s 第 %s 章更新 API 请求计数：%s 次",
                project_id,
                request.chapter_number,
                successful_count,
            )

    contents: List[str] = []
    metadata: List[Dict] = []
    for variant in raw_versions:
        if isinstance(variant, dict):
            if "content" in variant and isinstance(variant["content"], str):
                contents.append(variant["content"])
            elif "chapter_content" in variant:
                contents.append(str(variant["chapter_content"]))
            else:
                contents.append(json.dumps(variant, ensure_ascii=False))
            metadata.append(variant)
        else:
            contents.append(str(variant))
            metadata.append({"raw": variant})

    await novel_service.replace_chapter_versions(chapter, contents, metadata)
    logger.info(
        "项目 %s 第 %s 章生成完成，已写入 %s 个版本",
        project_id,
        request.chapter_number,
        len(contents),
    )
    # 清除session缓存，确保返回最新数据（包含刚保存的versions）
    session.expire_all()
    return await _load_project_schema(novel_service, project_id, current_user.id)


async def _resolve_version_count(session: AsyncSession) -> int:
    repo = SystemConfigRepository(session)
    record = await repo.get_by_key("writer.chapter_versions")
    if record:
        try:
            value = int(record.value)
            if value > 0:
                return value
        except (TypeError, ValueError):
            pass
    env_value = os.getenv("WRITER_CHAPTER_VERSION_COUNT")
    if env_value:
        try:
            value = int(env_value)
            if value > 0:
                return value
        except ValueError:
            pass
    return 3


@router.post("/novels/{project_id}/chapters/select", response_model=NovelProjectSchema)
async def select_chapter_version(
    project_id: str,
    request: SelectVersionRequest,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> NovelProjectSchema:
    novel_service = NovelService(session)
    llm_service = LLMService(session)

    project = await novel_service.ensure_project_owner(project_id, current_user.id)
    chapter = next((ch for ch in project.chapters if ch.chapter_number == request.chapter_number), None)
    if not chapter:
        logger.warning("项目 %s 未找到第 %s 章，无法选择版本", project_id, request.chapter_number)
        raise HTTPException(status_code=404, detail="章节不存在")

    selected = await novel_service.select_chapter_version(chapter, request.version_index)
    logger.info(
        "用户 %s 选择了项目 %s 第 %s 章的第 %s 个版本",
        current_user.id,
        project_id,
        request.chapter_number,
        request.version_index,
    )
    
    # 优化：分离版本选择和摘要生成，避免摘要失败导致整个操作失败
    if selected and selected.content:
        try:
            summary = await llm_service.get_summary(
                selected.content,
                temperature=0.15,
                user_id=current_user.id,
                timeout=180.0,
            )
            chapter.real_summary = remove_think_tags(summary)
            await session.commit()
        except Exception as exc:
            logger.error("项目 %s 第 %s 章摘要生成失败，但版本选择已保存: %s", project_id, request.chapter_number, exc)
            # 摘要生成失败不影响版本选择结果，继续处理

        # 选定版本后同步向量库，确保后续章节可检索到最新内容
        vector_store: Optional[VectorStoreService]
        if not settings.vector_store_enabled:
            vector_store = None
        else:
            try:
                vector_store = VectorStoreService()
            except RuntimeError as exc:
                logger.warning("向量库初始化失败，跳过章节向量同步: %s", exc)
                vector_store = None

        if vector_store:
            ingestion_service = ChapterIngestionService(llm_service=llm_service, vector_store=vector_store)
            outline = next((item for item in project.outlines if item.chapter_number == chapter.chapter_number), None)
            chapter_title = outline.title if outline and outline.title else f"第{chapter.chapter_number}章"
            await ingestion_service.ingest_chapter(
                project_id=project_id,
                chapter_number=chapter.chapter_number,
                title=chapter_title,
                content=selected.content,
                summary=chapter.real_summary,
                user_id=current_user.id,
            )
            logger.info(
                "项目 %s 第 %s 章已同步至向量库",
                project_id,
                chapter.chapter_number,
            )

    # 选择版本后检查是否所有章节都完成了
    await novel_service.check_and_update_completion_status(project_id, current_user.id)

    # 清除session缓存，确保返回最新数据
    session.expire_all()
    return await _load_project_schema(novel_service, project_id, current_user.id)


@router.post("/novels/{project_id}/chapters/retry-version", response_model=NovelProjectSchema)
async def retry_chapter_version(
    project_id: str,
    request: RetryVersionRequest,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> NovelProjectSchema:
    """重新生成指定章节的某个版本"""
    logger.info("用户 %s 请求重试项目 %s 第 %s 章的版本 %s", current_user.id, project_id, request.chapter_number, request.version_index)

    novel_service = NovelService(session)
    prompt_service = PromptService(session)
    llm_service = LLMService(session)

    project = await novel_service.ensure_project_owner(project_id, current_user.id)
    chapter = next((ch for ch in project.chapters if ch.chapter_number == request.chapter_number), None)
    if not chapter or not chapter.versions:
        raise HTTPException(status_code=404, detail="章节或版本不存在")

    versions = sorted(chapter.versions, key=lambda item: item.created_at)
    if request.version_index < 0 or request.version_index >= len(versions):
        raise HTTPException(status_code=400, detail="版本索引无效")

    # 构建生成上下文（复用generate_chapter的逻辑）
    outline = await novel_service.get_outline(project_id, request.chapter_number)
    if not outline:
        raise HTTPException(status_code=404, detail="章节大纲不存在")

    outlines_map = {item.chapter_number: item for item in project.outlines}
    previous_summary_text = ""
    previous_tail_excerpt = ""
    latest_prev_number = -1

    for existing in project.chapters:
        if existing.chapter_number >= request.chapter_number:
            continue
        if existing.selected_version is None or not existing.selected_version.content:
            continue
        if existing.chapter_number > latest_prev_number:
            latest_prev_number = existing.chapter_number
            previous_summary_text = existing.real_summary or ""
            previous_tail_excerpt = _extract_tail_excerpt(existing.selected_version.content)

    project_schema = await novel_service._serialize_project(project)
    blueprint_dict = project_schema.blueprint.model_dump()

    if "relationships" in blueprint_dict and blueprint_dict["relationships"]:
        for relation in blueprint_dict["relationships"]:
            if "character_from" in relation:
                relation["from"] = relation.pop("character_from")
            if "character_to" in relation:
                relation["to"] = relation.pop("character_to")

    banned_blueprint_keys = {
        "chapter_outline", "chapter_summaries", "chapter_details",
        "chapter_dialogues", "chapter_events", "conversation_history", "character_timelines",
    }
    for key in banned_blueprint_keys:
        blueprint_dict.pop(key, None)

    writer_prompt = await prompt_service.get_prompt("writing")
    if not writer_prompt:
        raise HTTPException(status_code=500, detail="缺少写作提示词")

    # RAG检索
    vector_store = None
    if settings.vector_store_enabled:
        try:
            vector_store = VectorStoreService()
        except RuntimeError as exc:
            logger.warning("向量库初始化失败: %s", exc)

    context_service = ChapterContextService(llm_service=llm_service, vector_store=vector_store)
    outline_title = outline.title or f"第{outline.chapter_number}章"
    outline_summary = outline.summary or "暂无摘要"
    query_parts = [outline_title, outline_summary]
    if request.custom_prompt:
        query_parts.append(request.custom_prompt)
    rag_query = "\n".join(query_parts)
    rag_context = await context_service.retrieve_for_generation(
        project_id=project_id,
        query_text=rag_query,
        user_id=current_user.id,
    )

    blueprint_text = json.dumps(blueprint_dict, ensure_ascii=False, indent=2)
    previous_summary_text = previous_summary_text or "暂无可用摘要"
    previous_tail_excerpt = previous_tail_excerpt or "暂无上一章结尾内容"
    rag_chunks_text = "\n\n".join(rag_context.chunk_texts()) if rag_context.chunks else "未检索到章节片段"
    rag_summaries_text = "\n".join(rag_context.summary_lines()) if rag_context.summaries else "未检索到章节摘要"

    # 如果用户提供了自定义提示词，添加到写作要求中
    writing_notes = request.custom_prompt or "无额外写作指令"

    prompt_sections = [
        ("[世界蓝图](JSON)", blueprint_text),
        ("[上一章摘要]", previous_summary_text),
        ("[上一章结尾]", previous_tail_excerpt),
        ("[检索到的剧情上下文](Markdown)", rag_chunks_text),
        ("[检索到的章节摘要]", rag_summaries_text),
        ("[当前章节目标]", f"标题：{outline_title}\n摘要：{outline_summary}\n写作要求：{writing_notes}"),
    ]
    prompt_input = "\n\n".join(f"{title}\n{content}" for title, content in prompt_sections if content)

    # 生成单个版本
    response = await llm_service.get_llm_response(
        system_prompt=writer_prompt,
        conversation_history=[{"role": "user", "content": prompt_input}],
        temperature=0.9,
        user_id=current_user.id,
        timeout=600.0,
    )

    cleaned = remove_think_tags(response)
    normalized = unwrap_markdown_json(cleaned)
    try:
        result = json.loads(normalized)
        new_content = result.get("content", normalized)
    except json.JSONDecodeError:
        new_content = normalized

    # 替换指定版本的内容
    target_version = versions[request.version_index]
    target_version.content = new_content
    await session.commit()

    logger.info("项目 %s 第 %s 章版本 %s 重试完成", project_id, request.chapter_number, request.version_index)

    session.expire_all()
    return await _load_project_schema(novel_service, project_id, current_user.id)


@router.post("/novels/{project_id}/chapters/evaluate", response_model=NovelProjectSchema)
async def evaluate_chapter(
    project_id: str,
    request: EvaluateChapterRequest,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> NovelProjectSchema:
    novel_service = NovelService(session)
    prompt_service = PromptService(session)
    llm_service = LLMService(session)

    project = await novel_service.ensure_project_owner(project_id, current_user.id)
    chapter = next((ch for ch in project.chapters if ch.chapter_number == request.chapter_number), None)
    if not chapter:
        logger.warning("项目 %s 未找到第 %s 章，无法执行评估", project_id, request.chapter_number)
        raise HTTPException(status_code=404, detail="章节不存在")
    if not chapter.versions:
        logger.warning("项目 %s 第 %s 章无可评估版本", project_id, request.chapter_number)
        raise HTTPException(status_code=400, detail="无可评估的章节版本")

    evaluator_prompt = await prompt_service.get_prompt("evaluation")
    if not evaluator_prompt:
        logger.error("缺少评估提示词，项目 %s 第 %s 章评估失败", project_id, request.chapter_number)
        raise HTTPException(status_code=500, detail="缺少评估提示词")

    project_schema = await novel_service._serialize_project(project)
    blueprint_dict = project_schema.blueprint.model_dump()

    versions_to_evaluate = [
        {"version_id": idx + 1, "content": version.content}
        for idx, version in enumerate(sorted(chapter.versions, key=lambda item: item.created_at))
    ]
    # print("blueprint_dict:",blueprint_dict)
    evaluator_payload = {
        "novel_blueprint": blueprint_dict,
        "content_to_evaluate": {
            "chapter_number": chapter.chapter_number,
            "versions": versions_to_evaluate,
        },
    }

    evaluation_raw = await llm_service.get_llm_response(
        system_prompt=evaluator_prompt,
        conversation_history=[{"role": "user", "content": json.dumps(evaluator_payload, ensure_ascii=False)}],
        temperature=0.3,
        user_id=current_user.id,
        timeout=360.0,
    )
    evaluation_clean = remove_think_tags(evaluation_raw)
    await novel_service.add_chapter_evaluation(chapter, None, evaluation_clean)
    logger.info("项目 %s 第 %s 章评估完成", project_id, request.chapter_number)

    return await _load_project_schema(novel_service, project_id, current_user.id)


@router.post("/novels/{project_id}/chapters/outline", response_model=NovelProjectSchema)
async def generate_chapter_outline(
    project_id: str,
    request: GenerateOutlineRequest,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> NovelProjectSchema:
    novel_service = NovelService(session)
    prompt_service = PromptService(session)
    llm_service = LLMService(session)

    await novel_service.ensure_project_owner(project_id, current_user.id)
    logger.info(
        "用户 %s 请求生成项目 %s 的章节大纲，起始章节 %s，数量 %s",
        current_user.id,
        project_id,
        request.start_chapter,
        request.num_chapters,
    )
    outline_prompt = await prompt_service.get_prompt("outline")
    if not outline_prompt:
        logger.error("缺少大纲提示词，项目 %s 大纲生成失败", project_id)
        raise HTTPException(status_code=500, detail="缺少大纲提示词")

    project_schema = await novel_service.get_project_schema(project_id, current_user.id)
    blueprint_dict = project_schema.blueprint.model_dump()

    payload = {
        "novel_blueprint": blueprint_dict,
        "wait_to_generate": {
            "start_chapter": request.start_chapter,
            "num_chapters": request.num_chapters,
        },
    }

    response = await llm_service.get_llm_response(
        system_prompt=outline_prompt,
        conversation_history=[{"role": "user", "content": json.dumps(payload, ensure_ascii=False)}],
        temperature=0.7,
        user_id=current_user.id,
        timeout=360.0,
    )
    normalized = unwrap_markdown_json(remove_think_tags(response))
    try:
        data = json.loads(normalized)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=500, detail="章节大纲生成失败") from exc

    new_outlines = data.get("chapters", [])
    for item in new_outlines:
        stmt = (
            select(ChapterOutline)
            .where(
                ChapterOutline.project_id == project_id,
                ChapterOutline.chapter_number == item.get("chapter_number"),
            )
        )
        result = await session.execute(stmt)
        record = result.scalars().first()
        if record:
            record.title = item.get("title", record.title)
            record.summary = item.get("summary", record.summary)
        else:
            session.add(
                ChapterOutline(
                    project_id=project_id,
                    chapter_number=item.get("chapter_number"),
                    title=item.get("title", ""),
                    summary=item.get("summary"),
                )
            )
    await session.commit()
    logger.info("项目 %s 章节大纲生成完成", project_id)

    return await novel_service.get_project_schema(project_id, current_user.id)


@router.post("/novels/{project_id}/chapters/update-outline", response_model=NovelProjectSchema)
async def update_chapter_outline(
    project_id: str,
    request: UpdateChapterOutlineRequest,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> NovelProjectSchema:
    novel_service = NovelService(session)
    await novel_service.ensure_project_owner(project_id, current_user.id)
    logger.info(
        "用户 %s 更新项目 %s 第 %s 章大纲",
        current_user.id,
        project_id,
        request.chapter_number,
    )

    stmt = (
        select(ChapterOutline)
        .where(
            ChapterOutline.project_id == project_id,
            ChapterOutline.chapter_number == request.chapter_number,
        )
    )
    result = await session.execute(stmt)
    outline = result.scalars().first()
    if not outline:
        outline = ChapterOutline(
            project_id=project_id,
            chapter_number=request.chapter_number,
        )
        session.add(outline)

    outline.title = request.title
    outline.summary = request.summary
    await session.commit()
    logger.info("项目 %s 第 %s 章大纲已更新", project_id, request.chapter_number)

    return await novel_service.get_project_schema(project_id, current_user.id)


@router.post("/novels/{project_id}/chapters/delete", response_model=NovelProjectSchema)
async def delete_chapters(
    project_id: str,
    request: DeleteChapterRequest,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> NovelProjectSchema:
    if not request.chapter_numbers:
        logger.warning("项目 %s 未提供要删除的章节号", project_id)
        raise HTTPException(status_code=400, detail="请提供要删除的章节号")
    novel_service = NovelService(session)
    llm_service = LLMService(session)
    await novel_service.ensure_project_owner(project_id, current_user.id)
    logger.info(
        "用户 %s 删除项目 %s 的章节 %s",
        current_user.id,
        project_id,
        request.chapter_numbers,
    )
    await novel_service.delete_chapters(project_id, request.chapter_numbers)

    # 删除章节时同步清理向量库，避免过时内容被检索
    vector_store: Optional[VectorStoreService]
    if not settings.vector_store_enabled:
        vector_store = None
    else:
        try:
            vector_store = VectorStoreService()
        except RuntimeError as exc:
            logger.warning("向量库初始化失败，跳过章节向量删除: %s", exc)
            vector_store = None

    if vector_store:
        ingestion_service = ChapterIngestionService(llm_service=llm_service, vector_store=vector_store)
        await ingestion_service.delete_chapters(project_id, request.chapter_numbers)
        logger.info(
            "项目 %s 已从向量库移除章节 %s",
            project_id,
            request.chapter_numbers,
        )

    return await novel_service.get_project_schema(project_id, current_user.id)


@router.post("/novels/{project_id}/chapters/edit", response_model=NovelProjectSchema)
async def edit_chapter(
    project_id: str,
    request: EditChapterRequest,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> NovelProjectSchema:
    novel_service = NovelService(session)
    llm_service = LLMService(session)

    project = await novel_service.ensure_project_owner(project_id, current_user.id)
    chapter = next((ch for ch in project.chapters if ch.chapter_number == request.chapter_number), None)
    if not chapter or chapter.selected_version is None:
        logger.warning("项目 %s 第 %s 章尚未生成或未选择版本，无法编辑", project_id, request.chapter_number)
        raise HTTPException(status_code=404, detail="章节尚未生成或未选择版本")

    chapter.selected_version.content = request.content
    chapter.word_count = len(request.content)
    logger.info("用户 %s 更新了项目 %s 第 %s 章内容", current_user.id, project_id, request.chapter_number)

    # 优化：分离内容保存和摘要生成，避免摘要失败导致编辑失败
    if request.content.strip():
        try:
            summary = await llm_service.get_summary(
                request.content,
                temperature=0.15,
                user_id=current_user.id,
                timeout=180.0,
            )
            chapter.real_summary = remove_think_tags(summary)
        except Exception as exc:
            logger.error("项目 %s 第 %s 章编辑后摘要生成失败，但内容已保存: %s", project_id, request.chapter_number, exc)
            # 摘要生成失败不影响内容保存，继续处理
            chapter.real_summary = "摘要生成失败，请稍后手动生成"
    await session.commit()

    vector_store: Optional[VectorStoreService]
    if not settings.vector_store_enabled:
        vector_store = None
    else:
        try:
            vector_store = VectorStoreService()
        except RuntimeError as exc:
            logger.warning("向量库初始化失败，跳过章节向量更新: %s", exc)
            vector_store = None

    if vector_store and chapter.selected_version and chapter.selected_version.content:
        ingestion_service = ChapterIngestionService(llm_service=llm_service, vector_store=vector_store)
        outline = next((item for item in project.outlines if item.chapter_number == chapter.chapter_number), None)
        chapter_title = outline.title if outline and outline.title else f"第{chapter.chapter_number}章"
        await ingestion_service.ingest_chapter(
            project_id=project_id,
            chapter_number=chapter.chapter_number,
            title=chapter_title,
            content=chapter.selected_version.content,
            summary=chapter.real_summary,
            user_id=current_user.id,
        )
        logger.info("项目 %s 第 %s 章更新内容已同步至向量库", project_id, chapter.chapter_number)

    return await novel_service.get_project_schema(project_id, current_user.id)


# ------------------------------------------------------------------
# 部分大纲生成接口（用于长篇小说分层大纲）
# ------------------------------------------------------------------


@router.post("/novels/{project_id}/parts/generate", response_model=PartOutlineGenerationProgress)
async def generate_part_outlines(
    project_id: str,
    request: GeneratePartOutlinesRequest,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> PartOutlineGenerationProgress:
    """
    生成部分大纲（大纲的大纲）

    用于长篇小说（51章以上），将整部小说分割成多个部分，
    每个部分包含若干章节，便于后续分批生成详细章节大纲。
    """
    logger.info("用户 %s 请求为项目 %s 生成部分大纲", current_user.id, project_id)

    part_service = PartOutlineService(session)

    return await part_service.generate_part_outlines(
        project_id=project_id,
        user_id=current_user.id,
        total_chapters=request.total_chapters,
        chapters_per_part=request.chapters_per_part,
    )


@router.post("/novels/{project_id}/parts/{part_number}/chapters", response_model=NovelProjectSchema)
async def generate_part_chapters(
    project_id: str,
    part_number: int,
    request: GeneratePartChaptersRequest,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> NovelProjectSchema:
    """
    为指定部分生成详细的章节大纲

    基于部分大纲的主题、关键事件等信息，
    生成该部分范围内所有章节的详细大纲。
    """
    logger.info("用户 %s 请求为项目 %s 的第 %d 部分生成章节大纲", current_user.id, project_id, part_number)

    part_service = PartOutlineService(session)
    novel_service = NovelService(session)

    await part_service.generate_part_chapters(
        project_id=project_id,
        user_id=current_user.id,
        part_number=part_number,
        regenerate=request.regenerate,
    )

    return await novel_service.get_project_schema(project_id, current_user.id)


@router.post("/novels/{project_id}/parts/batch-generate", response_model=PartOutlineGenerationProgress)
async def batch_generate_part_chapters(
    project_id: str,
    request: BatchGenerateChaptersRequest,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> PartOutlineGenerationProgress:
    """
    批量并发生成多个部分的章节大纲

    支持并发生成多个部分的章节大纲，提高长篇小说大纲生成效率。
    可以指定要生成的部分编号列表，或自动生成所有待生成的部分。
    """
    logger.info(
        "用户 %s 请求批量生成项目 %s 的章节大纲，part_numbers=%s",
        current_user.id,
        project_id,
        request.part_numbers,
    )

    part_service = PartOutlineService(session)

    return await part_service.batch_generate_chapters(
        project_id=project_id,
        user_id=current_user.id,
        part_numbers=request.part_numbers,
        max_concurrent=request.max_concurrent,
    )


@router.post("/novels/{project_id}/parts/{part_number}/cancel")
async def cancel_part_generation(
    project_id: str,
    part_number: int,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    取消指定部分的章节大纲生成

    设置取消标志，正在生成的任务会在下一次检查点停止。
    只能取消状态为 generating 的部分。
    """
    logger.info("用户 %s 请求取消项目 %s 的第 %d 部分生成", current_user.id, project_id, part_number)

    part_service = PartOutlineService(session)

    success = await part_service.cancel_part_generation(
        project_id=project_id,
        part_number=part_number,
        user_id=current_user.id,
    )

    if success:
        return {
            "success": True,
            "message": f"第 {part_number} 部分的生成正在取消中",
            "part_number": part_number,
        }
    else:
        return {
            "success": False,
            "message": f"第 {part_number} 部分当前无法取消（可能不在生成中）",
            "part_number": part_number,
        }


@router.get("/novels/{project_id}/parts/progress", response_model=PartOutlineGenerationProgress)
async def get_part_outline_progress(
    project_id: str,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> PartOutlineGenerationProgress:
    """
    查询部分大纲生成进度

    用于中断恢复机制，返回所有部分的生成状态。
    前端可根据状态判断哪些部分需要继续生成。
    """
    try:
        logger.info("用户 %s 查询项目 %s 的部分大纲进度", current_user.id, project_id)

        novel_service = NovelService(session)
        part_service = PartOutlineService(session)

        # 验证权限
        await novel_service.ensure_project_owner(project_id, current_user.id)

        # 先清理超时的generating状态（超过15分钟未更新视为超时）
        logger.info("开始清理超时状态...")
        cleaned_count = await part_service.cleanup_stale_generating_status(project_id, timeout_minutes=15)
        if cleaned_count > 0:
            logger.info("清理了 %d 个超时的generating状态", cleaned_count)

        # 获取所有部分大纲
        logger.info("获取所有部分大纲...")
        all_parts = await part_service.repo.get_by_project_id(project_id)

        if not all_parts:
            raise HTTPException(
                status_code=404, detail="尚未生成部分大纲，请先调用生成部分大纲接口"
            )

        completed_count = sum(1 for p in all_parts if p.generation_status == "completed")
        all_completed = completed_count == len(all_parts)

        logger.info("转换数据为schema...")
        return PartOutlineGenerationProgress(
            parts=[part_service._to_schema(p) for p in all_parts],
            total_parts=len(all_parts),
            completed_parts=completed_count,
            status="completed" if all_completed else "partial",
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("查询部分大纲进度失败: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"查询进度失败: {str(exc)}")
