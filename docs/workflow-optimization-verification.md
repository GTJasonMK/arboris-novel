# 小说生成工作流优化验证文档

## 优化概述

### 优化目标
重构小说生成工作流，将蓝图生成与章节大纲生成解耦，实现清晰的分阶段生成流程。

### 核心问题
- **之前**: 蓝图生成时包含章节大纲，导致流程混乱，长篇小说生成效率低
- **现在**: 蓝图只包含基础设定，章节大纲分离为独立生成步骤

### 新工作流
```
灵感模式（对话）
  ↓
蓝图生成（基础设定）
  ↓
├─ 短篇（≤50章）→ 一次性生成章节大纲 → 写作
└─ 长篇（>50章）→ 生成部分大纲 → 批量生成章节大纲 → 写作
```

---

## 修改清单

### 后端修改（4个文件）

#### 1. `backend/prompts/screenwriting.md` (97-140行)
**修改内容**: 移除章节大纲生成指令，添加新的章节数估算规则

**关键变更**:
```markdown
3. **章节大纲生成规则（重要变更）**

**注意：在此蓝图生成阶段，不要生成任何章节大纲。章节大纲将在后续步骤中单独生成。**

你只需要完成以下工作：

1. **估算总章节数**：根据故事复杂度和用户讨论的内容，估算合理的总章节数，设置 `total_chapters` 字段

2. **判断是否需要分阶段生成**：
   - 短篇小说（≤50章）：设置 `needs_part_outlines: false`
   - 长篇小说（>50章）：设置 `needs_part_outlines: true`，设置 `chapters_per_part: 25`

3. **chapter_outline 必须设为空数组**：`"chapter_outline": []`
```

#### 2. `backend/app/api/routers/novels.py` (256-290行，293-417行)
**修改内容**:
- 简化蓝图生成逻辑，移除章节大纲生成
- 新增短篇小说章节大纲生成端点

**新增API端点**:
```python
@router.post("/{project_id}/chapter-outlines/generate")
async def generate_chapter_outlines(
    project_id: str,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
):
    """为短篇小说（≤50章）一次性生成全部章节大纲"""
    # ... 实现逻辑
```

**状态变化**:
- 蓝图生成完成 → `project.status = "blueprint_ready"`
- 章节大纲生成完成 → `project.status = "chapter_outlines_ready"`

#### 3. `backend/app/services/part_outline_service.py` (198-201行，350-362行)
**修改内容**: 完善部分大纲生成的状态更新逻辑

**关键变更**:
```python
# 部分大纲生成完成后
project.status = "part_outlines_ready"

# 所有部分的章节大纲都生成完成后
if all_completed:
    project.status = "chapter_outlines_ready"
```

#### 4. `backend/app/schemas/novel.py` & `backend/app/services/novel_service.py`
**修改内容**: NovelProjectSummary 添加 status 字段

---

### 前端修改（5个文件）

#### 1. `frontend/src/api/novel.ts` (55行，307-315行)
**修改内容**:
- NovelProjectSummary 添加 status 字段
- 新增 generateAllChapterOutlines API 方法

```typescript
export interface NovelProjectSummary {
  // ...
  status: string  // 项目状态：draft, blueprint_ready, part_outlines_ready, chapter_outlines_ready 等
}

// 短篇小说（≤50章）一次性生成全部章节大纲
static async generateAllChapterOutlines(projectId: string): Promise<{
  message: string
  total_chapters: number
  status: string
}>
```

#### 2. `frontend/src/views/NovelWorkspace.vue` (173-181行)
**修改内容**: 基于 status 字段判断路由目标

```typescript
const enterProject = (project: NovelProjectSummary) => {
  if (project.status === 'draft') {
    router.push(`/inspiration?project_id=${project.id}`)  // 跳转到灵感模式
  } else {
    router.push(`/novel/${project.id}`)  // 跳转到写作台
  }
}
```

#### 3. `frontend/src/components/ProjectCard.vue` (136-157行)
**修改内容**: 根据 status 显示准确的状态文本

```typescript
const getStatusText = computed(() => {
  const { completed_chapters, total_chapters, status } = props.project

  if (status === 'draft') return '灵感模式进行中'
  if (status === 'need_part_outlines') return '需要生成部分大纲'
  if (completed_chapters > 0) return `已完成 ${completed_chapters}/${total_chapters} 章`
  // ...
})
```

