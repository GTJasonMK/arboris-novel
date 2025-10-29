# 历史遗留问题修复文档

## 执行摘要

本文档记录了在系统性检查Arboris-Novel项目时发现的历史遗留问题，并提供完整的修复方案。

**检查时间**: 2025-10-27
**检查范围**: 提示词、API路由、前端组件、数据库Schema、状态管理
**发现问题数**: 5个
**严重程度**: 🟡 中等（影响工作流一致性，但不影响核心功能）

---

## 问题清单

| 问题 | 严重程度 | 影响范围 | 状态 |
|------|---------|---------|------|
| 1. 提示词矛盾指令 | 🔴 高 | 蓝图生成 | ✅ 已修复 |
| 2. Schema注释不一致 | 🟡 中 | 文档准确性 | ⏳ 待修复 |
| 3. 状态迁移不完整 | 🟡 中 | 工作流追踪 | ⏳ 待优化 |
| 4. 前端状态判断不统一 | 🟡 中 | 代码可维护性 | ⏳ 待重构 |
| 5. 缺少状态枚举定义 | 🟢 低 | 类型安全 | ⏳ 待补充 |

---

## 问题 1: 提示词矛盾指令 🔴 已修复

### 问题描述

**文件**: `backend/prompts/screenwriting.md`

**发现的矛盾**:
- **第41行（旧指令）**: "chapter_outline 需要有每一章节。"
- **第133行（新指令）**: "**绝对要求**：`\"chapter_outline\": []`"

这两条指令直接冲突，导致LLM可能违反工作流分离原则，在蓝图生成阶段生成章节大纲。

### 根本原因

**历史演变**:
```
旧版设计（已废弃）:
  蓝图生成 = 基础设定 + 章节大纲（一起生成）

新版设计（工作流分离）:
  蓝图生成 = 基础设定（chapter_outline: []）
  章节大纲生成 = 单独步骤
```

**问题**: 在实施新设计时，添加了新指令，但忘记删除第41行的旧指令。

### 修复方案

**文件**: `backend/prompts/screenwriting.md` 第39-41行

**修改前**:
```markdown
1. 生成严格符合蓝图结构的完整 JSON 对象，但内容要充满人性温度和创作灵感，绝不能有程式化的 AI 痕迹。
2. JSON 对象严格遵循下方提供的蓝图模型的结构。
   请勿添加任何对话文本或解释。您的输出必须仅为 JSON 对象。chapter_outline 需要有每一章节。
```

**修改后**:
```markdown
1. 生成严格符合蓝图结构的完整 JSON 对象，但内容要充满人性温度和创作灵感，绝不能有程式化的 AI 痕迹。
2. JSON 对象严格遵循下方提供的蓝图模型的结构。
   请勿添加任何对话文本或解释。您的输出必须仅为 JSON 对象。
```

**修复状态**: ✅ 已完成

---

## 问题 2: Schema注释不一致 🟡 待修复

### 问题描述

**文件**: `backend/app/schemas/novel.py`

**不一致之处**:
- **第117行（NovelProject注释）**: "draft, blueprint_ready, part_outlines_ready, chapter_outlines_ready 等" ✅ 正确
- **第133行（NovelProjectSummary注释）**: "draft, blueprint_ready, need_part_outlines 等" ❌ 错误

**问题**: `need_part_outlines` 不是状态值，它是Blueprint中的布尔字段 `needs_part_outlines`。正确的状态值应该是 `part_outlines_ready`。

### 影响

- 🟡 **中等影响**: 误导开发者，认为存在 `need_part_outlines` 状态
- 📚 **文档准确性**: 注释是代码文档的一部分，错误注释会导致理解偏差
- 🔍 **代码审查**: 新开发者可能根据错误注释写出不一致的代码

### 修复方案

**文件**: `backend/app/schemas/novel.py` 第133行

**修改前**:
```python
status: str  # 项目状态：draft, blueprint_ready, need_part_outlines 等
```

