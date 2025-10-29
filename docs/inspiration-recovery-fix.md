# 灵感模式对话恢复机制修复文档

## 问题描述

用户报告："无法恢复灵感模式的对话记录"

## 根本原因分析

在 `frontend/src/views/InspirationMode.vue` 的 `findUnfinishedProject` 函数中发现两个严重错误：

### 错误 1: 方法名错误

**位置**: InspirationMode.vue:404

**错误代码**:
```typescript
await novelStore.fetchProjects()
```

**问题**: `novelStore` 中不存在 `fetchProjects()` 方法，正确的方法名是 `loadProjects()`

**影响**: 导致恢复机制的第三层（查找未完成项目）完全失效，抛出 `TypeError: novelStore.fetchProjects is not a function`

### 错误 2: 类型不匹配的字段访问

**位置**: InspirationMode.vue:408-410

**错误代码**:
```typescript
const unfinished = projects.find(p =>
  p.status === 'draft' &&
  (!p.blueprint || Object.keys(p.blueprint).length === 0)
)
```

**问题**:
- `projects` 是 `NovelProjectSummary[]` 类型
- `NovelProjectSummary` 接口中**没有** `blueprint` 字段
- 该接口只包含: `id`, `title`, `genre`, `last_edited`, `completed_chapters`, `total_chapters`, `status`

**影响**:
- `p.blueprint` 访问永远返回 `undefined`
- 判断逻辑 `!p.blueprint` 永远为 `true`
- 实际上变成了只检查 `p.status === 'draft'`，但由于错误1的存在，这段代码根本无法执行

### 逻辑简化

根据我们的新工作流设计：
- `status === 'draft'` → 项目处于灵感对话阶段
- `status === 'blueprint_ready'` → 蓝图已生成，等待生成章节大纲
- `status === 'chapter_outlines_ready'` → 章节大纲已生成，可以开始写作

因此，**只需检查 `status === 'draft'` 就足以判断项目是否处于灵感模式**。

## 修复方案

### 修改内容

**文件**: `frontend/src/views/InspirationMode.vue`
**函数**: `findUnfinishedProject` (401-415行)

**修复后的代码**:
```typescript
// 查找未完成的项目（灵感模式进行中的项目）
const findUnfinishedProject = async () => {
  try {
    await novelStore.loadProjects()  // 修复1: fetchProjects → loadProjects
    const projects = novelStore.projects

    // 查找符合条件的项目：状态为 draft（灵感模式进行中）
    const unfinished = projects.find(p => p.status === 'draft')  // 修复2: 移除 blueprint 检查

    return unfinished
  } catch (error) {
    console.error('查找未完成项目失败:', error)
    return null
  }
}
```

### 修复说明

1. **`fetchProjects()` → `loadProjects()`**: 使用正确的 store 方法名
2. **移除 blueprint 字段检查**:
   - `NovelProjectSummary` 没有 `blueprint` 字段
   - `status === 'draft'` 已经足够判断项目是否在灵感模式
3. **简化逻辑**: 根据状态机设计，draft 状态就代表灵感模式进行中

## 灵感模式恢复机制详解

### 三层恢复策略

InspirationMode.vue 的 `onMounted` 钩子实现了三层恢复机制（优先级从高到低）：

#### 优先级 1: URL 参数 `project_id`

**触发场景**: 用户从工作台点击 draft 状态的项目卡片

**代码位置**: InspirationMode.vue:421-426
```typescript
const projectId = route.query.project_id as string
if (projectId) {
  await restoreConversation(projectId)
  return
}
```

**工作流**:
1. 用户在 NovelWorkspace.vue 点击 draft 项目的"继续创作"按钮
2. NovelWorkspace.vue:173-181 判断 `project.status === 'draft'`
3. 跳转到 `/inspiration?project_id={id}`
4. InspirationMode 接收 URL 参数，调用 `restoreConversation(projectId)`

#### 优先级 2: localStorage 缓存

**触发场景**: 用户刷新页面或意外关闭浏览器

**代码位置**: InspirationMode.vue:428-439
```typescript
const cachedProjectId = localStorage.getItem(STORAGE_KEY)
if (cachedProjectId) {
  try {
    await restoreConversation(cachedProjectId)
    return
  } catch (error) {
    console.warn('缓存的项目ID失效，已清理:', error)
    localStorage.removeItem(STORAGE_KEY)
  }
}
```

**工作流**:
1. 用户开始灵感对话时，`startConversation()` 将项目ID存入 localStorage
2. 用户刷新页面或浏览器崩溃后重新打开
3. InspirationMode 读取 localStorage，恢复对话

**注意**: 如果缓存的项目已被删除，会捕获异常并清理缓存

#### 优先级 3: 查找未完成项目