#### 4. `frontend/src/components/novel-detail/ChapterOutlineGenerator.vue` (新建)
**功能**: 短篇小说章节大纲生成器组件

**显示条件**:
- 蓝图已生成（blueprint_ready）
- 不需要部分大纲（needs_part_outlines == false）
- 章节大纲未生成（outline.length == 0）

**核心逻辑**:
```typescript
const generateChapterOutlines = async () => {
  const result = await NovelAPI.generateAllChapterOutlines(props.projectId)
  await novelStore.loadProject(props.projectId)  // 刷新项目数据
}
```

#### 5. `frontend/src/components/novel-detail/ChapterOutlineSection.vue` (修改)
**修改内容**: 添加短篇小说生成器的集成逻辑

```vue
<!-- 短篇小说: 一次性生成章节大纲 -->
<ChapterOutlineGenerator v-if="showChapterOutlineGenerator" :projectId="projectId" />
```

```typescript
// 短篇小说显示逻辑：不需要部分大纲 且 还没有章节大纲
const showChapterOutlineGenerator = computed(() =>
  !needsPartOutlines.value && props.outline.length === 0
)
```

---

## 项目状态流转图

```
draft (草稿/灵感模式中)
  ↓ [完成灵感对话，生成蓝图]
blueprint_ready (蓝图就绪)
  ↓
  ├─ 短篇（needs_part_outlines: false）
  │    ↓ [点击"生成章节大纲"按钮]
  │    chapter_outlines_ready (章节大纲就绪)
  │
  └─ 长篇（needs_part_outlines: true）
       ↓ [点击"生成部分大纲"按钮]
       part_outlines_ready (部分大纲就绪)
       ↓ [逐个或批量生成各部分的章节大纲]
       chapter_outlines_ready (章节大纲就绪)
```

---

## 测试场景

### 场景 1: 短篇小说完整流程（新流程）

**步骤**:
1. 进入灵感模式，与 AI 对话
2. 对话完成后，点击"生成蓝图"
3. 蓝图生成完成，估算总章节数为 30 章
4. 在详情页看到提示："您的小说计划 30 章，接下来请在详情页点击「生成章节大纲」按钮来规划具体章节。"
5. 进入详情页，看到 `ChapterOutlineGenerator` 组件
6. 点击"生成章节大纲"按钮
7. 等待生成完成

**预期结果**:
- 步骤 2 后：`project.status = "blueprint_ready"`, `blueprint.needs_part_outlines = false`, `blueprint.chapter_outline = []`
- 步骤 5：显示蓝色渐变的"生成章节大纲"按钮
- 步骤 7：`project.status = "chapter_outlines_ready"`, 章节大纲表中有 30 条记录
- 步骤 7 后：ChapterOutlineGenerator 隐藏，显示标准章节大纲列表

### 场景 2: 长篇小说完整流程（优化后）

**步骤**:
1. 进入灵感模式，与 AI 对话
2. 对话完成后，点击"生成蓝图"
3. 蓝图生成完成，估算总章节数为 150 章
4. 在详情页看到提示："您的小说计划 150 章，接下来请在详情页点击「生成部分大纲」按钮来规划整体结构，然后再生成详细的章节大纲。"
5. 进入详情页，看到 `PartOutlineGenerator` 组件
6. 点击"生成部分大纲"按钮
7. 等待生成完成，系统生成 6 个部分（每部分 25 章）
8. 看到 `ChapterOutlineBatchGenerator` 组件
9. 点击"批量生成章节大纲"或逐个生成
10. 等待所有部分的章节大纲生成完成

**预期结果**:
- 步骤 2 后：`project.status = "blueprint_ready"`, `blueprint.needs_part_outlines = true`, `blueprint.total_chapters = 150`
- 步骤 7：`project.status = "part_outlines_ready"`, `blueprint.part_outlines.length = 6`
- 步骤 10：`project.status = "chapter_outlines_ready"`, 章节大纲表中有 150 条记录
- 步骤 10 后：PartOutlineGenerator 和 ChapterOutlineBatchGenerator 隐藏，显示标准章节大纲列表

### 场景 3: 未完成项目恢复（已修复的问题）

**步骤**:
1. 进入灵感模式，完成 2-3 轮对话
2. 不点击"生成蓝图"，直接关闭浏览器
3. 重新打开应用，进入"我的小说项目"工作台
4. 查看该项目的卡片状态
5. 点击"继续创作"按钮

