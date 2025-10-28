"""
核心常量定义模块

定义项目中使用的枚举类型和常量值，确保类型安全和代码一致性。
"""

from enum import Enum


class ProjectStatus(str, Enum):
    """
    小说项目状态枚举

    状态流转路径：
    1. 短篇流程（≤50章）：
       draft → blueprint_ready → chapter_outlines_ready → writing → completed

    2. 长篇流程（>50章）：
       draft → blueprint_ready → part_outlines_ready → chapter_outlines_ready → writing → completed

    状态说明：
    - DRAFT: 灵感对话阶段，收集创作要素
    - BLUEPRINT_READY: 蓝图生成完成，包含基础设定
    - PART_OUTLINES_READY: 部分大纲生成完成（仅长篇）
    - CHAPTER_OUTLINES_READY: 章节大纲生成完成，可开始写作
    - WRITING: 写作进行中，至少有一章已生成
    - COMPLETED: 所有章节完成，项目结束
    """

    DRAFT = "draft"
    BLUEPRINT_READY = "blueprint_ready"
    PART_OUTLINES_READY = "part_outlines_ready"
    CHAPTER_OUTLINES_READY = "chapter_outlines_ready"
    WRITING = "writing"
    COMPLETED = "completed"

    def __str__(self) -> str:
        """返回枚举值的字符串形式，方便与数据库字段比较"""
        return self.value

    @classmethod
    def get_display_name(cls, status: str) -> str:
        """获取状态的中文显示名称"""
        display_names = {
            cls.DRAFT: "灵感收集中",
            cls.BLUEPRINT_READY: "蓝图完成",
            cls.PART_OUTLINES_READY: "部分大纲完成",
            cls.CHAPTER_OUTLINES_READY: "章节大纲完成",
            cls.WRITING: "写作中",
            cls.COMPLETED: "已完成",
        }
        return display_names.get(status, "未知状态")

    @classmethod
    def can_generate_blueprint(cls, status: str) -> bool:
        """判断是否可以生成蓝图"""
        return status == cls.DRAFT

    @classmethod
    def can_generate_part_outlines(cls, status: str) -> bool:
        """判断是否可以生成部分大纲"""
        return status == cls.BLUEPRINT_READY

    @classmethod
    def can_generate_chapter_outlines(cls, status: str) -> bool:
        """判断是否可以生成章节大纲"""
        return status in [cls.BLUEPRINT_READY, cls.PART_OUTLINES_READY]

    @classmethod
    def can_start_writing(cls, status: str) -> bool:
        """判断是否可以开始写作"""
        return status in [cls.CHAPTER_OUTLINES_READY, cls.WRITING]