**修改后**:
```python
status: str  # 项目状态：draft, blueprint_ready, part_outlines_ready, chapter_outlines_ready 等
```

**同步修复前端**:

**文件**: `frontend/src/api/novel.ts` 第56行

**修改前**:
```typescript
status: string  // 项目状态：draft, blueprint_ready, need_part_outlines 等
```

**修改后**:
```typescript
status: string  // 项目状态：draft, blueprint_ready, part_outlines_ready, chapter_outlines_ready 等
```

---

## 问题 3: 状态迁移不完整 🟡 待优化

### 问题描述

**当前状态迁移流程**:

```
创建项目 → draft（默认值，models/novel.py:38）
   ↓
生成蓝图 → blueprint_ready（novels.py:286）✅
   ↓
生成部分大纲 → part_outlines_ready（part_outline_service.py:199）✅
   ↓
生成章节大纲 → chapter_outlines_ready（novels.py:434）✅
   ↓
生成章节内容 → ❌ 没有状态更新（缺少"writing"状态）
   ↓
完成所有章节 → ❌ 没有状态更新（缺少"completed"状态）
```

### 缺失的状态

1. **`writing`**: 表示项目正在进行章节生成
   - 应该在第一次生成章节时设置
   - 可用于区分"准备写作"和"写作中"

2. **`completed`**: 表示所有章节已完成
   - 应该在所有章节都选择了版本后设置
   - 可用于项目列表的筛选（显示已完成项目）

### 影响

- 🟡 **中等影响**:
  - 无法通过status判断项目是否在写作阶段
  - 无法通过status判断项目是否完成
  - 项目列表无法准确显示项目进度状态

- 📊 **统计功能受限**:
  - 无法统计"正在写作"的项目数
  - 无法区分"已完成"和"写作中"的项目

### 修复方案（可选优化）

#### 方案A: 添加完整的状态迁移（推荐）

**状态定义**:
```python
# backend/app/core/constants.py（新建）

class ProjectStatus:
    """项目状态常量"""
    DRAFT = "draft"  # 灵感对话中
    BLUEPRINT_READY = "blueprint_ready"  # 蓝图完成
    PART_OUTLINES_READY = "part_outlines_ready"  # 部分大纲完成（长篇）
    CHAPTER_OUTLINES_READY = "chapter_outlines_ready"  # 章节大纲完成
    WRITING = "writing"  # 写作中
    COMPLETED = "completed"  # 已完成
```

**修改1**: `backend/app/api/routers/writer.py` - 生成章节时更新状态

```python
@router.post("/novels/{project_id}/chapters/generate", response_model=NovelProjectSchema)
async def generate_chapter(
    project_id: str,
    request: GenerateChapterRequest,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> NovelProjectSchema:
    # ... 现有逻辑

    # 新增：如果项目还未进入写作状态，更新为writing
    if project.status == "chapter_outlines_ready":
        project.status = "writing"
        await session.commit()
        logger.info("项目 %s 状态更新为 writing", project_id)

    # ... 继续生成章节
```

**修改2**: `backend/app/services/novel_service.py` - 添加完成度检查方法

```python
async def check_and_update_completion_status(self, project_id: str, user_id: int) -> None:
    """检查项目是否完成，如果所有章节都已选择版本，更新状态为completed"""
    project_schema = await self.get_project_schema(project_id, user_id)
    project = await self.repo.get_project(project_id)

    if not project_schema.blueprint or not project_schema.blueprint.total_chapters:
        return

    total_chapters = project_schema.blueprint.total_chapters
    completed_chapters = sum(1 for ch in project_schema.chapters if ch.selected_version)

    if completed_chapters == total_chapters and project.status == "writing":
        project.status = "completed"
        await self.session.commit()
        logger.info("项目 %s 所有章节完成，状态更新为 completed", project_id)
```

**修改3**: `backend/app/api/routers/writer.py` - 选择版本后检查完成度

