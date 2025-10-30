import json
import logging
from typing import Dict, List
from urllib.parse import quote

from fastapi import APIRouter, Body, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from io import BytesIO
from datetime import datetime

from ...core.state_machine import ProjectStatus
from ...core.dependencies import get_current_user
from ...db.session import get_session
from ...schemas.novel import (
    Blueprint,
    BlueprintGenerationResponse,
    BlueprintPatch,
    BlueprintRefineRequest,
    Chapter as ChapterSchema,
    ConverseRequest,
    ConverseResponse,
    NovelProject as NovelProjectSchema,
    NovelProjectSummary,
    NovelSectionResponse,
    NovelSectionType,
)
from ...schemas.user import UserInDB
from ...services.llm_service import LLMService
from ...services.novel_service import NovelService
from ...services.prompt_service import PromptService
from ...utils.json_utils import remove_think_tags, unwrap_markdown_json

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/novels", tags=["Novels"])

JSON_RESPONSE_INSTRUCTION = """
IMPORTANT: 你的回复必须是合法的 JSON 对象，并严格包含以下字段：
{
  "ai_message": "string",
  "ui_control": {
    "type": "single_choice | text_input | info_display",
    "options": [
      {"id": "option_1", "label": "string"}
    ],
    "placeholder": "string"
  },
  "conversation_state": {},
  "is_complete": false
}

**重要说明：**
- 在对话进行中，`is_complete` 必须为 `false`
- 当「内部信息清单」中的所有项目都已完成，准备结束对话时，`is_complete` 必须设置为 `true`
- 当 `is_complete` 为 `true` 时，用户将看到"生成蓝图"按钮

不要输出额外的文本或解释。
"""


def _ensure_prompt(prompt: str | None, name: str) -> str:
    if not prompt:
        raise HTTPException(status_code=500, detail=f"未配置名为 {name} 的提示词，请联系管理员")
    return prompt


