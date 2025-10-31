# 章节大纲灵活管理功能文档

## 📋 功能概述

为长篇小说（>50章）提供更灵活的章节大纲管理功能，允许用户增量生成、删除和重新生成章节大纲，而不是一次性生成全部。

## 🎯 设计目标

### 1. 增量生成
- ✅ 不需要一次性生成所有章节大纲
- ✅ 可以写一部分、生成一部分
- ✅ 降低一次性生成失败的风险

### 2. 快速调整
- ✅ 不满意最新几章可以快速删除
- ✅ 删除后重新生成
- ✅ 避免全部推倒重来

### 3. 精准优化
- ✅ 重新生成最新章节时可输入提示词
- ✅ 精确引导AI生成方向
- ✅ 提高大纲质量

## 🔄 新的工作流程

### 长篇小说（>50章）流程

```
1. [生成部分大纲]
   ↓
2. [显示部分大纲列表]
   ↓
3. [章节大纲管理区域]
   ├── 显示已生成的章节大纲列表
   ├── [生成大纲] 按钮（输入数量）
   ├── [删除大纲] 按钮（输入数量）
   └── [重新生成最新章节] 按钮（可输入提示词）
```

### 短篇小说（≤50章）流程

```
1. [一次性生成全部章节大纲]
   ↓
2. [显示章节大纲列表]
   └── 编辑按钮（保持原样）
```

## 🎨 UI 设计

### 章节大纲管理面板

一个渐变背景的卡片，包含3个操作区域：

#### 1. 生成大纲
- 输入框：要生成的章节数量
- 范围：1 到 (总章节数 - 已生成数)
- 示例："生成10章" → 从第11章生成到第20章
- 按钮：绿色渐变
- 确认提示："确定要生成后续N章大纲吗？"

#### 2. 删除大纲
- 输入框：要删除的章节数量
- 范围：1 到 已生成数
- 示例："删除5章" → 删除第16-20章（假设当前有20章）
- 按钮：红色渐变
- 确认提示："确定要删除第X到第Y章大纲吗？此操作不可撤销。"

#### 3. 重新生成最新章节
- 按钮：青色渐变
- 点击后打开对话框
- 对话框包含：
  - 提示词输入框（可选）
  - 常用示例（增加转折点、强化情感冲突等）
  - 警告提示

## 💻 前端实现

### 新增组件

#### 1. `ChapterOutlineActions.vue`
**位置**：`frontend/src/components/novel-detail/ChapterOutlineActions.vue`

**Props**：
```typescript
interface Props {
  projectId: string
  currentChapterCount: number  // 已生成的章节大纲数量
  totalChapters: number        // 总章节数
  latestChapterNumber: number  // 最新章节编号
}
```

**Emits**：
```typescript
emits: {
  refresh: []  // 操作完成后刷新父组件数据
}
```

**功能**：
- 3个输入区域（生成/删除/重新生成）
- 输入验证
- 确认对话框
- 加载状态

#### 2. `RegenerateOutlineModal.vue`
**位置**：`frontend/src/components/RegenerateOutlineModal.vue`

**Props**：
```typescript
interface Props {
  show: boolean
  title: string
  description?: string
  warningTitle?: string
  warningMessage?: string
  examples?: string[]
  isGenerating?: boolean
}
```

**功能**：
- 提示词输入
- 示例快速填入
- 警告提示
- 确认/取消按钮

### 重构组件

#### `ChapterOutlineSection.vue`
**重构内容**：
- 移除旧的批量生成逻辑（`ChapterOutlineBatchGenerator`）
- 简化显示逻辑
- 集成 `ChapterOutlineActions` 组件
- 优化部分大纲展示

**新的显示逻辑**：
```typescript
// 长篇小说
if (needsPartOutlines) {
  if (!hasPartOutlines) {
    // 显示：生成部分大纲按钮
  } else {
    // 显示：部分大纲列表
    // 显示：章节大纲列表
    // 显示：ChapterOutlineActions（始终显示）
  }
}

// 短篇小说
else {
  if (outline.length === 0) {
    // 显示：一次性生成按钮
  } else {
    // 显示：章节大纲列表
    // 显示：编辑按钮
  }
}
```

## 🔌 后端 API 需求

### 1. 生成指定数量的章节大纲

```python
POST /api/writer/novels/{project_id}/chapter-outlines/generate-count

Request Body:
{
  "count": 10,  # 要生成的数量
  "start_from": 11  # 可选，从第几章开始，默认为当前最大章节号+1
}

Response:
{
  "message": "成功生成10章大纲",
  "generated_chapters": [11, 12, 13, ..., 20],
  "total_chapters": 20
}
```

**实现要点**：
- 查询当前项目已有的最大章节号
- 从 `start_from` 开始生成 `count` 个章节
- 使用现有的章节大纲生成逻辑
- 支持并行生成（可选）

### 2. 删除最新的N章大纲