```python
@router.post("/novels/{project_id}/chapters/select", response_model=NovelProjectSchema)
async def select_chapter_version(
    project_id: str,
    request: SelectVersionRequest,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> NovelProjectSchema:
    # ... 现有逻辑

    # 新增：选择版本后检查是否所有章节都完成了
    await novel_service.check_and_update_completion_status(project_id, current_user.id)

    # ... 返回
```

#### 方案B: 保持现状（不推荐）

**理由**:
- 当前系统主要通过blueprint字段判断阶段，而非status
- 添加新状态需要全面测试
- 对现有功能影响较小

**权衡**: 如果选择方案B，建议至少添加状态常量定义，为未来扩展预留接口。

---

## 问题 4: 前端状态判断不统一 🟡 待重构

### 问题描述

**前端状态判断混乱**:

1. **NovelWorkspace.vue（第175行）**:
   ```typescript
   if (project.status === 'draft') {
     router.push(`/inspiration?project_id=${project.id}`)
   } else {
     router.push(`/novel/${project.id}`)
   }
   ```
   ✅ 使用 `project.status` 判断

2. **ChapterOutlineSection.vue（第107行）**:
   ```typescript
   const needsPartOutlines = computed(() => props.blueprint?.needs_part_outlines || false)
   ```
   ❌ 使用 `blueprint.needs_part_outlines` 判断（不是status）

3. **NovelDetail.vue**:
   ❌ 完全没有状态检查，依赖组件自行判断

### 影响

- 🟡 **代码可维护性差**:
  - 判断逻辑分散在各个组件
  - 新开发者难以理解状态流转
  - 修改工作流时需要多处修改

- 🐛 **潜在bug风险**:
  - 如果status和blueprint字段不一致，可能导致UI显示错误
  - 难以统一管理状态相关的UI逻辑

### 修复方案（可选重构）

#### 方案A: 统一使用Composable管理状态判断（推荐）

**新建文件**: `frontend/src/composables/useProjectStatus.ts`

```typescript
import { computed } from 'vue'
import type { NovelProject } from '@/api/novel'

export function useProjectStatus(project: NovelProject | undefined) {
  const status = computed(() => project?.status || 'draft')

  // 状态判断
  const isDraft = computed(() => status.value === 'draft')
  const isBlueprintReady = computed(() => status.value === 'blueprint_ready')
  const isPartOutlinesReady = computed(() => status.value === 'part_outlines_ready')
  const isChapterOutlinesReady = computed(() => status.value === 'chapter_outlines_ready')
  const isWriting = computed(() => status.value === 'writing')
  const isCompleted = computed(() => status.value === 'completed')

  // 阶段判断（基于status + blueprint）
  const needsBlueprint = computed(() => isDraft.value)
  const needsPartOutlines = computed(() =>
    isBlueprintReady.value && project?.blueprint?.needs_part_outlines
  )
  const needsChapterOutlines = computed(() =>
    (isBlueprintReady.value || isPartOutlinesReady.value) &&
    (!project?.blueprint?.chapter_outline || project.blueprint.chapter_outline.length === 0)
  )
  const canStartWriting = computed(() =>
    isChapterOutlinesReady.value || isWriting.value || isCompleted.value
  )

  // 状态显示文本
  const statusLabel = computed(() => {
    const labels: Record<string, string> = {
      'draft': '灵感收集中',
      'blueprint_ready': '蓝图完成',
      'part_outlines_ready': '部分大纲完成',
      'chapter_outlines_ready': '章节大纲完成',
      'writing': '写作中',
      'completed': '已完成'
    }
    return labels[status.value] || '未知状态'
  })

  // 状态徽章样式
  const statusClass = computed(() => {
    const classes: Record<string, string> = {
      'draft': 'bg-gray-500',
      'blueprint_ready': 'bg-blue-500',
      'part_outlines_ready': 'bg-indigo-500',
      'chapter_outlines_ready': 'bg-purple-500',
      'writing': 'bg-green-500',
      'completed': 'bg-emerald-600'
    }
    return classes[status.value] || 'bg-gray-400'
  })

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

    // 显示相关
    statusLabel,
    statusClass
  }
}
```

