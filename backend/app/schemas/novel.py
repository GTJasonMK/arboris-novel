from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ChoiceOption(BaseModel):
    """前端选择项描述，用于动态 UI 控件。"""

    id: str
    label: str


class UIControl(BaseModel):
    """描述前端应渲染的组件类型与配置。"""

    type: str = Field(..., description="控件类型，如 single_choice/text_input")
    options: Optional[List[ChoiceOption]] = Field(default=None, description="可选项列表")
    placeholder: Optional[str] = Field(default=None, description="输入提示文案")


class ConverseResponse(BaseModel):
    """概念对话接口的统一返回体。"""

    ai_message: str
    ui_control: UIControl
    conversation_state: Dict[str, Any]
    is_complete: bool = False
    ready_for_blueprint: Optional[bool] = None


class ConverseRequest(BaseModel):
    """概念对话接口的请求体。"""

    user_input: Dict[str, Any]
    conversation_state: Dict[str, Any]


class ChapterGenerationStatus(str, Enum):
    NOT_GENERATED = "not_generated"
    GENERATING = "generating"
    EVALUATING = "evaluating"
    SELECTING = "selecting"
    FAILED = "failed"
    EVALUATION_FAILED = "evaluation_failed"
    WAITING_FOR_CONFIRM = "waiting_for_confirm"
    SUCCESSFUL = "successful"


class ChapterOutline(BaseModel):
    chapter_number: int
    title: str
    summary: str


class PartOutlineStatus(str, Enum):
    """部分大纲生成状态"""
    PENDING = "pending"
    GENERATING = "generating"
    COMPLETED = "completed"
    FAILED = "failed"


class PartOutline(BaseModel):
    """部分大纲（用于长篇小说的分层结构）"""
    part_number: int
    title: str
    start_chapter: int
    end_chapter: int
    summary: str
    theme: str
    key_events: List[str] = []
    character_arcs: Dict[str, str] = {}  # 角色名 -> 成长描述
    conflicts: List[str] = []
    ending_hook: Optional[str] = None  # 与下一部分的衔接点
    generation_status: PartOutlineStatus = PartOutlineStatus.PENDING
    progress: int = 0  # 生成进度 0-100


class Chapter(ChapterOutline):
    real_summary: Optional[str] = None
    content: Optional[str] = None
    versions: Optional[List[str]] = None
    evaluation: Optional[str] = None
    generation_status: ChapterGenerationStatus = ChapterGenerationStatus.NOT_GENERATED


class Relationship(BaseModel):
    character_from: str
    character_to: str
    description: str


class Blueprint(BaseModel):
    title: str
    target_audience: str = ""
    genre: str = ""
    style: str = ""
    tone: str = ""
    one_sentence_summary: str = ""
    full_synopsis: str = ""
    world_setting: Dict[str, Any] = {}
    characters: List[Dict[str, Any]] = []
    relationships: List[Relationship] = []
    chapter_outline: List[ChapterOutline] = []
    needs_part_outlines: bool = False  # 是否需要分阶段生成（>50章）
    total_chapters: Optional[int] = None  # 总章节数
    chapters_per_part: Optional[int] = 25  # 每部分章节数（默认25）
    part_outlines: List[PartOutline] = []  # 部分大纲列表


class NovelProject(BaseModel):
    id: str
    user_id: int
    title: str
    initial_prompt: str
    status: str  # 项目状态：draft, blueprint_ready, part_outlines_ready, chapter_outlines_ready 等
    conversation_history: List[Dict[str, Any]] = []
    blueprint: Optional[Blueprint] = None
    chapters: List[Chapter] = []

    class Config:
        from_attributes = True


class NovelProjectSummary(BaseModel):
    id: str
    title: str
    genre: str
    last_edited: str
    completed_chapters: int
    total_chapters: int
    status: str  # 项目状态：draft, blueprint_ready, part_outlines_ready, chapter_outlines_ready 等


class BlueprintGenerationResponse(BaseModel):
    blueprint: Blueprint
    ai_message: str


class BlueprintRefineRequest(BaseModel):
    """蓝图优化请求体"""
    refinement_instruction: str = Field(
        ...,
        description="用户的优化指令，描述想要改进的方向",
        min_length=1,
        max_length=2000
    )


class ChapterGenerationResponse(BaseModel):
    ai_message: str
    chapter_versions: List[Dict[str, Any]]


class NovelSectionType(str, Enum):
    OVERVIEW = "overview"
    WORLD_SETTING = "world_setting"
    CHARACTERS = "characters"
    RELATIONSHIPS = "relationships"
    CHAPTER_OUTLINE = "chapter_outline"
    CHAPTERS = "chapters"


class NovelSectionResponse(BaseModel):
    section: NovelSectionType
    data: Dict[str, Any]


class GenerateChapterRequest(BaseModel):
    chapter_number: int
    writing_notes: Optional[str] = Field(default=None, description="章节额外写作指令")


class SelectVersionRequest(BaseModel):
    chapter_number: int
    version_index: int


class EvaluateChapterRequest(BaseModel):
    chapter_number: int


class UpdateChapterOutlineRequest(BaseModel):
    chapter_number: int
    title: str
    summary: str


class DeleteChapterRequest(BaseModel):
    chapter_numbers: List[int]


class GenerateOutlineRequest(BaseModel):
    start_chapter: int
    num_chapters: int


class BlueprintPatch(BaseModel):
    one_sentence_summary: Optional[str] = None
    full_synopsis: Optional[str] = None
    world_setting: Optional[Dict[str, Any]] = None
    characters: Optional[List[Dict[str, Any]]] = None
    relationships: Optional[List[Relationship]] = None
    chapter_outline: Optional[List[ChapterOutline]] = None


class EditChapterRequest(BaseModel):
    chapter_number: int
    content: str


# 部分大纲相关请求和响应模型
class GeneratePartOutlinesRequest(BaseModel):
    """生成部分大纲请求"""
    total_chapters: int = Field(
        ...,
        description="小说总章节数",
        ge=10,
        le=10000
    )
    chapters_per_part: int = Field(
        default=25,
        description="每个部分的章节数",
        ge=10,
        le=100
    )


class GeneratePartChaptersRequest(BaseModel):
    """基于部分大纲生成章节请求"""
    regenerate: bool = Field(
        default=False,
        description="是否重新生成（如果章节已存在则覆盖）"
    )


class BatchGenerateChaptersRequest(BaseModel):
    """批量并发生成章节请求"""
    part_numbers: Optional[List[int]] = Field(
        default=None,
        description="要并发生成的部分编号列表，为空则生成所有"
    )
    max_concurrent: int = Field(
        default=5,
        description="最大并发数",
        ge=1,
        le=10
    )


class PartOutlineGenerationProgress(BaseModel):
    """部分大纲批量生成进度（整体进度）"""
    parts: List[PartOutline] = []  # 所有部分的大纲列表
    total_parts: int = 0  # 总部分数
    completed_parts: int = 0  # 已完成部分数
    status: str = "pending"  # 整体状态：pending, partial, completed