**预期结果**:
- 步骤 4：项目卡片显示"灵感模式进行中"状态
- 步骤 5：跳转到 `/inspiration?project_id={id}`，恢复之前的对话历史
- 能够继续进行对话，直至完成

### 场景 4: 蓝图生成后的状态显示

**步骤**:
1. 完成蓝图生成（30 章短篇小说）
2. 不生成章节大纲，返回工作台
3. 查看项目卡片状态

**预期结果**:
- 项目卡片显示"准备创作"或"蓝图完成"状态
- 点击"继续创作"跳转到写作台（不是灵感模式）

### 场景 5: API 错误处理

**步骤**:
1. 进入详情页，点击"生成章节大纲"
2. 假设 API 返回错误（例如 LLM 调用失败）

**预期结果**:
- 显示红色错误提示框
- 显示具体错误信息
- "生成章节大纲"按钮恢复可点击状态（不会永久禁用）

---

## 回归测试检查项

### 后端 API 测试
- [ ] `POST /api/novels/{id}/blueprint/generate` - 蓝图生成不包含章节大纲，返回正确的 `needs_part_outlines` 和 `total_chapters`
- [ ] `POST /api/novels/{id}/chapter-outlines/generate` - 短篇小说章节大纲生成成功，返回正确的章节数
- [ ] `POST /api/writer/novels/{id}/parts/generate` - 长篇小说部分大纲生成成功，项目状态更新为 `part_outlines_ready`
- [ ] `POST /api/writer/novels/{id}/parts/{part_number}/chapters` - 单个部分章节大纲生成成功
- [ ] 所有部分章节大纲生成完成后，项目状态自动更新为 `chapter_outlines_ready`

### 前端组件测试
- [ ] ProjectCard 组件正确显示所有状态（draft, blueprint_ready, part_outlines_ready, chapter_outlines_ready）
- [ ] NovelWorkspace 根据 status 正确路由（draft → inspiration, 其他 → novel detail）
- [ ] ChapterOutlineGenerator 在正确的条件下显示（短篇 + 无章节大纲）
- [ ] PartOutlineGenerator 在正确的条件下显示（长篇 + 无部分大纲）
- [ ] ChapterOutlineBatchGenerator 在正确的条件下显示（长篇 + 已有部分大纲）
- [ ] 标准章节大纲列表在正确的条件下显示（有章节大纲）

### 端到端测试
- [ ] 短篇小说从灵感到章节大纲生成的完整流程
- [ ] 长篇小说从灵感到章节大纲生成的完整流程
- [ ] 中途退出后的项目恢复流程
- [ ] 蓝图生成失败的错误处理
- [ ] 章节大纲生成失败的错误处理

---

## 数据库验证

### 验证蓝图生成后的数据

```sql
-- 查看蓝图生成后的项目状态
SELECT id, title, status FROM novel_projects WHERE id = '{project_id}';
-- 预期: status = 'blueprint_ready'

-- 查看蓝图数据
SELECT total_chapters, needs_part_outlines, chapters_per_part
FROM novel_blueprints WHERE project_id = '{project_id}';
-- 预期:
-- - 短篇: total_chapters <= 50, needs_part_outlines = 0
-- - 长篇: total_chapters > 50, needs_part_outlines = 1, chapters_per_part = 25

-- 查看章节大纲（应为空）
SELECT COUNT(*) FROM chapter_outlines WHERE project_id = '{project_id}';
-- 预期: 0
```

### 验证章节大纲生成后的数据

```sql
-- 短篇小说
SELECT COUNT(*), MIN(chapter_number), MAX(chapter_number)
FROM chapter_outlines WHERE project_id = '{project_id}';
-- 预期: COUNT = total_chapters, MIN = 1, MAX = total_chapters

-- 长篇小说
SELECT part_number, title, start_chapter, end_chapter, generation_status
FROM part_outlines WHERE project_id = '{project_id}';
-- 预期: 所有 generation_status = 'completed'

SELECT COUNT(*) FROM chapter_outlines WHERE project_id = '{project_id}';
-- 预期: COUNT = total_chapters
```

---

## 已知问题和注意事项

### 1. 向后兼容性
本次优化采用**激进策略，不保证向后兼容**。

**影响**:
- 旧项目可能在蓝图中包含 `chapter_outline` 数据，但新流程会忽略这些数据
- 如果旧项目状态为 `blueprint_ready` 但已有章节大纲，不会触发 ChapterOutlineGenerator