**使用示例**:

```vue
<!-- ChapterOutlineSection.vue -->
<script setup lang="ts">
import { useProjectStatus } from '@/composables/useProjectStatus'

const { needsPartOutlines, needsChapterOutlines, canStartWriting } = useProjectStatus(props.project)
</script>

<template>
  <div v-if="needsPartOutlines">
    <!-- 显示生成部分大纲的按钮 -->
  </div>
  <div v-else-if="needsChapterOutlines">
    <!-- 显示生成章节大纲的按钮 -->
  </div>
  <div v-else-if="canStartWriting">
    <!-- 显示写作相关UI -->
  </div>
</template>
```

**优点**:
- ✅ 状态判断逻辑集中在一处
- ✅ 易于维护和测试
- ✅ 类型安全（TypeScript）
- ✅ 可复用

#### 方案B: 保持现状（不推荐）

**理由**: 当前系统依赖blueprint字段的方式虽然不规范，但功能正常。

**风险**: 未来扩展时容易出错。

---

## 问题 5: 缺少状态枚举定义 🟢 待补充

### 问题描述

**当前状态**: 状态值以字符串字面量散落在各处代码中

**位置**:
- `backend/app/models/novel.py:38`: `default="draft"`
- `backend/app/api/routers/novels.py:286`: `project.status = "blueprint_ready"`
- `backend/app/api/routers/novels.py:434`: `project.status = "chapter_outlines_ready"`
- `backend/app/services/part_outline_service.py:199`: `project.status = "part_outlines_ready"`
- `frontend/src/views/InspirationMode.vue:232`: `if (project.status !== 'draft')`

### 影响

- 🟢 **低影响**:
  - 类型不安全，容易拼写错误
  - IDE无法提供自动补全
  - 难以追踪所有状态值的使用

### 修复方案

#### 后端：添加枚举类

**新建文件**: `backend/app/core/constants.py`

```python
from enum import Enum

class ProjectStatus(str, Enum):
    """项目状态枚举"""
    DRAFT = "draft"
    BLUEPRINT_READY = "blueprint_ready"
    PART_OUTLINES_READY = "part_outlines_ready"
    CHAPTER_OUTLINES_READY = "chapter_outlines_ready"
    WRITING = "writing"  # 可选，见问题3
    COMPLETED = "completed"  # 可选，见问题3

    def __str__(self) -> str:
        return self.value
```

**使用示例**:
```python
from app.core.constants import ProjectStatus

# 修改前
project.status = "blueprint_ready"

# 修改后
project.status = ProjectStatus.BLUEPRINT_READY
```

#### 前端：添加类型枚举

**新建文件**: `frontend/src/types/enums.ts`

```typescript
export enum ProjectStatus {
  DRAFT = 'draft',
  BLUEPRINT_READY = 'blueprint_ready',
  PART_OUTLINES_READY = 'part_outlines_ready',
  CHAPTER_OUTLINES_READY = 'chapter_outlines_ready',
  WRITING = 'writing',  // 可选，见问题3
  COMPLETED = 'completed'  // 可选，见问题3
}

// 状态显示名称映射
export const PROJECT_STATUS_LABELS: Record<ProjectStatus, string> = {
  [ProjectStatus.DRAFT]: '灵感收集中',
  [ProjectStatus.BLUEPRINT_READY]: '蓝图完成',
  [ProjectStatus.PART_OUTLINES_READY]: '部分大纲完成',
  [ProjectStatus.CHAPTER_OUTLINES_READY]: '章节大纲完成',
  [ProjectStatus.WRITING]: '写作中',
  [ProjectStatus.COMPLETED]: '已完成'
}
```

