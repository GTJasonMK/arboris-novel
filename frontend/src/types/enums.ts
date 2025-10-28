/**
 * 项目状态枚举
 *
 * 与后端 backend/app/core/constants.py 中的 ProjectStatus 保持一致
 */
export enum ProjectStatus {
  /** 灵感收集中（对话阶段） */
  DRAFT = 'draft',
  /** 蓝图完成 */
  BLUEPRINT_READY = 'blueprint_ready',
  /** 部分大纲完成（仅长篇小说） */
  PART_OUTLINES_READY = 'part_outlines_ready',
  /** 章节大纲完成，可开始写作 */
  CHAPTER_OUTLINES_READY = 'chapter_outlines_ready',
  /** 写作进行中 */
  WRITING = 'writing',
  /** 已完成 */
  COMPLETED = 'completed'
}

/**
 * 项目状态显示名称映射
 */
export const PROJECT_STATUS_LABELS: Record<ProjectStatus, string> = {
  [ProjectStatus.DRAFT]: '灵感收集中',
  [ProjectStatus.BLUEPRINT_READY]: '蓝图完成',
  [ProjectStatus.PART_OUTLINES_READY]: '部分大纲完成',
  [ProjectStatus.CHAPTER_OUTLINES_READY]: '章节大纲完成',
  [ProjectStatus.WRITING]: '写作中',
  [ProjectStatus.COMPLETED]: '已完成'
}

/**
 * 项目状态徽章样式映射（TailwindCSS类名）
 */
export const PROJECT_STATUS_CLASSES: Record<ProjectStatus, string> = {
  [ProjectStatus.DRAFT]: 'bg-gray-500',
  [ProjectStatus.BLUEPRINT_READY]: 'bg-blue-500',
  [ProjectStatus.PART_OUTLINES_READY]: 'bg-indigo-500',
  [ProjectStatus.CHAPTER_OUTLINES_READY]: 'bg-purple-500',
  [ProjectStatus.WRITING]: 'bg-green-500',
  [ProjectStatus.COMPLETED]: 'bg-emerald-600'
}

/**
 * 状态判断辅助函数
 */
export const ProjectStatusHelpers = {
  /** 判断是否可以生成蓝图 */
  canGenerateBlueprint(status: string): boolean {
    return status === ProjectStatus.DRAFT
  },

  /** 判断是否可以生成部分大纲 */
  canGeneratePartOutlines(status: string): boolean {
    return status === ProjectStatus.BLUEPRINT_READY
  },

  /** 判断是否可以生成章节大纲 */
  canGenerateChapterOutlines(status: string): boolean {
    return status === ProjectStatus.BLUEPRINT_READY || status === ProjectStatus.PART_OUTLINES_READY
  },

  /** 判断是否可以开始写作 */
  canStartWriting(status: string): boolean {
    return status === ProjectStatus.CHAPTER_OUTLINES_READY || status === ProjectStatus.WRITING
  },

  /** 判断项目是否已完成 */
  isCompleted(status: string): boolean {
    return status === ProjectStatus.COMPLETED
  },

  /** 判断项目是否在写作阶段 */
  isWriting(status: string): boolean {
    return status === ProjectStatus.WRITING
  }
}