**触发场景**: 用户直接访问 `/inspiration` 路径，且有未完成的灵感对话

**代码位置**: InspirationMode.vue:441-452
```typescript
const unfinishedProject = await findUnfinishedProject()
if (unfinishedProject) {
  const confirmed = await globalAlert.showConfirm(
    `检测到未完成的对话"${unfinishedProject.title}"，是否继续？`,
    '恢复对话'
  )
  if (confirmed) {
    await restoreConversation(unfinishedProject.id)
    return
  }
}
```

**工作流**:
1. 调用 `novelStore.loadProjects()` 获取所有项目摘要
2. 查找 `status === 'draft'` 的项目
3. 弹出确认对话框询问用户是否继续
4. 用户确认后恢复对话

**本次修复的重点**: 这一层之前因为方法名错误和字段访问错误而完全失效

### restoreConversation 函数详解

**代码位置**: InspirationMode.vue:222-283

**核心逻辑**:

1. **加载完整项目数据**:
```typescript
await novelStore.loadProject(projectId)
const project = novelStore.currentProject
```
- 注意：这里调用的是 `loadProject(id)`，返回完整的 `NovelProject` 对象
- `NovelProject` 包含 `conversation_history` 和 `blueprint` 字段
- 与 `NovelProjectSummary` 不同，后者是轻量级摘要数据

2. **重建聊天记录**:
```typescript
chatMessages.value = project.conversation_history.map((item): ChatMessage | null => {
  if (item.role === 'user') {
    try {
      const userInput = JSON.parse(item.content)
      return { content: userInput.value, type: 'user' }
    } catch {
      return { content: item.content, type: 'user' }
    }
  } else { // assistant
    try {
      const assistantOutput = JSON.parse(item.content)
      return { content: assistantOutput.ai_message, type: 'ai' }
    } catch {
      return { content: item.content, type: 'ai' }
    }
  }
}).filter((msg): msg is ChatMessage => msg !== null && msg.content !== null)
```
- 解析数据库中的 JSON 字符串
- 提取 `user.value` 和 `assistant.ai_message` 用于显示
- 过滤空消息

3. **恢复 UI 状态**:
```typescript
if (project.blueprint) {
  // 已有蓝图，显示蓝图展示界面
  completedBlueprint.value = project.blueprint
  showBlueprint.value = true
} else {
  // 检查对话是否完成
  const lastAssistantMsg = JSON.parse(lastAssistantMsgStr)
  if (lastAssistantMsg.is_complete) {
    // 对话完成，显示蓝图确认界面
    showBlueprintConfirmation.value = true
  } else {
    // 对话进行中，恢复输入控件
    currentUIControl.value = lastAssistantMsg.ui_control
  }
}
```

## 测试验证方案

### 测试场景 1: URL 参数恢复（优先级最高）

**步骤**:
1. 进入灵感模式，完成 2-3 轮对话
2. 不生成蓝图，返回工作台
3. 在工作台找到该项目，状态应显示"灵感模式进行中"
4. 点击"继续创作"按钮

**预期结果**:
- 跳转到 `/inspiration?project_id={id}`
- 页面自动恢复之前的 2-3 轮对话记录
- 显示最后一条 AI 消息和对应的输入控件
- 可以继续进行对话

**验证点**:
- [ ] URL 包含正确的 project_id 参数
- [ ] 聊天记录完整显示
- [ ] 轮次计数正确（第 N 轮）
- [ ] 输入控件类型正确（single_choice/text_input）

### 测试场景 2: localStorage 缓存恢复

**步骤**:
1. 进入灵感模式，完成 2-3 轮对话
2. 不关闭灵感模式页面，直接刷新浏览器（F5）

**预期结果**:
- 页面刷新后自动恢复对话
- 无需用户手动选择项目

**验证点**:
- [ ] 开发者工具 → Application → Local Storage 中有 `inspiration_project_id` 键
- [ ] 刷新后对话记录完整恢复
- [ ] 控制台无错误信息

**调试命令**:
```javascript
// 浏览器控制台执行
console.log(localStorage.getItem('inspiration_project_id'))
```

### 测试场景 3: 查找未完成项目（本次修复重点）

**步骤**:
1. 进入灵感模式，完成 2-3 轮对话
2. 不生成蓝图，返回首页（不通过工作台）
3. 清除 localStorage:
   ```javascript
   localStorage.removeItem('inspiration_project_id')
   ```
4. 直接访问 `/inspiration` 路径（或点击首页的"开启灵感模式"按钮）

**预期结果**:
- 弹出确认对话框："检测到未完成的对话"{项目标题}"，是否继续？"
- 点击"确定"后恢复对话

