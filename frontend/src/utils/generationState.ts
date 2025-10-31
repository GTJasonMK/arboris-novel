/**
 * 生成操作状态持久化工具
 * 用于在页面刷新后仍能显示"正在生成"状态
 */

export enum GenerationType {
  BLUEPRINT = 'blueprint',
  PART_OUTLINE = 'part_outline',
  CHAPTER_OUTLINE = 'chapter_outline',
  CHAPTER = 'chapter',
  REFINE_BLUEPRINT = 'refine_blueprint'
}

interface GenerationState {
  type: GenerationType
  projectId: string
  timestamp: number
  metadata?: Record<string, any>
}

// 默认超时时间（毫秒）
const DEFAULT_TIMEOUTS: Record<GenerationType, number> = {
  [GenerationType.BLUEPRINT]: 10 * 60 * 1000, // 10分钟
  [GenerationType.PART_OUTLINE]: 5 * 60 * 1000, // 5分钟
  [GenerationType.CHAPTER_OUTLINE]: 5 * 60 * 1000, // 5分钟
  [GenerationType.CHAPTER]: 10 * 60 * 1000, // 10分钟
  [GenerationType.REFINE_BLUEPRINT]: 10 * 60 * 1000 // 10分钟
}

/**
 * 生成localStorage key
 */
function getStorageKey(type: GenerationType, projectId: string): string {
  return `generation_${type}_${projectId}`
}

/**
 * 标记生成操作开始
 */
export function markGenerationStart(
  type: GenerationType,
  projectId: string,
  metadata?: Record<string, any>
): void {
  const state: GenerationState = {
    type,
    projectId,
    timestamp: Date.now(),
    metadata
  }
  const key = getStorageKey(type, projectId)
  localStorage.setItem(key, JSON.stringify(state))
  console.log(`[GenerationState] 标记生成开始: ${type}, projectId: ${projectId}`)
}

/**
 * 标记生成操作完成
 */
export function markGenerationComplete(type: GenerationType, projectId: string): void {
  const key = getStorageKey(type, projectId)
  localStorage.removeItem(key)
  console.log(`[GenerationState] 标记生成完成: ${type}, projectId: ${projectId}`)
}

/**
 * 检查是否正在生成（考虑超时）
 */
export function isGenerating(
  type: GenerationType,
  projectId: string,
  customTimeout?: number
): { generating: boolean; elapsed: number; state?: GenerationState } {
  const key = getStorageKey(type, projectId)
  const storageValue = localStorage.getItem(key)

  if (!storageValue) {
    return { generating: false, elapsed: 0 }
  }

  try {
    const state: GenerationState = JSON.parse(storageValue)
    const elapsed = Date.now() - state.timestamp
    const timeout = customTimeout || DEFAULT_TIMEOUTS[type]

    // 检查是否超时
    if (elapsed > timeout) {
      console.log(
        `[GenerationState] 检测到超时的生成标记: ${type}, projectId: ${projectId}, elapsed: ${elapsed}ms`
      )
      localStorage.removeItem(key)
      return { generating: false, elapsed, state }
    }

    console.log(
      `[GenerationState] 恢复生成状态: ${type}, projectId: ${projectId}, elapsed: ${elapsed}ms`
    )
    return { generating: true, elapsed, state }
  } catch (e) {
    console.error(`[GenerationState] 解析生成状态失败:`, e)
    localStorage.removeItem(key)
    return { generating: false, elapsed: 0 }
  }
}

/**
 * 清除所有过期的生成状态
 */
export function clearExpiredGenerationStates(): void {
  const keys = Object.keys(localStorage)
  const generationKeys = keys.filter((key) => key.startsWith('generation_'))

  let cleared = 0
  generationKeys.forEach((key) => {
    const storageValue = localStorage.getItem(key)
    if (!storageValue) return

    try {
      const state: GenerationState = JSON.parse(storageValue)
      const elapsed = Date.now() - state.timestamp
      const timeout = DEFAULT_TIMEOUTS[state.type]

      if (elapsed > timeout) {
        localStorage.removeItem(key)
        cleared++
      }
    } catch (e) {
      localStorage.removeItem(key)
      cleared++
    }
  })

  if (cleared > 0) {
    console.log(`[GenerationState] 清除了 ${cleared} 个过期的生成状态`)
  }
}

/**
 * 获取项目的所有生成状态
 */
export function getProjectGenerationStates(projectId: string): Record<GenerationType, boolean> {
  const states: Record<GenerationType, boolean> = {
    [GenerationType.BLUEPRINT]: false,
    [GenerationType.PART_OUTLINE]: false,
    [GenerationType.CHAPTER_OUTLINE]: false,
    [GenerationType.CHAPTER]: false,
    [GenerationType.REFINE_BLUEPRINT]: false
  }

  Object.values(GenerationType).forEach((type) => {
    const { generating } = isGenerating(type, projectId)
    states[type] = generating
  })

  return states
}
