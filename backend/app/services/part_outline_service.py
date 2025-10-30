import asyncio
import json
import logging
import math
import uuid
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.state_machine import ProjectStatus
from ..models.part_outline import PartOutline
from ..models.novel import ChapterOutline, NovelProject
from ..repositories.part_outline_repository import PartOutlineRepository
from ..repositories.novel_repository import NovelRepository
from ..schemas.novel import (
    PartOutline as PartOutlineSchema,
    PartOutlineGenerationProgress,
    ChapterOutline as ChapterOutlineSchema,
)
from ..utils.json_utils import remove_think_tags, unwrap_markdown_json
from .llm_service import LLMService
from .prompt_service import PromptService
from .novel_service import NovelService

logger = logging.getLogger(__name__)


class GenerationCancelledException(Exception):
    """生成被用户取消的异常"""
    pass


class PartOutlineService:
    """部分大纲服务，负责长篇小说的分层大纲生成"""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = PartOutlineRepository(session)
        self.novel_repo = NovelRepository(session)
        self.llm_service = LLMService(session)
        self.prompt_service = PromptService(session)

    async def _check_if_cancelled(self, part_outline: PartOutline) -> bool:
        """
        检查部分大纲是否被请求取消

        参数：
            part_outline: 部分大纲对象

        返回：
            bool: 如果被取消返回True

        抛出：
            GenerationCancelledException: 如果检测到取消状态
        """
        # 刷新对象以获取最新状态
        await self.session.refresh(part_outline)

        if part_outline.generation_status == "cancelling":
            logger.info("检测到第 %d 部分被请求取消生成", part_outline.part_number)
            raise GenerationCancelledException(f"第 {part_outline.part_number} 部分的生成已被取消")

        return False

    async def cancel_part_generation(
        self,
        project_id: str,
        part_number: int,
        user_id: int,
    ) -> bool:
        """
        取消指定部分的大纲生成

        参数：
            project_id: 项目ID
            part_number: 部分编号
            user_id: 用户ID

        返回：
            bool: 是否成功设置取消标志
        """
        # 验证权限
        project = await self.novel_repo.get_by_id(project_id)
        if not project or project.user_id != user_id:
            raise HTTPException(status_code=404, detail="项目不存在或无权访问")

        # 获取部分大纲
        part_outline = await self.repo.get_by_part_number(project_id, part_number)
        if not part_outline:
            raise HTTPException(status_code=404, detail=f"未找到第 {part_number} 部分的大纲")

        # 只有正在生成的任务才能取消
        if part_outline.generation_status != "generating":
            logger.warning(
                "第 %d 部分当前状态为 %s，无法取消",
                part_number,
                part_outline.generation_status,
            )
            return False

        # 设置为取消中状态
        await self.repo.update_status(part_outline, "cancelling", part_outline.progress)
        await self.session.commit()

        logger.info("第 %d 部分已设置为取消中状态", part_number)
        return True

    async def cleanup_stale_generating_status(
        self,
        project_id: str,
        timeout_minutes: int = 15,
    ) -> int:
        """
        清理超时的generating状态，将其改为failed

        参数：
            project_id: 项目ID
            timeout_minutes: 超时时间（分钟），默认15分钟

        返回：
            int: 清理的数量
        """
        all_parts = await self.repo.get_by_project_id(project_id)
        timeout_threshold = datetime.now(timezone.utc) - timedelta(minutes=timeout_minutes)
        cleaned_count = 0

        for part in all_parts:
            # 检查是否处于generating状态且更新时间超过阈值
            if part.generation_status == "generating":
                # 防御性检查：updated_at可能为None
                if part.updated_at is None or part.updated_at < timeout_threshold:
                    logger.warning(
                        "检测到第 %d 部分超时（超过%d分钟未更新），将状态改为failed",
                        part.part_number,
                        timeout_minutes,
                    )
                    await self.repo.update_status(part, "failed", 0)
                    cleaned_count += 1

        if cleaned_count > 0:
            await self.session.commit()
            logger.info("项目 %s 清理了 %d 个超时状态", project_id, cleaned_count)

        return cleaned_count

    async def generate_part_outlines(
        self,
        project_id: str,
        user_id: int,
        total_chapters: int,
        chapters_per_part: int = 25,
    ) -> PartOutlineGenerationProgress:
        """
        生成部分大纲（大纲的大纲）

        参数：
            project_id: 项目ID
            user_id: 用户ID
            total_chapters: 总章节数
            chapters_per_part: 每个部分包含的章节数（默认25章）

        返回：
            PartOutlineGenerationProgress: 生成进度和结果
        """
        logger.info("开始为项目 %s 生成部分大纲，总章节数=%d", project_id, total_chapters)

        # 检查章节数是否需要分部分
        if total_chapters <= 50:
            raise HTTPException(
                status_code=400,
                detail=f"章节数为 {total_chapters}，不需要使用部分大纲功能（仅适用于51章以上的长篇小说）",
            )

        # 获取项目信息
        project = await self.novel_repo.get_by_id(project_id)
        if not project or project.user_id != user_id:
            raise HTTPException(status_code=404, detail="项目不存在或无权访问")

        if not project.blueprint:
            raise HTTPException(status_code=400, detail="项目蓝图未生成，无法创建部分大纲")

        # 从blueprint和关联表获取数据
        world_setting = project.blueprint.world_setting or {}
        full_synopsis = project.blueprint.full_synopsis or ""

        # 将BlueprintCharacter模型转换为字典列表
        characters = [
            {
                "name": char.name,
                "identity": char.identity or "",
                "personality": char.personality or "",
                "goals": char.goals or "",
                "abilities": char.abilities or "",
                **(char.extra or {}),
            }
            for char in sorted(project.characters, key=lambda c: c.position)
        ]

        # 计算部分数量
        total_parts = math.ceil(total_chapters / chapters_per_part)
        logger.info("计划生成 %d 个部分，每部分约 %d 章", total_parts, chapters_per_part)

        # 构建提示词
        system_prompt = await self.prompt_service.get_prompt("part_outline")
        user_prompt = self._build_part_outline_prompt(
            total_chapters=total_chapters,
            chapters_per_part=chapters_per_part,
            total_parts=total_parts,
            world_setting=world_setting,
            characters=characters,
            full_synopsis=full_synopsis,
        )

        # 调用LLM生成部分大纲
        logger.info("调用LLM生成部分大纲，total_parts=%d", total_parts)
        response = await self.llm_service.get_llm_response(
            system_prompt=system_prompt,
            conversation_history=[{"role": "user", "content": user_prompt}],
            temperature=0.3,
            user_id=user_id,
            response_format="json_object",
            timeout=300.0,
        )

        # 解析响应
        cleaned = remove_think_tags(response)
        unwrapped = unwrap_markdown_json(cleaned)
        try:
            result = json.loads(unwrapped)
        except json.JSONDecodeError as exc:
            logger.error("解析部分大纲JSON失败: %s", exc)
            raise HTTPException(status_code=500, detail="LLM返回的部分大纲格式错误")

        parts_data = result.get("parts", [])
        if not parts_data:
            raise HTTPException(status_code=500, detail="LLM未返回有效的部分大纲")

        # 删除旧的部分大纲（如果存在）
        await self.repo.delete_by_project_id(project_id)

        # 创建部分大纲模型
        part_outlines = []
        for idx, part_data in enumerate(parts_data):
            part = PartOutline(
                id=str(uuid.uuid4()),
                project_id=project_id,
                part_number=part_data.get("part_number", idx + 1),
                title=part_data.get("title", f"第{idx + 1}部分"),
                start_chapter=part_data.get("start_chapter"),
                end_chapter=part_data.get("end_chapter"),
                summary=part_data.get("summary", ""),
                theme=part_data.get("theme", ""),
                key_events=part_data.get("key_events", []),
                character_arcs=part_data.get("character_arcs", {}),
                conflicts=part_data.get("conflicts", []),
                ending_hook=part_data.get("ending_hook"),
                generation_status="pending",
                progress=0,
            )
            part_outlines.append(part)

        # 批量保存到数据库
        await self.repo.batch_create(part_outlines)
        await self.session.commit()

        logger.info("成功生成 %d 个部分大纲", len(part_outlines))

        # 更新项目状态为部分大纲完成
        novel_service = NovelService(self.session)
        await novel_service.transition_project_status(project, ProjectStatus.PART_OUTLINES_READY.value)
        logger.info("项目 %s 状态已更新为 %s", project_id, ProjectStatus.PART_OUTLINES_READY.value)

        # 返回进度信息
        return PartOutlineGenerationProgress(
            parts=[self._to_schema(p) for p in part_outlines],
            total_parts=len(part_outlines),
            completed_parts=0,
            status="completed",
        )

    async def generate_part_chapters(
        self,
        project_id: str,
        user_id: int,
        part_number: int,
        regenerate: bool = False,
    ) -> List[ChapterOutlineSchema]:
        """
        为指定部分生成详细的章节大纲

        参数：
            project_id: 项目ID
            user_id: 用户ID
            part_number: 部分编号
            regenerate: 是否重新生成（默认False，如果章节已存在则跳过）

        返回：
            List[ChapterOutlineSchema]: 生成的章节大纲列表
        """
        logger.info("开始为项目 %s 的第 %d 部分生成章节大纲", project_id, part_number)

        # 获取部分大纲
        part_outline = await self.repo.get_by_part_number(project_id, part_number)
        if not part_outline:
            raise HTTPException(status_code=404, detail=f"未找到第 {part_number} 部分的大纲")

        # 获取项目信息
        project = await self.novel_repo.get_by_id(project_id)
        if not project or project.user_id != user_id:
            raise HTTPException(status_code=404, detail="项目不存在或无权访问")

        if not project.blueprint:
            raise HTTPException(status_code=400, detail="项目蓝图未生成")

        # 更新状态为generating
        await self.repo.update_status(part_outline, "generating", 0)
        await self.session.commit()

        generation_successful = False  # 追踪是否成功完成

        try:
            # 检查是否已被取消
            await self._check_if_cancelled(part_outline)

            # 构建提示词
            system_prompt = await self.prompt_service.get_prompt("screenwriting")
            user_prompt = await self._build_part_chapters_prompt(
                part_outline=part_outline,
                project=project,
            )

            # 再次检查取消状态（在LLM调用前）
            await self._check_if_cancelled(part_outline)

            # 调用LLM生成章节大纲
            logger.info(
                "调用LLM生成第 %d 部分的章节大纲（章节 %d-%d）",
                part_number,
                part_outline.start_chapter,
                part_outline.end_chapter,
            )
            response = await self.llm_service.get_llm_response(
                system_prompt=system_prompt,
                conversation_history=[{"role": "user", "content": user_prompt}],
                temperature=0.3,
                user_id=user_id,
                response_format="json_object",
                timeout=300.0,
            )

            # LLM调用完成后检查取消状态
            await self._check_if_cancelled(part_outline)

            # 解析响应
            cleaned = remove_think_tags(response)
            unwrapped = unwrap_markdown_json(cleaned)
            try:
                result = json.loads(unwrapped)
            except json.JSONDecodeError as exc:
                logger.error("解析章节大纲JSON失败: %s", exc)
                raise HTTPException(status_code=500, detail="LLM返回的章节大纲格式错误")

            chapters_data = result.get("chapter_outline", [])
            if not chapters_data:
                raise HTTPException(status_code=500, detail="LLM未返回有效的章节大纲")

            # 将章节大纲插入数据库
            for chapter_data in chapters_data:
                chapter_number = chapter_data.get("chapter_number")
                if not chapter_number:
                    continue

                # 检查是否已存在
                existing = next(
                    (o for o in project.outlines if o.chapter_number == chapter_number),
                    None,
                )

                if existing and not regenerate:
                    logger.info("章节 %d 大纲已存在，跳过", chapter_number)
                    continue

                if existing:
                    # 更新现有大纲
                    existing.title = chapter_data.get("title", "")
                    existing.summary = chapter_data.get("summary", "")
                else:
                    # 创建新大纲（不设置scene字段，因为数据库模型中不存在）
                    outline = ChapterOutline(
                        project_id=project_id,
                        chapter_number=chapter_number,
                        title=chapter_data.get("title", ""),
                        summary=chapter_data.get("summary", ""),
                    )
                    self.session.add(outline)

            # 标记生成成功
            generation_successful = True

            logger.info("成功为第 %d 部分生成 %d 个章节大纲", part_number, len(chapters_data))

            # 返回章节大纲schema
            return [
                ChapterOutlineSchema(
                    chapter_number=c.get("chapter_number"),
                    title=c.get("title", ""),
                    summary=c.get("summary", ""),
                )
                for c in chapters_data
            ]

        except GenerationCancelledException as exc:
            logger.info("第 %d 部分生成已被用户取消: %s", part_number, exc)
            # 取消异常不需要重新抛出，让finally块处理状态更新

        except Exception as exc:
            logger.error("为第 %d 部分生成章节大纲失败: %s", part_number, exc)
            raise

        finally:
            # 确保状态总是会更新，防止永久卡在generating状态
            try:
                # 再次刷新状态，确保获取最新的generation_status
                await self.session.refresh(part_outline)

                if generation_successful:
                    await self.repo.update_status(part_outline, "completed", 100)
                    status_desc = "completed"
                elif part_outline.generation_status == "cancelling":
                    await self.repo.update_status(part_outline, "cancelled", part_outline.progress)
                    status_desc = "cancelled"
                else:
                    await self.repo.update_status(part_outline, "failed", 0)
                    status_desc = "failed"

                await self.session.commit()
                logger.info("第 %d 部分状态已更新: %s", part_number, status_desc)

                # 检查是否所有部分都已完成，如果是则更新项目状态
                if generation_successful:
                    all_parts = await self.repo.get_by_project_id(project_id)
                    all_completed = all(p.generation_status == "completed" for p in all_parts)

                    if all_completed:
                        project.status = "chapter_outlines_ready"
                        await self.session.commit()
                        logger.info("项目 %s 所有部分大纲已完成，状态已更新为 chapter_outlines_ready", project_id)

            except Exception as status_update_error:
                logger.error("更新第 %d 部分状态失败: %s", part_number, status_update_error)
                # 即使状态更新失败，也不影响原始异常的抛出

    async def batch_generate_chapters(
        self,
        project_id: str,
        user_id: int,
        part_numbers: Optional[List[int]] = None,
        max_concurrent: int = 3,
    ) -> PartOutlineGenerationProgress:
        """
        批量并发生成多个部分的章节大纲

        注意：为避免session并发问题，此方法不直接使用并发。
        建议在API层实现并发控制，每个请求使用独立的session。

        参数：
            project_id: 项目ID
            user_id: 用户ID
            part_numbers: 要生成的部分编号列表（None表示生成所有待生成的部分）
            max_concurrent: 最大并发数（默认3）

        返回：
            PartOutlineGenerationProgress: 生成进度
        """
        logger.info("开始批量生成章节大纲（串行模式），max_concurrent=%d", max_concurrent)

        # 获取要生成的部分
        if part_numbers:
            parts = []
            for pn in part_numbers:
                part = await self.repo.get_by_part_number(project_id, pn)
                if part:
                    parts.append(part)
        else:
            parts = await self.repo.get_pending_parts(project_id)

        if not parts:
            logger.info("没有待生成的部分大纲")
            return PartOutlineGenerationProgress(
                parts=[],
                total_parts=0,
                completed_parts=0,
                status="completed",
            )

        logger.info("共有 %d 个部分待生成（串行执行）", len(parts))

        # 串行生成（避免session并发问题）
        results = []
        for part in parts:
            try:
                logger.info("开始生成第 %d 部分", part.part_number)
                chapters = await self.generate_part_chapters(
                    project_id=project_id,
                    user_id=user_id,
                    part_number=part.part_number,
                    regenerate=False,
                )
                results.append({"success": True, "part_number": part.part_number, "chapters": len(chapters)})
            except Exception as exc:
                logger.error("生成第 %d 部分失败: %s", part.part_number, exc)
                results.append({"success": False, "part_number": part.part_number, "error": str(exc)})

        # 统计结果
        completed = sum(1 for r in results if r["success"])
        failed = len(results) - completed

        logger.info("批量生成完成，成功=%d，失败=%d", completed, failed)

        # 重新加载所有部分大纲
        all_parts = await self.repo.get_by_project_id(project_id)

        return PartOutlineGenerationProgress(
            parts=[self._to_schema(p) for p in all_parts],
            total_parts=len(all_parts),
            completed_parts=sum(1 for p in all_parts if p.generation_status == "completed"),
            status="completed" if failed == 0 else "partial",
        )

    def _build_part_outline_prompt(
        self,
        total_chapters: int,
        chapters_per_part: int,
        total_parts: int,
        world_setting: Dict,
        characters: List[Dict],
        full_synopsis: str,
    ) -> str:
        """构建生成部分大纲的用户提示词"""
        return f"""请基于以下信息，为这部长篇小说生成分层的部分大纲（大纲的大纲）。

## 小说基本信息

总章节数：{total_chapters}
每个部分的章节数：约 {chapters_per_part} 章
需要生成的部分数：{total_parts} 个部分

## 世界观设定

{json.dumps(world_setting, ensure_ascii=False, indent=2)}

## 角色档案

{json.dumps(characters, ensure_ascii=False, indent=2)}

## 主要剧情

{full_synopsis}

## 输出要求

请生成 {total_parts} 个部分的大纲，每个部分应包含：
- part_number: 部分编号（1-{total_parts}）
- title: 部分标题
- start_chapter: 起始章节号
- end_chapter: 结束章节号
- summary: 该部分的剧情摘要（200-300字）
- theme: 该部分的核心主题
- key_events: 关键事件列表（3-5个）
- character_arcs: 角色成长弧线（字典格式，key为角色名，value为成长描述）
- conflicts: 主要冲突列表（2-3个）
- ending_hook: 部分结尾的悬念/钩子

确保：
1. 每个部分的章节范围连续且不重叠
2. 部分之间有清晰的承接关系
3. 整体剧情符合三幕/五幕结构
4. 每个部分都有独立的小高潮
5. 角色成长和剧情推进合理分布

输出JSON格式：
{{
  "parts": [
    {{
      "part_number": 1,
      "title": "...",
      "start_chapter": 1,
      "end_chapter": {chapters_per_part},
      ...
    }},
    ...
  ]
}}
"""

    async def _build_part_chapters_prompt(
        self,
        part_outline: PartOutline,
        project: NovelProject,
    ) -> str:
        """构建生成单个部分章节大纲的用户提示词（异步方法）"""
        # 获取上一部分的ending_hook
        prev_part = None
        if part_outline.part_number > 1:
            prev_part_outline = await self.repo.get_by_part_number(
                project.id, part_outline.part_number - 1
            )
            if prev_part_outline:
                prev_part = prev_part_outline.ending_hook

        # 获取下一部分的summary
        next_part = None
        next_part_outline = await self.repo.get_by_part_number(
            project.id, part_outline.part_number + 1
        )
        if next_part_outline:
            next_part = next_part_outline.summary

        world_setting = project.blueprint.world_setting or {}

        # 转换角色列表
        characters = [
            {
                "name": char.name,
                "identity": char.identity or "",
                "personality": char.personality or "",
                "goals": char.goals or "",
            }
            for char in sorted(project.characters, key=lambda c: c.position)
        ]

        prompt = f"""请基于以下信息，为这部小说的第 {part_outline.part_number} 部分生成详细的章节大纲。

## 部分信息

标题：{part_outline.title}
章节范围：第 {part_outline.start_chapter} 章 - 第 {part_outline.end_chapter} 章
主题：{part_outline.theme or ""}

### 部分摘要
{part_outline.summary or ""}

### 关键事件
{json.dumps(part_outline.key_events or [], ensure_ascii=False, indent=2)}

### 主要冲突
{json.dumps(part_outline.conflicts or [], ensure_ascii=False, indent=2)}

### 角色成长弧线
{json.dumps(part_outline.character_arcs or {}, ensure_ascii=False, indent=2)}

### 结尾钩子
{part_outline.ending_hook or "（无）"}

"""

        if prev_part:
            prompt += f"""
## 上一部分的结尾
{prev_part}
"""

        if next_part:
            prompt += f"""
## 下一部分的开始
{next_part}
"""

        prompt += f"""
## 世界观设定
{json.dumps(world_setting, ensure_ascii=False, indent=2)}

## 角色档案
{json.dumps(characters, ensure_ascii=False, indent=2)}

## 输出要求

请为第 {part_outline.start_chapter} 章到第 {part_outline.end_chapter} 章生成详细的章节大纲。

每个章节应包含：
- chapter_number: 章节编号
- title: 章节标题
- summary: 章节摘要（100-200字）

确保：
1. 严格按照章节编号顺序生成（{part_outline.start_chapter} 到 {part_outline.end_chapter}）
2. 章节之间有自然的承接关系
3. 关键事件和冲突合理分布在各个章节
4. 角色成长轨迹清晰可见
5. 整体节奏符合起承转合结构

输出JSON格式：
{{
  "chapter_outline": [
    {{
      "chapter_number": {part_outline.start_chapter},
      "title": "...",
      "summary": "..."
    }},
    ...
  ]
}}
"""
        return prompt

    def _to_schema(self, part: PartOutline) -> PartOutlineSchema:
        """将数据库模型转换为Pydantic Schema"""
        return PartOutlineSchema(
            part_number=part.part_number,
            title=part.title or "",
            start_chapter=part.start_chapter,
            end_chapter=part.end_chapter,
            summary=part.summary or "",
            theme=part.theme or "",
            key_events=part.key_events or [],
            character_arcs=part.character_arcs or {},
            conflicts=part.conflicts or [],
            ending_hook=part.ending_hook,
            generation_status=part.generation_status,
            progress=part.progress,
        )