@router.post("", response_model=NovelProjectSchema, status_code=status.HTTP_201_CREATED)
async def create_novel(
    title: str = Body(...),
    initial_prompt: str = Body(...),
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> NovelProjectSchema:
    """为当前用户创建一个新的小说项目。"""
    novel_service = NovelService(session)
    project = await novel_service.create_project(current_user.id, title, initial_prompt)
    logger.info("用户 %s 创建项目 %s", current_user.id, project.id)
    return await novel_service.get_project_schema(project.id, current_user.id)


@router.get("", response_model=List[NovelProjectSummary])
async def list_novels(
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> List[NovelProjectSummary]:
    """列出用户的全部小说项目摘要信息。"""
    novel_service = NovelService(session)
    projects = await novel_service.list_projects_for_user(current_user.id)
    logger.info("用户 %s 获取项目列表，共 %s 个", current_user.id, len(projects))
    return projects


@router.get("/{project_id}", response_model=NovelProjectSchema)
async def get_novel(
    project_id: str,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> NovelProjectSchema:
    novel_service = NovelService(session)
    logger.info("用户 %s 查询项目 %s", current_user.id, project_id)
    return await novel_service.get_project_schema(project_id, current_user.id)


@router.get("/{project_id}/sections/{section}", response_model=NovelSectionResponse)
async def get_novel_section(
    project_id: str,
    section: NovelSectionType,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> NovelSectionResponse:
    novel_service = NovelService(session)
    logger.info("用户 %s 获取项目 %s 的 %s 区段", current_user.id, project_id, section)
    return await novel_service.get_section_data(project_id, current_user.id, section)


@router.get("/{project_id}/chapters/{chapter_number}", response_model=ChapterSchema)
async def get_chapter(
    project_id: str,
    chapter_number: int,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> ChapterSchema:
    novel_service = NovelService(session)
    logger.info("用户 %s 获取项目 %s 第 %s 章", current_user.id, project_id, chapter_number)
    return await novel_service.get_chapter_schema(project_id, current_user.id, chapter_number)


@router.delete("", status_code=status.HTTP_200_OK)
async def delete_novels(
    project_ids: List[str] = Body(...),
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> Dict[str, str]:
    novel_service = NovelService(session)
    await novel_service.delete_projects(project_ids, current_user.id)
    logger.info("用户 %s 删除项目 %s", current_user.id, project_ids)
    return {"status": "success", "message": f"成功删除 {len(project_ids)} 个项目"}


@router.post("/{project_id}/concept/converse", response_model=ConverseResponse)
async def converse_with_concept(
    project_id: str,
    request: ConverseRequest,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> ConverseResponse:
    """与概念设计师（LLM）进行对话，引导蓝图筹备。"""
    novel_service = NovelService(session)
    prompt_service = PromptService(session)
    llm_service = LLMService(session)

    project = await novel_service.ensure_project_owner(project_id, current_user.id)

    history_records = await novel_service.list_conversations(project_id)
    logger.info(
        "项目 %s 概念对话请求，用户 %s，历史记录 %s 条",
        project_id,
        current_user.id,
        len(history_records),
    )
    conversation_history = [
        {"role": record.role, "content": record.content}
        for record in history_records
    ]
    user_content = json.dumps(request.user_input, ensure_ascii=False)
    conversation_history.append({"role": "user", "content": user_content})

    system_prompt = _ensure_prompt(await prompt_service.get_prompt("concept"), "concept")
    system_prompt = f"{system_prompt}\n{JSON_RESPONSE_INSTRUCTION}"

    llm_response = await llm_service.get_llm_response(
        system_prompt=system_prompt,
        conversation_history=conversation_history,
        temperature=0.8,
        user_id=current_user.id,
        timeout=240.0,
    )
    llm_response = remove_think_tags(llm_response)

    try:
        normalized = unwrap_markdown_json(llm_response)
        parsed = json.loads(normalized)
    except json.JSONDecodeError as exc:
        logger.exception(
            "Failed to parse concept converse response: project_id=%s user_id=%s normalized=%s",
            project_id,
            current_user.id,
            normalized,
        )
        raise HTTPException(status_code=500, detail="AI 返回内容不是有效的 JSON") from exc

    await novel_service.append_conversation(project_id, "user", user_content)
    await novel_service.append_conversation(project_id, "assistant", normalized)

    logger.info("项目 %s 概念对话完成，is_complete=%s", project_id, parsed.get("is_complete"))

    if parsed.get("is_complete"):
        parsed["ready_for_blueprint"] = True

    parsed.setdefault("conversation_state", parsed.get("conversation_state", {}))
    return ConverseResponse(**parsed)


@router.post("/{project_id}/blueprint/generate", response_model=BlueprintGenerationResponse)
async def generate_blueprint(
    project_id: str,
    force_regenerate: bool = False,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> BlueprintGenerationResponse:
    """根据完整对话生成可执行的小说蓝图。"""
    logger.info("=== 蓝图生成接口调用 CODE_VERSION=2025-10-27-v2 ===")
    novel_service = NovelService(session)
    prompt_service = PromptService(session)
    llm_service = LLMService(session)

    project = await novel_service.ensure_project_owner(project_id, current_user.id)
    logger.info("项目 %s 开始生成蓝图", project_id)

    # 检查是否已有章节大纲，如果有且未强制重新生成，则返回警告
    if not force_regenerate:
        outline_count = await novel_service.count_chapter_outlines(project_id)
        if outline_count > 0:
            logger.warning("项目 %s 已有 %d 个章节大纲，需要用户确认是否删除", project_id, outline_count)
            raise HTTPException(
                status_code=409,
                detail=f"项目已有 {outline_count} 个章节大纲，重新生成蓝图将删除所有章节大纲。请确认后重试。"
            )

    history_records = await novel_service.list_conversations(project_id)
    if not history_records:
        raise HTTPException(status_code=400, detail="缺少对话历史，无法生成蓝图")

    formatted_history: List[Dict[str, str]] = []
    for record in history_records:
        role = record.role
        content = record.content
        if not role or not content:
            continue
        try:
            normalized = unwrap_markdown_json(content)
            data = json.loads(normalized)
            if role == "user":
                user_value = data.get("value", data)
                if isinstance(user_value, str):
                    formatted_history.append({"role": "user", "content": user_value})
            elif role == "assistant":
                ai_message = data.get("ai_message") if isinstance(data, dict) else None
                if ai_message:
                    formatted_history.append({"role": "assistant", "content": ai_message})
        except (json.JSONDecodeError, AttributeError):
            continue

    if not formatted_history:
        raise HTTPException(status_code=400, detail="无法从历史对话中提取内容")

    system_prompt = _ensure_prompt(await prompt_service.get_prompt("screenwriting"), "screenwriting")
    blueprint_raw = await llm_service.get_llm_response(
        system_prompt=system_prompt,
        conversation_history=formatted_history,
        temperature=0.3,
        user_id=current_user.id,
        timeout=480.0,
        max_tokens=8000,  # DeepSeek 限制最大 8192
    )
    blueprint_raw = remove_think_tags(blueprint_raw)

    blueprint_normalized = unwrap_markdown_json(blueprint_raw)
    try:
        blueprint_data = json.loads(blueprint_normalized)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=500, detail="蓝图生成失败，请稍后重试") from exc

    logger.info("项目 %s 蓝图JSON解析成功，total_chapters=%s", project_id, blueprint_data.get('total_chapters'))
    blueprint = Blueprint(**blueprint_data)

    # 强制工作流分离：蓝图生成阶段不包含章节大纲
    # 即使LLM违反指令生成了章节大纲，也要强制清空
    if blueprint.chapter_outline:
        logger.warning(
            "项目 %s 蓝图生成时包含了 %d 个章节大纲，违反工作流设计，已强制清空",
            project_id,
            len(blueprint.chapter_outline),
        )
        blueprint.chapter_outline = []

    # 数据校验与降级：total_chapters 必须大于0
    total_chapters = blueprint.total_chapters or 0
    if total_chapters <= 0:
        # 降级策略1：尝试从对话历史中解析用户明确指定的章节数
        import re
        extracted_chapters = None
        for msg in reversed(formatted_history):  # 从最新的对话开始查找
            if msg.get("role") == "user":
                content = msg.get("content", "")
                # 使用更精确的正则表达式，避免误匹配章节引用
                # 优先匹配明确指定章节数的表述
                patterns = [
                    r'(?:写|创作|生成|共|总共|一共|大概|大约)[\s\w]*?(\d+)\s*章',  # "写100章"、"共100章"
                    r'(\d+)\s*章(?:左右|以上|以内|的小说)',  # "100章左右"、"100章的小说"
                    r'(?:小说|故事)[\s\w]{0,10}?(\d+)\s*章',  # "小说100章"
                ]
                for pattern in patterns:
                    match = re.search(pattern, content)
                    if match:
                        candidate = int(match.group(1))
                        # 排除不合理的章节数（避免误匹配年份等）
                        if 5 <= candidate <= 10000:
                            extracted_chapters = candidate
                            logger.info(
                                "项目 %s 从对话中解析到用户指定的章节数: %d（原文：%s，匹配模式：%s）",
                                project_id,
                                extracted_chapters,
                                content[:50],
                                pattern
                            )
                            break
                if extracted_chapters:
                    break

        # 降级策略2：如果仍未找到，根据对话轮次估算
        if extracted_chapters:
            default_chapters = extracted_chapters
        else:
            conversation_rounds = len(history_records) // 2
            if conversation_rounds <= 5:
                default_chapters = 30  # 简单短篇故事
            elif conversation_rounds <= 10:
                default_chapters = 80  # 中等复杂度
            else:
                default_chapters = 150  # 复杂史诗

        logger.warning(
            "项目 %s LLM返回的total_chapters=%s无效，使用%s值 %d",
            project_id,
            total_chapters,
            "解析" if extracted_chapters else "默认",
            default_chapters,
        )
        blueprint.total_chapters = default_chapters
        total_chapters = default_chapters

        # 同时更新 needs_part_outlines 字段（根据章节数判断）
        if default_chapters > 50:
            blueprint.needs_part_outlines = True
            logger.info("项目 %s 章节数为 %d，自动设置 needs_part_outlines=True", project_id, default_chapters)
        else:
            blueprint.needs_part_outlines = False
            logger.info("项目 %s 章节数为 %d，自动设置 needs_part_outlines=False", project_id, default_chapters)

    # 新流程：蓝图生成阶段不包含章节大纲，统一设置为 blueprint_ready
    await novel_service.transition_project_status(project, ProjectStatus.BLUEPRINT_READY.value)

    needs_part_outlines = blueprint.needs_part_outlines

    logger.info(
        "项目 %s 蓝图生成完成，总章节数=%d，需要部分大纲=%s",
        project_id,
        total_chapters,
        needs_part_outlines,
    )

    # 根据章节数生成不同的提示消息
    if needs_part_outlines:
        ai_message = (
            f"太棒了！基础蓝图已生成完成。您的小说计划 {total_chapters} 章，"
            "接下来请在详情页点击「生成部分大纲」按钮来规划整体结构，"
            "然后再生成详细的章节大纲。"
        )
    else:
        ai_message = (
            f"太棒了！基础蓝图已生成完成。您的小说计划 {total_chapters} 章，"
            "接下来请在详情页点击「生成章节大纲」按钮来规划具体章节。"
        )

    await novel_service.replace_blueprint(project_id, blueprint)
    if blueprint.title:
        project.title = blueprint.title
        await session.commit()
        logger.info("项目 %s 更新标题为 %s", project_id, blueprint.title)

    return BlueprintGenerationResponse(blueprint=blueprint, ai_message=ai_message)


@router.post("/{project_id}/chapter-outlines/generate")
async def generate_chapter_outlines(
    project_id: str,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
):
    """为短篇小说（≤50章）一次性生成全部章节大纲"""
    novel_service = NovelService(session)
    prompt_service = PromptService(session)
    llm_service = LLMService(session)

    project = await novel_service.ensure_project_owner(project_id, current_user.id)
    logger.info("项目 %s 开始生成章节大纲", project_id)

    # 检查蓝图是否存在
    project_schema = await novel_service.get_project_schema(project_id, current_user.id)
    if not project_schema.blueprint:
        raise HTTPException(status_code=400, detail="项目蓝图未生成，无法生成章节大纲")

    blueprint = project_schema.blueprint

    # 检查是否为短篇流程（不需要部分大纲）
    if blueprint.needs_part_outlines:
        raise HTTPException(
            status_code=400,
            detail="该项目为长篇小说（>50章），请先生成部分大纲，再分批生成章节大纲",
        )

    total_chapters = blueprint.total_chapters or 0
    if total_chapters == 0:
        raise HTTPException(status_code=400, detail="蓝图未设置总章节数")

    # 检查是否已有章节大纲
    if blueprint.chapter_outline and len(blueprint.chapter_outline) > 0:
        logger.info("项目 %s 已有 %d 个章节大纲，跳过生成", project_id, len(blueprint.chapter_outline))
        raise HTTPException(
            status_code=400,
            detail=f"章节大纲已存在（共{len(blueprint.chapter_outline)}章），如需重新生成请先删除现有大纲",
        )

    # 构建蓝图JSON（用于LLM上下文）
    blueprint_context = {
        "title": blueprint.title,
        "target_audience": blueprint.target_audience,
        "genre": blueprint.genre,
        "style": blueprint.style,
        "tone": blueprint.tone,
        "one_sentence_summary": blueprint.one_sentence_summary,
        "full_synopsis": blueprint.full_synopsis,
        "world_setting": blueprint.world_setting,
        "characters": blueprint.characters,
        "relationships": blueprint.relationships,
        "chapter_outline": [],  # 当前为空，等待生成
    }

    # 构建用户输入（复用 outline.md 提示词格式）
    user_prompt = json.dumps(
        {
            "novel_blueprint": blueprint_context,
            "wait_to_generate": {"start_chapter": 1, "num_chapters": total_chapters},
        },
        ensure_ascii=False,
        indent=2,
    )

    # 获取提示词
    system_prompt = _ensure_prompt(await prompt_service.get_prompt("outline"), "outline")

    # 调用LLM生成章节大纲
    logger.info("调用LLM生成 %d 个章节大纲", total_chapters)
    response = await llm_service.get_llm_response(
        system_prompt=system_prompt,
        conversation_history=[{"role": "user", "content": user_prompt}],
        temperature=0.3,
        user_id=current_user.id,
        timeout=300.0,
        max_tokens=8000,
    )

    # 解析响应
    response_cleaned = remove_think_tags(response)
    response_normalized = unwrap_markdown_json(response_cleaned)

    try:
        result = json.loads(response_normalized)
    except json.JSONDecodeError as exc:
        logger.exception("解析章节大纲JSON失败: project_id=%s", project_id)
        raise HTTPException(status_code=500, detail="LLM返回的章节大纲格式错误") from exc

    chapters_data = result.get("chapters", [])
    if not chapters_data:
        raise HTTPException(status_code=500, detail="LLM未返回有效的章节大纲")

    # 保存章节大纲到数据库
    from ..models.novel import ChapterOutline
    from sqlalchemy import delete

    # 清空旧的章节大纲（防御性编程，虽然前面已检查）
    await session.execute(delete(ChapterOutline).where(ChapterOutline.project_id == project_id))

    # 插入新的章节大纲
    for chapter_data in chapters_data:
        chapter_number = chapter_data.get("chapter_number")
        if not chapter_number:
            continue

        outline = ChapterOutline(
            project_id=project_id,
            chapter_number=chapter_number,
            title=chapter_data.get("title", f"第{chapter_number}章"),
            summary=chapter_data.get("summary", ""),
        )
        session.add(outline)

    # 更新项目状态为章节大纲完成
    await novel_service.transition_project_status(project, ProjectStatus.CHAPTER_OUTLINES_READY.value)

    logger.info("项目 %s 章节大纲生成完成，共 %d 章", project_id, len(chapters_data))

    return {
        "message": "章节大纲生成完成",
        "total_chapters": len(chapters_data),
        "status": ProjectStatus.CHAPTER_OUTLINES_READY.value,
    }


@router.post("/{project_id}/blueprint/save", response_model=NovelProjectSchema)
async def save_blueprint(
    project_id: str,
    blueprint_data: Blueprint | None = Body(None),
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> NovelProjectSchema:
    """保存蓝图信息，可用于手动覆盖自动生成结果。"""
    novel_service = NovelService(session)
    project = await novel_service.ensure_project_owner(project_id, current_user.id)

    if blueprint_data:
        await novel_service.replace_blueprint(project_id, blueprint_data)
        if blueprint_data.title:
            project.title = blueprint_data.title
            await session.commit()
        logger.info("项目 %s 手动保存蓝图", project_id)
    else:
        raise HTTPException(status_code=400, detail="缺少蓝图数据")

    return await novel_service.get_project_schema(project_id, current_user.id)


@router.post("/{project_id}/blueprint/refine", response_model=BlueprintGenerationResponse)
async def refine_blueprint(
    project_id: str,
    request: BlueprintRefineRequest,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> BlueprintGenerationResponse:
    """基于用户的优化指令，迭代改进现有蓝图"""
    novel_service = NovelService(session)
    prompt_service = PromptService(session)
    llm_service = LLMService(session)

    project = await novel_service.ensure_project_owner(project_id, current_user.id)
    logger.info("项目 %s 开始优化蓝图，优化指令：%s", project_id, request.refinement_instruction)

    # 获取当前蓝图
    project_schema = await novel_service.get_project_schema(project_id, current_user.id)
    if not project_schema.blueprint:
        raise HTTPException(status_code=400, detail="当前项目没有蓝图，请先生成初始蓝图")

    # 将当前蓝图转为JSON字符串
    current_blueprint_json = project_schema.blueprint.model_dump_json(
        indent=2,
        exclude_none=True,
        by_alias=False
    )

    # 构造优化提示词
    system_prompt = _ensure_prompt(
        await prompt_service.get_prompt("screenwriting"),
        "screenwriting"
    )

    # 在系统提示词后添加优化任务说明
    refinement_context = f"""

## 蓝图优化任务

你正在进行的是蓝图**优化任务**，而非从零开始创建。

### 当前蓝图（JSON格式）：
```json
{current_blueprint_json}
```

### 用户的优化需求：
{request.refinement_instruction}

### 优化要求：
1. **保持现有设定的连贯性**：除非用户明确要求修改，否则保留现有的核心设定
2. **针对性改进**：重点优化用户指出的方面
3. **增量改进**：在现有基础上完善，而非推翻重来
4. **输出完整蓝图**：返回优化后的完整蓝图JSON，确保所有字段完整

请基于以上信息，生成优化后的完整蓝图。
"""

    full_system_prompt = system_prompt + refinement_context

    # 调用LLM生成优化后的蓝图
    blueprint_raw = await llm_service.get_llm_response(
        system_prompt=full_system_prompt,
        conversation_history=[],  # 优化任务不需要对话历史，所有上下文已在系统提示词中
        temperature=0.3,
        user_id=current_user.id,
        timeout=480.0,
        max_tokens=8000,  # DeepSeek 限制最大 8192
    )
    blueprint_raw = remove_think_tags(blueprint_raw)

    # 解析蓝图
    blueprint_normalized = unwrap_markdown_json(blueprint_raw)
    try:
        blueprint_data = json.loads(blueprint_normalized)
    except json.JSONDecodeError as exc:
        logger.exception("蓝图优化失败，无法解析JSON：project_id=%s", project_id)
        raise HTTPException(status_code=500, detail="蓝图优化失败，请稍后重试") from exc

    # 验证并保存优化后的蓝图
    refined_blueprint = Blueprint(**blueprint_data)
    await novel_service.replace_blueprint(project_id, refined_blueprint)

    # 更新项目标题（如果蓝图中有）
    if refined_blueprint.title:
        project.title = refined_blueprint.title
        await session.commit()
        logger.info("项目 %s 优化完成，更新标题为 %s", project_id, refined_blueprint.title)

    ai_message = (
        f"已根据您的要求优化蓝图：「{request.refinement_instruction}」。"
        "请查看优化后的内容，如需继续调整可再次提出优化建议。"
    )

    return BlueprintGenerationResponse(blueprint=refined_blueprint, ai_message=ai_message)


@router.patch("/{project_id}/blueprint", response_model=NovelProjectSchema)
async def patch_blueprint(
    project_id: str,
    payload: BlueprintPatch,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> NovelProjectSchema:
    """局部更新蓝图字段，对世界观或角色做微调。"""
    novel_service = NovelService(session)
    project = await novel_service.ensure_project_owner(project_id, current_user.id)

    update_data = payload.model_dump(exclude_unset=True)
    await novel_service.patch_blueprint(project_id, update_data)
    logger.info("项目 %s 局部更新蓝图字段：%s", project_id, list(update_data.keys()))
    return await novel_service.get_project_schema(project_id, current_user.id)


@router.get("/{project_id}/export")
async def export_chapters(
    project_id: str,
    format: str = "txt",
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> StreamingResponse:
    """导出所有已完成的章节内容"""
    novel_service = NovelService(session)
    project = await novel_service.ensure_project_owner(project_id, current_user.id)

    # 获取项目完整信息
    project_schema = await novel_service.get_project_schema(project_id, current_user.id)

    # 收集所有已选择版本的章节
    completed_chapters = []
    outlines_map = {outline.chapter_number: outline for outline in project.outlines}

    for chapter in sorted(project.chapters, key=lambda x: x.chapter_number):
        if chapter.selected_version and chapter.selected_version.content:
            outline = outlines_map.get(chapter.chapter_number)
            completed_chapters.append({
                "chapter_number": chapter.chapter_number,
                "title": outline.title if outline else f"第{chapter.chapter_number}章",
                "content": chapter.selected_version.content,
            })

    if not completed_chapters:
        raise HTTPException(status_code=404, detail="没有已完成的章节可供导出")

    # 获取小说标题
    novel_title = project.title or "未命名小说"
    blueprint_title = project_schema.blueprint.title if project_schema.blueprint else None
    if blueprint_title:
        novel_title = blueprint_title

    # 生成导出内容
    if format.lower() == "markdown" or format.lower() == "md":
        content = _generate_markdown_export(novel_title, completed_chapters)
        filename = f"{novel_title}.md"
        media_type = "text/markdown"
    else:  # 默认为 txt
        content = _generate_txt_export(novel_title, completed_chapters)
        filename = f"{novel_title}.txt"
        media_type = "text/plain"

    # 创建字节流
    buffer = BytesIO(content.encode("utf-8"))

    # 对文件名进行 URL 编码以支持中文（RFC 2231）
    encoded_filename = quote(filename.encode('utf-8'))

    logger.info(
        "用户 %s 导出项目 %s，格式：%s，章节数：%s",
        current_user.id,
        project_id,
        format,
        len(completed_chapters),
    )

    return StreamingResponse(
        buffer,
        media_type=media_type,
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}",
            "Content-Type": f"{media_type}; charset=utf-8",
        },
    )


def _generate_txt_export(novel_title: str, chapters: List[Dict]) -> str:
    """生成 TXT 格式的导出内容"""
    lines = []

    # 添加标题和元信息
    lines.append("=" * 60)
    lines.append(novel_title)
    lines.append("=" * 60)
    lines.append("")
    lines.append(f"导出时间：{datetime.now().strftime('%Y年%m月%d日 %H:%M')}")
    lines.append(f"总章节数：{len(chapters)}")
    lines.append("")
    lines.append("=" * 60)
    lines.append("")

    # 添加章节内容
    for chapter in chapters:
        lines.append("")
        lines.append(f"第{chapter['chapter_number']}章 {chapter['title']}")
        lines.append("-" * 60)
        lines.append("")
        lines.append(chapter["content"])
        lines.append("")
        lines.append("")

    return "\n".join(lines)


def _generate_markdown_export(novel_title: str, chapters: List[Dict]) -> str:
    """生成 Markdown 格式的导出内容"""
    lines = []

    # 添加标题和元信息
    lines.append(f"# {novel_title}")
    lines.append("")
    lines.append(f"> 导出时间：{datetime.now().strftime('%Y年%m月%d日 %H:%M')}")
    lines.append(f"> 总章节数：{len(chapters)}")
    lines.append("")
    lines.append("---")
    lines.append("")

    # 添加目录
    lines.append("## 目录")
    lines.append("")
    for chapter in chapters:
        lines.append(f"- [第{chapter['chapter_number']}章 {chapter['title']}](#第{chapter['chapter_number']}章)")
    lines.append("")
    lines.append("---")
    lines.append("")

    # 添加章节内容
    for chapter in chapters:
        lines.append(f"## 第{chapter['chapter_number']}章 {chapter['title']}")
        lines.append("")
        lines.append(chapter["content"])
        lines.append("")
        lines.append("---")
        lines.append("")

    return "\n".join(lines)