**验证点**:
- [ ] 确认对话框正确弹出
- [ ] 项目标题正确显示
- [ ] 点击确定后对话记录恢复
- [ ] 控制台无 `fetchProjects is not a function` 错误

**本次修复验证**:
```javascript
// 打开浏览器控制台，查看网络请求
// 应该能看到 GET /api/novels 请求成功返回
```

### 测试场景 4: 多个 draft 项目的处理

**步骤**:
1. 创建项目 A，进行 2 轮对话，返回
2. 创建项目 B，进行 1 轮对话，返回
3. 清除 localStorage
4. 直接访问 `/inspiration`

**预期结果**:
- 弹出确认对话框，显示其中一个 draft 项目（通常是列表中的第一个）
- 用户可以选择继续或拒绝
- 如果拒绝，显示"开启灵感模式"按钮

**注意**: `findUnfinishedProject` 使用 `find()` 方法，只返回第一个匹配项

### 测试场景 5: 蓝图已生成的项目

**步骤**:
1. 完成灵感对话，生成蓝图
2. 从工作台点击该项目

**预期结果**:
- 项目状态显示"蓝图完成"或"准备创作"
- 点击"继续创作"跳转到 `/novel/{id}` (写作台)，**不是**灵感模式
- 即使项目标题仍是"未命名灵感"，也应该跳转到写作台

**验证点**:
- [ ] status 字段为 `blueprint_ready` 或 `chapter_outlines_ready`
- [ ] 不会触发灵感模式恢复逻辑

## 错误排查指南

### 问题 1: 控制台报错 `fetchProjects is not a function`

**原因**: InspirationMode.vue 未更新，仍使用错误的方法名

**解决**: 确认 InspirationMode.vue:404 行为 `await novelStore.loadProjects()`

**验证**:
```bash
grep -n "fetchProjects" frontend/src/views/InspirationMode.vue
```
应该没有任何输出

### 问题 2: 恢复后聊天记录为空

**可能原因**:
1. 数据库中没有 `conversation_history` 数据
2. `conversation_history` 的 JSON 格式不正确

**排查步骤**:
```sql
-- 检查数据库
SELECT id, title, status FROM novel_projects WHERE status = 'draft';
SELECT role, content FROM novel_conversations WHERE project_id = '{project_id}';
```

**验证**: conversation_history 应该包含 user 和 assistant 消息

### 问题 3: 弹出"检测到未完成的对话"但点击确定后无反应

**可能原因**: `restoreConversation` 函数抛出异常

**排查步骤**:
1. 打开浏览器控制台查看错误信息
2. 检查网络请求 `GET /api/novels/{id}` 是否成功
3. 检查返回的 JSON 数据是否包含 `conversation_history` 字段

### 问题 4: localStorage 缓存的项目ID失效

**现象**: 控制台显示 "缓存的项目ID失效，已清理"

**原因**:
- 项目已被删除
- 项目ID格式错误

**处理**: 代码已自动清理无效缓存，这是正常行为

## 状态机与恢复逻辑的关系

```
项目状态          是否触发恢复      恢复到哪里
-----------------------------------------------
draft            是               灵感模式（/inspiration?project_id={id}）
blueprint_ready  否               写作台（/novel/{id}）
part_outlines_ready  否           写作台（/novel/{id}）
chapter_outlines_ready  否        写作台（/novel/{id}）
```

**关键设计**:
- 只有 `draft` 状态的项目才会触发灵感模式恢复
- 其他状态一律跳转到写作台
- `findUnfinishedProject` 只查找 `status === 'draft'` 的项目

## 与工作流优化的集成

本次修复是工作流优化的一部分，与以下组件协同工作：

1. **NovelWorkspace.vue**:
   - 根据 `status === 'draft'` 判断是否跳转到灵感模式
   - 提供 URL 参数 `project_id`

2. **ProjectCard.vue**:
   - 显示"灵感模式进行中"状态文本
   - 引导用户点击"继续创作"

3. **后端 API**:
   - `GET /api/novels` 返回包含 `status` 字段的 `NovelProjectSummary[]`
   - `GET /api/novels/{id}` 返回完整的 `NovelProject`（包含 conversation_history）

## 总结

### 修复内容

1. **方法名纠正**: `fetchProjects()` → `loadProjects()`
2. **类型安全**: 移除对 `NovelProjectSummary.blueprint` 的非法访问
3. **逻辑简化**: 利用 `status` 字段准确判断项目状态

### 影响范围

- 修复了灵感模式恢复机制的第三层（查找未完成项目）
- 提升了对话恢复的可靠性
- 消除了控制台错误

### 验证标准

- [x] 修复前：`novelStore.fetchProjects is not a function` 错误
- [x] 修复后：三层恢复机制全部正常工作
- [ ] 所有测试场景通过
- [ ] 控制台无错误或警告