**建议**:
- 清理测试数据库，从头开始测试新流程
- 生产环境部署前，手动将已有项目的状态更新为正确值

### 2. 状态不一致修复

如果发现状态不一致（例如有章节大纲但 status 仍是 blueprint_ready），执行：

```sql
-- 短篇小说修复
UPDATE novel_projects np
SET status = 'chapter_outlines_ready'
WHERE EXISTS (
  SELECT 1 FROM chapter_outlines co
  WHERE co.project_id = np.id
)
AND EXISTS (
  SELECT 1 FROM novel_blueprints nb
  WHERE nb.project_id = np.id AND nb.needs_part_outlines = 0
);

-- 长篇小说修复
UPDATE novel_projects np
SET status = 'part_outlines_ready'
WHERE EXISTS (
  SELECT 1 FROM part_outlines po
  WHERE po.project_id = np.id
)
AND NOT EXISTS (
  SELECT 1 FROM chapter_outlines co
  WHERE co.project_id = np.id
);

UPDATE novel_projects np
SET status = 'chapter_outlines_ready'
WHERE EXISTS (
  SELECT 1 FROM part_outlines po
  WHERE po.project_id = np.id AND po.generation_status = 'completed'
)
AND EXISTS (
  SELECT 1 FROM chapter_outlines co
  WHERE co.project_id = np.id
);
```

### 3. 缓存清理

测试前务必：
- 清除浏览器缓存（或使用无痕模式）
- 重启后端服务（确保提示词缓存刷新）
- 清理 localStorage（灵感模式对话恢复缓存）

---

## 验证完成标准

### 必须通过的测试
1. ✅ 短篇小说（≤50章）完整流程测试通过
2. ✅ 长篇小说（>50章）完整流程测试通过
3. ✅ draft 状态的项目能正确跳转到灵感模式并恢复对话
4. ✅ 非 draft 状态的项目能正确跳转到写作台
5. ✅ 项目卡片显示准确的状态文本
6. ✅ 所有新增 API 端点正常工作
7. ✅ 所有前端组件在正确的条件下显示/隐藏
8. ✅ 无控制台错误或警告

### 性能验证
- 短篇小说（30章）章节大纲生成时间 < 60 秒
- 长篇小说（150章）部分大纲生成时间 < 90 秒
- 单个部分（25章）章节大纲生成时间 < 60 秒

### 用户体验验证
- 每个阶段都有清晰的提示信息
- 错误信息具体明确，不出现"未知错误"
- 按钮状态明确（禁用时有 loading 指示）
- 生成完成后自动刷新数据，无需手动刷新页面

---

## 问题排查指南

### 问题 1: 点击"生成章节大纲"后无反应

**检查**:
1. 浏览器控制台是否有 JavaScript 错误
2. 网络请求是否成功发送（检查 Network 标签）
3. 后端日志是否有错误

**可能原因**:
- API 路径错误
- 权限验证失败（Token 过期）
- 后端服务未启动或崩溃

### 问题 2: 章节大纲生成后页面不刷新

**检查**:
1. `ChapterOutlineGenerator.vue` 中的 `novelStore.loadProject(props.projectId)` 是否执行
2. novel store 的 `loadProject` 方法是否正常返回

**可能原因**:
- API 调用成功但未刷新 store
- 组件未正确响应 store 变化

### 问题 3: 长篇小说所有部分完成后状态未更新

**检查**:
1. `part_outline_service.py` 的 `generate_part_chapters` 方法中的 finally 块是否执行
2. 数据库中 `part_outlines` 表的 `generation_status` 是否全部为 'completed'

**可能原因**:
- 状态更新逻辑有异常
- 数据库事务未提交

---

## 总结

本次优化实现了**蓝图生成与章节大纲生成的完全解耦**，使工作流更加清晰、高效。

**关键收益**:
1. **流程清晰**: 每个阶段职责明确，用户不会困惑
2. **性能提升**: 长篇小说不再一次性生成所有章节大纲，避免超时
3. **状态准确**: 基于 status 字段的精确状态管理，恢复机制可靠
4. **可扩展性**: 为未来添加更多生成策略（如分卷、分册）奠定基础

**技术亮点**:
- 后端提示词工程优化（screenwriting.md）
- RESTful API 设计（职责分离）
- 前端组件条件渲染逻辑（ChapterOutlineSection.vue）
- 状态机驱动的 UI 显示（ProjectCard.vue）