**使用示例**:
```typescript
import { ProjectStatus } from '@/types/enums'

// 修改前
if (project.status === 'draft') { ... }

// 修改后
if (project.status === ProjectStatus.DRAFT) { ... }
```

---

## 修复优先级

### 立即修复（已完成）
- ✅ **问题1**: 提示词矛盾指令（已修复）

### 短期修复（本周内）
- ⏳ **问题2**: Schema注释不一致（简单修改，5分钟）

### 中期优化（可选，1-2周内）
- ⏳ **问题5**: 添加状态枚举定义（提升代码质量，半天工作量）
- ⏳ **问题3**: 完善状态迁移（需要测试，1天工作量）

### 长期重构（可选，未来版本）
- ⏳ **问题4**: 统一前端状态判断（较大重构，2-3天工作量）

---

## 测试建议

### 问题2修复后的测试

**测试场景**: 验证注释修改是否正确

**测试步骤**:
1. 检查 `backend/app/schemas/novel.py:133` 注释是否已修正
2. 检查 `frontend/src/api/novel.ts:56` 注释是否已修正
3. 确认所有状态注释一致：draft, blueprint_ready, part_outlines_ready, chapter_outlines_ready

**预期结果**: 所有注释统一，不再出现错误的 `need_part_outlines`

### 问题3修复后的测试

**测试场景1**: 验证writing状态迁移

**测试步骤**:
1. 创建项目，完成灵感对话（status=draft）
2. 生成蓝图（status=blueprint_ready）
3. 生成章节大纲（status=chapter_outlines_ready）
4. 生成第1章（status应该变为writing）✅

**预期结果**: 第4步后项目状态为"writing"

**测试场景2**: 验证completed状态迁移

**测试步骤**:
1. 项目状态为writing
2. 总章节数为5章
3. 依次为5章都选择版本
4. 选择最后一章的版本后（status应该变为completed）✅

**预期结果**: 第4步后项目状态为"completed"

### 问题4修复后的测试

**测试场景**: 验证统一的状态判断

**测试步骤**:
1. 在各个组件中使用 `useProjectStatus` composable
2. 验证状态判断逻辑一致
3. 修改status，观察所有组件是否正确响应

**预期结果**: 所有组件使用统一的状态判断逻辑

---

## 向后兼容性

### 不兼容变更

**无**：所有修复都是向后兼容的

**原因**:
- 问题1：只删除了矛盾的旧指令，不影响现有功能
- 问题2：只修改注释，不影响代码逻辑
- 问题3、4、5：都是可选优化，不修改现有API

### 数据迁移

**不需要**数据库迁移，原因：
- 只修改了代码逻辑和注释
- 不涉及数据库schema变更
- 新增的状态值（writing, completed）对旧数据无影响

---

## 总结

### 核心发现

1. ✅ **工作流分离原则基本正确**: 蓝图、章节大纲、内容生成是分离的
2. ⚠️ **状态管理不够完善**: 缺少部分状态迁移
3. ⚠️ **前端状态判断不统一**: 依赖blueprint字段而非status

### 修复建议

**必须修复**:
- ✅ 问题1（已完成）
- ⏳ 问题2（简单修改）

**建议修复**:
- 问题5（提升代码质量）
- 问题3（完善状态追踪）

**可选优化**:
- 问题4（需要较大重构，但收益明显）

### 技术债务

**当前技术债务**:
- 前端状态判断逻辑分散
- 缺少完整的状态枚举定义
- 状态迁移不完整（缺少writing和completed）

**偿还计划**:
- 短期：修复注释不一致（问题2）
- 中期：添加状态枚举（问题5）和完善状态迁移（问题3）
- 长期：重构前端状态判断（问题4）

---

## 相关文档

- [工作流分离修复](./workflow-separation-fix.md)
- [灵感模式自动打开问题修复](./inspiration-mode-auto-opening-fix.md)
- [工作流程文档](./novel_workflow.md)
