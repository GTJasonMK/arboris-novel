# 生成操作状态持久化集成指南

本文档说明如何在各个组件中集成统一的生成状态管理工具，确保用户刷新页面后仍能看到"正在生成"状态。

## 已完成

- ✅ `PartOutlineGenerator.vue` - 生成部分大纲

## 待集成组件

### 1. BlueprintConfirmation.vue - 生成蓝图

**文件路径**: `frontend/src/components/BlueprintConfirmation.vue`

**集成步骤**:

1. 导入工具函数:
```typescript
import {
  GenerationType,
  markGenerationStart,
  markGenerationComplete,
  isGenerating as checkIsGenerating
} from '@/utils/generationState'
```

2. 在 `onMounted` 中检查状态:
```typescript
onMounted(() => {
  const { generating, elapsed } = checkIsGenerating(
    GenerationType.BLUEPRINT,
    novelStore.currentProject?.id || ''
  )

  if (generating) {
    isGenerating.value = true
    console.log(`恢复蓝图生成状态（已等待 ${elapsed}ms）`)
  }
})
```

3. 在生成函数中标记开始/完成:
```typescript
const generateBlueprint = async () => {
  isGenerating.value = true
  markGenerationStart(GenerationType.BLUEPRINT, novelStore.currentProject?.id || '')

  try {
    // ... 调用API生成蓝图
    markGenerationComplete(GenerationType.BLUEPRINT, novelStore.currentProject?.id || '')
    isGenerating.value = false
  } catch (err) {
    markGenerationComplete(GenerationType.BLUEPRINT, novelStore.currentProject?.id || '')
    isGenerating.value = false
  }
}
```

### 2. InspirationMode.vue - 优化蓝图

**文件路径**: `frontend/src/views/InspirationMode.vue`

**集成步骤**: 类似BlueprintConfirmation.vue，使用 `GenerationType.REFINE_BLUEPRINT`

### 3. ChapterOutlineGenerator.vue - 生成章节大纲

**文件路径**: `frontend/src/components/novel-detail/ChapterOutlineGenerator.vue`

**集成步骤**: 使用 `GenerationType.CHAPTER_OUTLINE`

### 4. WDWorkspace.vue - 生成章节

**文件路径**: `frontend/src/components/writing-desk/WDWorkspace.vue`

**集成步骤**: 使用 `GenerationType.CHAPTER`

**特殊处理**: 章节生成可能需要存储额外的metadata（如章节号）:

```typescript
markGenerationStart(
  GenerationType.CHAPTER,
  projectId,
  { chapterNumber: currentChapter }
)
```

恢复时可以从metadata中获取:

```typescript
const { generating, state } = checkIsGenerating(GenerationType.CHAPTER, projectId)
if (generating && state?.metadata?.chapterNumber) {
  // 恢复到正在生成的章节
  currentChapter.value = state.metadata.chapterNumber
}
```

## 工具函数说明

### markGenerationStart(type, projectId, metadata?)

标记生成操作开始，存储到localStorage。

- `type`: 生成类型枚举
- `projectId`: 项目ID
- `metadata`: 可选的额外数据（如章节号）

### markGenerationComplete(type, projectId)

标记生成操作完成，从localStorage移除。

### isGenerating(type, projectId, customTimeout?)

检查是否正在生成（考虑超时）。

返回值:
```typescript
{
  generating: boolean,  // 是否正在生成
  elapsed: number,      // 已经过的毫秒数
  state?: GenerationState  // 完整的状态对象（包含metadata）
}
```

### clearExpiredGenerationStates()

清除所有过期的生成状态（可在应用启动时调用）。

## 默认超时时间

```typescript
BLUEPRINT: 10分钟
PART_OUTLINE: 5分钟
CHAPTER_OUTLINE: 5分钟
CHAPTER: 10分钟
REFINE_BLUEPRINT: 10分钟
```

## 最佳实践

1. **总是在组件卸载前清理**: 虽然有超时机制，但最好在操作成功/失败时立即清除状态
2. **watch props变化**: 当数据从后端加载完成时，立即清除生成状态
3. **添加日志**: 使用console.log记录状态变化，方便调试
4. **错误处理**: catch块中也要清除生成状态

## 应用启动时清理

在 `main.ts` 或 `App.vue` 中调用一次清理函数:

```typescript
import { clearExpiredGenerationStates } from '@/utils/generationState'

// 应用启动时清理过期状态
clearExpiredGenerationStates()
```

## 测试步骤

1. 点击生成按钮
2. 立即刷新页面
3. 验证仍显示"正在生成"状态
4. 等待生成完成，验证状态自动清除
5. 手动清除localStorage，刷新页面，验证不再显示生成状态
