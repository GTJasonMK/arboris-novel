/**
 * 项目状态管理 Composable
 *
 * 统一管理项目状态判断逻辑，确保前端组件使用一致的状态判断方式
 */

import { computed, type Ref } from 'vue'
import type { NovelProject } from '@/api/novel'
import {
  ProjectStatus,
  PROJECT_STATUS_LABELS,
  PROJECT_STATUS_CLASSES,
  ProjectStatusHelpers
} from '@/types/enums'

/**
 * 使用项目状态管理
 *
 * @param project 项目对象或Ref
 * @returns 状态判断和显示相关的computed属性
 */
export function useProjectStatus(project: Ref<NovelProject | undefined> | NovelProject | undefined) {
  // 处理Ref和普通对象两种情况
  const projectRef = computed(() => {
    if (!project) return undefined
    // 如果是Ref，返回其value
    if ('value' in project) return project.value
    // 否则直接返回
    return project
  })

  // 原始状态
  const status = computed(() => projectRef.value?.status || ProjectStatus.DRAFT)

  // 基础状态判断
  const isDraft = computed(() => status.value === ProjectStatus.DRAFT)
  const isBlueprintReady = computed(() => status.value === ProjectStatus.BLUEPRINT_READY)
  const isPartOutlinesReady = computed(() => status.value === ProjectStatus.PART_OUTLINES_READY)
  const isChapterOutlinesReady = computed(() => status.value === ProjectStatus.CHAPTER_OUTLINES_READY)
  const isWriting = computed(() => status.value === ProjectStatus.WRITING)
  const isCompleted = computed(() => status.value === ProjectStatus.COMPLETED)

  // 阶段判断（基于status + blueprint）
  const needsBlueprint = computed(() => isDraft.value)

  const needsPartOutlines = computed(() => {
    return isBlueprintReady.value && (projectRef.value?.blueprint?.needs_part_outlines || false)
  })

  const needsChapterOutlines = computed(() => {
    const hasBlueprint = isBlueprintReady.value || isPartOutlinesReady.value
    const hasNoOutlines = !projectRef.value?.blueprint?.chapter_outline ||
                          projectRef.value.blueprint.chapter_outline.length === 0
    return hasBlueprint && hasNoOutlines
  })

  const canStartWriting = computed(() => {
    return ProjectStatusHelpers.canStartWriting(status.value)
  })

  // 显示相关
  const statusLabel = computed(() => PROJECT_STATUS_LABELS[status.value as ProjectStatus] || '未知状态')

  const statusClass = computed(() => PROJECT_STATUS_CLASSES[status.value as ProjectStatus] || 'bg-gray-400')

  // 辅助方法（直接使用ProjectStatusHelpers）
  const canGenerateBlueprint = computed(() => ProjectStatusHelpers.canGenerateBlueprint(status.value))
  const canGeneratePartOutlines = computed(() => ProjectStatusHelpers.canGeneratePartOutlines(status.value))
  const canGenerateChapterOutlines = computed(() => ProjectStatusHelpers.canGenerateChapterOutlines(status.value))

  return {
    // 原始状态
    status,

    // 状态判断
    isDraft,
    isBlueprintReady,
    isPartOutlinesReady,
    isChapterOutlinesReady,
    isWriting,
    isCompleted,

    // 阶段判断
    needsBlueprint,
    needsPartOutlines,
    needsChapterOutlines,
    canStartWriting,

    // 能力判断
    canGenerateBlueprint,
    canGeneratePartOutlines,
    canGenerateChapterOutlines,

    // 显示相关
    statusLabel,
    statusClass
  }
}