```python
DELETE /api/writer/novels/{project_id}/chapter-outlines/delete-latest

Request Body:
{
  "count": 5  # 要删除的数量
}

Response:
{
  "message": "成功删除5章大纲",
  "deleted_chapters": [16, 17, 18, 19, 20],
  "remaining_chapters": 15
}
```

**实现要点**：
- 查询当前项目的最大章节号
- 计算要删除的章节范围：`[max - count + 1, max]`
- 删除章节大纲记录（`chapter_outlines` 表）
- 同时检查并删除相关的章节内容和版本（如果有）

### 3. 重新生成指定章节大纲

```python
POST /api/writer/novels/{project_id}/chapter-outlines/{chapter_number}/regenerate

Request Body:
{
  "prompt": "增加转折点，强化情感冲突"  # 可选的优化提示词
}

Response:
{
  "message": "第20章大纲已重新生成",
  "chapter_outline": {
    "chapter_number": 20,
    "title": "...",
    "summary": "..."
  }
}
```

**实现要点**：
- 查询指定章节的当前大纲
- 如果提供了 `prompt`，将其加入到生成提示中
- 重新生成该章节大纲
- 更新数据库记录（覆盖原有内容）
- **不影响该章节已生成的正文内容**

## 🎬 使用场景

### 场景1：渐进式创作

**用户**：写了10章后想看看后续怎么发展

**操作**：
1. 点击"生成大纲"
2. 输入 10
3. 确认
4. 等待2-3分钟
5. 查看第11-20章的大纲

### 场景2：调整不满意的大纲

**用户**：第18-20章的大纲不理想

**操作**：
1. 点击"删除大纲"
2. 输入 3
3. 确认删除
4. 点击"生成大纲"
5. 输入 3
6. 重新生成第18-20章

### 场景3：精准优化最新章节

**用户**：第20章的大纲需要更多悬念

**操作**：
1. 点击"重新生成最新章节"
2. 输入提示词："增加悬念，设置转折点"
3. 确认
4. 等待30秒
5. 查看优化后的第20章大纲

## ⚠️ 注意事项

### 1. 数据一致性
- 删除章节大纲时，检查是否有已生成的章节内容
- 如果有内容，给出警告提示
- 建议先删除章节内容，再删除大纲

### 2. 并发控制
- 同一时间只能执行一个操作
- 使用loading状态禁用其他按钮

### 3. 状态持久化
- 生成操作支持刷新后恢复状态
- 使用 `GenerationType.CHAPTER_OUTLINE`
- 超时时间：5分钟

### 4. 用户体验
- 所有操作都有确认对话框
- 清晰的成功/失败提示
- 显示剩余可生成数量
- 显示当前已生成数量

## 📊 数据流

```
用户点击"生成10章"
   ↓
前端验证输入（1-50章）
   ↓
显示确认对话框
   ↓
调用 POST /api/.../generate-count
   ↓
后端：
  - 查询当前最大章节号（假设为10）
  - 生成第11-20章大纲
  - 写入数据库
  - 返回结果
   ↓
前端：
  - 显示成功提示
  - emit('refresh')
  - 父组件重新加载项目数据
  - 章节大纲列表更新
```

## 🔧 后端实现建议

### 参考现有代码

1. **章节大纲生成**：参考 `generate_chapter_outline()` (writer.py:778)
2. **批量生成逻辑**：参考 `generate_chapter_outlines()` (novels.py:480)
3. **删除逻辑**：参考其他删除端点的实现

### 新增端点位置

建议在 `backend/app/api/routers/writer.py` 添加：
- `generate_chapter_outlines_by_count()`
- `delete_latest_chapter_outlines()`
- `regenerate_chapter_outline()`

## ✅ 完成清单

### 前端
- ✅ 创建 `ChapterOutlineActions.vue`
- ✅ 创建 `RegenerateOutlineModal.vue`
- ✅ 重构 `ChapterOutlineSection.vue`
- ⏳ 添加前端 API 调用方法（`novel.ts`）
- ⏳ 集成状态持久化
- ⏳ 测试完整流程

### 后端
- ⏳ 实现生成指定数量API
- ⏳ 实现删除最新N章API
- ⏳ 实现重新生成API
- ⏳ 添加数据验证和错误处理
- ⏳ 测试API端点

## 🚀 后续优化方向

1. **批量重新生成**：支持重新生成最新N章（而不只是1章）
2. **撤销功能**：删除前自动备份，支持一键恢复
3. **进度显示**：批量生成时显示实时进度
4. **智能建议**：根据已有内容智能推荐生成数量

## 📝 测试计划

### 单元测试
- 输入验证逻辑
- 计算剩余章节数
- 计算删除范围

### 集成测试
- 生成 → 查看 → 删除 → 重新生成 完整流程
- 并发操作控制
- 错误处理（网络错误、后端错误）

### 用户测试
- 长篇小说（200章）场景
- 短篇小说（30章）场景
- 边界情况（生成全部、删除全部）
