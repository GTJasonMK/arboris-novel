# 灵感模式自动打开项目问题修复

## 问题描述

**用户反馈**: "灵感模式为什么会默认打开一个项目？？这是不是存在逻辑问题？"

**问题表现**:
1. ❌ 进入灵感模式时，自动恢复显示已完成的项目（status='blueprint_ready'）
2. ❌ 在灵感模式中显示已生成的蓝图内容
3. ❌ 已完成灵感对话阶段的项目，不应该再出现在灵感模式中

**严重程度**: 🔴 高 - 违反了工作流设计，导致状态混乱

**影响范围**:
- 用户体验混乱：灵感模式应该用于创建新项目或继续未完成的对话，而非显示已完成的项目
- 状态机混乱：`blueprint_ready` 状态的项目出现在 `draft` 阶段的界面中
- 缓存污染：localStorage 缓存未正确清理，导致过期数据被复用

---

## 根本原因分析

### 问题 1: localStorage 缓存未及时清理

**设计意图**: localStorage 缓存（`inspiration_project_id`）应仅用于暂存正在进行中的灵感对话（`status='draft'`）

**实际情况**:
- 蓝图生成完成后，项目状态从 `draft` → `blueprint_ready`
- 但 localStorage 中的项目ID未被清理
- 下次进入灵感模式时，系统尝试恢复这个已完成的项目

**错误示例**:
```
用户完成灵感对话 → 生成蓝图 → 项目状态变为 'blueprint_ready'
  ↓
localStorage 仍保存项目ID  ❌ 未清理
  ↓
用户关闭页面后重新进入灵感模式
  ↓
系统从 localStorage 读取项目ID → 恢复项目 → 显示蓝图  ❌ 错误行为
```

---

### 问题 2: restoreConversation 未检查项目状态

**设计意图**: `restoreConversation` 应该只恢复 `draft` 状态的项目

**实际情况**:
- 函数没有在开始时检查 `project.status`
- 即使项目已完成灵感阶段（`status='blueprint_ready'`），仍然会恢复并显示
- 导致灵感模式界面显示蓝图确认或蓝图详情界面

**错误代码**（修复前）:
```javascript
const restoreConversation = async (projectId: string) => {
  try {
    await novelStore.loadProject(projectId)
    const project = novelStore.currentProject

    if (!project) {
      throw new Error('项目不存在')
    }

    // ❌ 缺少状态检查，直接继续恢复
    if (project.conversation_history) {
      conversationStarted.value = true
      // ... 恢复对话内容
    }
  }
}
```

**问题分析**:
1. 没有检查 `project.status`
2. 对所有项目一视同仁，不区分 `draft` 和 `blueprint_ready`
3. 导致已完成项目出现在灵感模式中

---

### 问题 3: findUnfinishedProject 的定义过于宽泛

**代码位置**: `InspirationMode.vue` 第426-440行

**当前逻辑**:
```javascript
const findUnfinishedProject = async () => {
  try {
    await novelStore.loadProjects()
    const projects = novelStore.projects

    // 查找符合条件的项目：状态为 draft（灵感模式进行中）
    const unfinished = projects.find(p => p.status === 'draft')

    return unfinished
  } catch (error) {
    console.error('查找未完成项目失败:', error)
    return null
  }
}
```

**分析**:
- 这个函数本身逻辑正确：只查找 `status='draft'` 的项目
- 但是当配合 localStorage 缓存使用时，会被缓存的优先级绕过
- 恢复优先级：URL参数 > localStorage > findUnfinishedProject
- 如果 localStorage 中有已完成项目的ID，就永远不会执行到 findUnfinishedProject

---

## 完整修复方案

### 修复 1: 蓝图生成完成时清理 localStorage ⭐ 核心修复

**文件**: `frontend/src/views/InspirationMode.vue`

**修改位置**: 第365-376行

**修改前**:
```javascript
const handleBlueprintGenerated = (response: any) => {
  console.log('收到蓝图生成完成事件:', response)
  completedBlueprint.value = response.blueprint
  blueprintMessage.value = response.ai_message
  showBlueprintConfirmation.value = false
  showBlueprint.value = true

  // ❌ 没有清理 localStorage
}
```

**修改后**:
```javascript
const handleBlueprintGenerated = (response: any) => {
  console.log('收到蓝图生成完成事件:', response)
  completedBlueprint.value = response.blueprint
  blueprintMessage.value = response.ai_message
  showBlueprintConfirmation.value = false
  showBlueprint.value = true

  // 蓝图生成完成，灵感对话阶段结束，清除localStorage
  // 项目状态已变为 blueprint_ready，不应该再在灵感模式中恢复
  localStorage.removeItem(STORAGE_KEY)
  console.log('蓝图生成完成，已清除灵感模式缓存')
}
```

**核心改进**:
1. ✅ 蓝图生成完成后立即清理缓存
2. ✅ 防止下次进入灵感模式时误恢复已完成的项目
3. ✅ 添加日志记录，方便调试

---

### 修复 2: restoreConversation 添加状态检查 ⭐ 核心修复

**文件**: `frontend/src/views/InspirationMode.vue`

**修改位置**: 第222-303行

**修改前**:
```javascript
const restoreConversation = async (projectId: string) => {
  try {
    await novelStore.loadProject(projectId)
    const project = novelStore.currentProject

    if (!project) {
      throw new Error('项目不存在')
    }

    // ❌ 直接开始恢复对话，没有检查状态
    if (project.conversation_history) {
      conversationStarted.value = true
      // ... 恢复逻辑
    }
  }
}
```

**修改后**:
```javascript
const restoreConversation = async (projectId: string) => {
  try {
    await novelStore.loadProject(projectId)
    const project = novelStore.currentProject

    if (!project) {
      throw new Error('项目不存在')
    }

    // 关键检查：灵感模式只处理 draft 状态的项目
    if (project.status !== 'draft') {
      // 项目已完成灵感阶段，不应该在灵感模式中显示
      console.warn('项目状态为', project.status, '，已完成灵感阶段，清除缓存')
      localStorage.removeItem(STORAGE_KEY)  // 清除缓存

      const confirmed = await globalAlert.showConfirm(
        `项目"${project.title}"已完成灵感对话阶段，是否跳转到详情页查看？`,
        '跳转确认'
      )

      if (confirmed) {
        router.push(`/novel/${projectId}`)
      } else {
        // 用户不想跳转，重置灵感模式显示初始界面
        resetInspirationMode()
      }
      return
    }

    // 只有 status='draft' 的项目才继续恢复对话
    if (project.conversation_history) {
      conversationStarted.value = true

      // 保存到 localStorage（成功恢复后更新缓存）
      localStorage.setItem(STORAGE_KEY, projectId)

      // ... 恢复对话内容
    }
  } catch (error) {
    console.error('恢复对话失败:', error)
    globalAlert.showError(`无法恢复对话: ${error instanceof Error ? error.message : '未知错误'}`, '加载失败')
    // 恢复失败，清理缓存
    localStorage.removeItem(STORAGE_KEY)
    resetInspirationMode()
  }
}
```

**核心改进**:
1. ✅ 在恢复前检查 `project.status`
2. ✅ 非 `draft` 状态的项目立即清理缓存
3. ✅ 提供友好的用户引导：询问是否跳转到详情页
4. ✅ 防御性编程：任何恢复失败都会清理缓存
5. ✅ 只有成功恢复 `draft` 项目后才更新 localStorage

---

### 修复 3: 蓝图保存时也清理 localStorage（额外保障）

**文件**: `frontend/src/views/InspirationMode.vue`

**修改位置**: 第398-417行

**修改前**:
```javascript
const handleConfirmBlueprint = async () => {
  if (!completedBlueprint.value) {
    globalAlert.showError('蓝图数据缺失，请重新生成或稍后重试。', '保存失败')
    return
  }
  try {
    await novelStore.saveBlueprint(completedBlueprint.value)

    // 跳转到写作工作台
    if (novelStore.currentProject) {
      router.push(`/novel/${novelStore.currentProject.id}`)
    }
  } catch (error) {
    console.error('保存蓝图失败:', error)
    globalAlert.showError(`保存蓝图失败: ${error instanceof Error ? error.message : '未知错误'}`, '保存失败')
  }
}
```

**修改后**:
```javascript
const handleConfirmBlueprint = async () => {
  if (!completedBlueprint.value) {
    globalAlert.showError('蓝图数据缺失，请重新生成或稍后重试。', '保存失败')
    return
  }
  try {
    await novelStore.saveBlueprint(completedBlueprint.value)

    // 蓝图保存成功，清理 localStorage（灵感对话已完成）
    localStorage.removeItem(STORAGE_KEY)

    // 跳转到写作工作台
    if (novelStore.currentProject) {
      router.push(`/novel/${novelStore.currentProject.id}`)
    }
  } catch (error) {
    console.error('保存蓝图失败:', error)
    globalAlert.showError(`保存蓝图失败: ${error instanceof Error ? error.message : '未知错误'}`, '保存失败')
  }
}
```

**核心改进**:
1. ✅ 蓝图保存成功后清理缓存
2. ✅ 双重保障：即使 `handleBlueprintGenerated` 未触发，这里也会清理
3. ✅ 确保跳转到详情页后，灵感模式不会再误恢复

---

## 工作流程图

### 修复前的错误流程

```
用户完成灵感对话
  ↓
生成蓝图
  ↓
项目状态: draft → blueprint_ready
  ↓
localStorage: 项目ID仍然存在  ❌ 未清理
  ↓
用户关闭页面
  ↓
用户重新进入灵感模式
  ↓
onMounted 执行恢复逻辑
  ├─ 优先级1: URL参数（无）
  ├─ 优先级2: localStorage（有！）  ❌ 读取到已完成项目的ID
  └─ 优先级3: findUnfinishedProject（未执行）
  ↓
调用 restoreConversation(已完成项目ID)
  ↓
加载项目，status='blueprint_ready'
  ↓
❌ 没有状态检查，继续恢复
  ↓
显示蓝图确认界面或蓝图详情  ❌ 错误：灵感模式显示了蓝图
```

---

### 修复后的正确流程

```
用户完成灵感对话
  ↓
生成蓝图
  ↓
【handleBlueprintGenerated 触发】
  ├─ 项目状态: draft → blueprint_ready
  ├─ completedBlueprint.value = response.blueprint
  ├─ showBlueprint.value = true
  └─ localStorage.removeItem(STORAGE_KEY)  ✅ 立即清理缓存
  ↓
用户确认蓝图
  ↓
【handleConfirmBlueprint 触发】
  ├─ await novelStore.saveBlueprint(...)
  ├─ localStorage.removeItem(STORAGE_KEY)  ✅ 双重清理（防御性）
  └─ router.push(`/novel/${projectId}`)  ✅ 跳转到详情页
  ↓
用户关闭页面
  ↓
用户重新进入灵感模式
  ↓
【onMounted 执行恢复逻辑】
  ├─ 优先级1: URL参数（无）
  ├─ 优先级2: localStorage（空！）  ✅ 已清理
  └─ 优先级3: findUnfinishedProject
      ├─ 查找 status='draft' 的项目
      ├─ 找到 → 询问用户是否继续  ✅ 正确行为
      └─ 未找到 → 显示初始界面  ✅ 正确行为
  ↓
✅ 灵感模式只处理未完成的对话，不会显示已完成的项目
```

---

### 特殊场景：用户手动通过 URL 恢复已完成项目

```
用户访问 /inspiration?project_id=已完成项目ID
  ↓
【onMounted 执行】
  ├─ 优先级1: URL参数（有！）
  └─ 调用 restoreConversation(已完成项目ID)
  ↓
【restoreConversation 执行】
  ├─ await novelStore.loadProject(projectId)
  ├─ 检查 project.status
  └─ if (project.status !== 'draft')  ✅ 状态检查生效
      ├─ localStorage.removeItem(STORAGE_KEY)  ✅ 清理缓存
      ├─ 弹窗：「项目已完成灵感对话阶段，是否跳转到详情页？」
      ├─ 用户确认 → router.push(`/novel/${projectId}`)  ✅ 跳转
      └─ 用户取消 → resetInspirationMode()  ✅ 显示初始界面
  ↓
✅ 即使通过 URL 强制访问，也会被拦截并引导到正确页面
```

---

## 数据流对比

### 旧流程（错误）

| 时间点 | 项目状态 | localStorage | 灵感模式行为 | 问题 |
|--------|---------|--------------|-------------|------|
| 完成灵感对话 | draft | project_id | 显示对话界面 | 正常 ✅ |
| 生成蓝图 | blueprint_ready | project_id | 显示蓝图界面 | 正常（仍在当前会话）✅ |
| 关闭页面 | blueprint_ready | project_id | - | ❌ 缓存未清理 |
| 重新进入灵感模式 | blueprint_ready | project_id | 恢复并显示蓝图 | ❌ 错误！ |

---

### 新流程（正确）

| 时间点 | 项目状态 | localStorage | 灵感模式行为 | 状态 |
|--------|---------|--------------|-------------|------|
| 完成灵感对话 | draft | project_id | 显示对话界面 | ✅ 正常 |
| 生成蓝图 | blueprint_ready | null | 显示蓝图界面 | ✅ 缓存已清理 |
| 关闭页面 | blueprint_ready | null | - | ✅ 无缓存污染 |
| 重新进入灵感模式 | blueprint_ready | null | 显示初始界面或查找其他draft项目 | ✅ 正确！ |
| 手动URL访问已完成项目 | blueprint_ready | null | 状态检查 → 询问跳转 → 跳转到详情页 | ✅ 拦截并引导 |

---

## 测试验证

### 场景 1: 正常完成灵感对话并生成蓝图

**步骤**:
1. 进入灵感模式，完成对话
2. 点击「生成蓝图」
3. 蓝图生成完成后，检查浏览器控制台
4. 点击「确认蓝图」
5. 跳转到详情页
6. 关闭页面
7. 重新进入灵感模式

**预期结果**:
```
步骤3（蓝图生成完成）：
  控制台输出: "蓝图生成完成，已清除灵感模式缓存"
  localStorage['inspiration_project_id'] = null  ✅

步骤4（确认蓝图）：
  localStorage['inspiration_project_id'] = null  ✅（双重清理）

步骤7（重新进入灵感模式）：
  显示初始界面：「准备好释放你的创造力了吗？」  ✅
  不会自动恢复刚才完成的项目  ✅
```

**验证命令**:
```javascript
// 在浏览器控制台执行
localStorage.getItem('inspiration_project_id')  // 应该返回 null
```

---

### 场景 2: localStorage 中存在已完成项目的ID（模拟缓存污染）

**步骤**:
1. 手动在控制台设置 localStorage：
   ```javascript
   localStorage.setItem('inspiration_project_id', '已完成项目的ID')
   ```
2. 刷新页面（进入灵感模式）

**预期结果**:
```
【restoreConversation 执行】
  ├─ 加载项目
  ├─ 检测到 project.status = 'blueprint_ready'
  ├─ 控制台警告: "项目状态为 blueprint_ready，已完成灵感阶段，清除缓存"
  ├─ localStorage.removeItem('inspiration_project_id')  ✅
  └─ 弹窗: 「项目"xxx"已完成灵感对话阶段，是否跳转到详情页查看？」

用户点击「确定」→ 跳转到详情页  ✅
用户点击「取消」→ 显示灵感模式初始界面  ✅
```

**验证点**:
- ✅ 缓存被立即清理
- ✅ 用户得到友好提示
- ✅ 不会在灵感模式中显示蓝图

---

### 场景 3: 用户通过 URL 强制访问已完成项目

**步骤**:
1. 访问 `/inspiration?project_id=已完成项目的ID`

**预期结果**:
```
同场景2，触发状态检查 → 清理缓存 → 询问跳转  ✅
```

**关键代码执行路径**:
```javascript
onMounted → restoreConversation(projectId from URL)
  → if (project.status !== 'draft')
    → localStorage.removeItem(STORAGE_KEY)
    → globalAlert.showConfirm(...)
```

---

### 场景 4: 存在多个 draft 项目时的行为

**步骤**:
1. 创建项目A，完成灵感对话，生成蓝图（状态: blueprint_ready）
2. 创建项目B，开始灵感对话但未完成（状态: draft）
3. 关闭页面
4. 重新进入灵感模式

**预期结果**:
```
【onMounted 执行】
  ├─ URL参数: 无
  ├─ localStorage: 空（项目A的缓存已清理）
  └─ findUnfinishedProject: 找到项目B（status='draft')
      └─ 弹窗: 「检测到未完成的对话"项目B"，是否继续？」

用户点击「是」→ 恢复项目B的对话  ✅
用户点击「否」→ 显示初始界面  ✅
```

**验证点**:
- ✅ 不会误恢复已完成的项目A
- ✅ 正确找到未完成的项目B
- ✅ 用户有选择权

---

### 场景 5: 蓝图生成失败或用户点击「返回」

**步骤**:
1. 完成灵感对话
2. 点击「生成蓝图」
3. 蓝图生成失败（网络错误或LLM错误）
4. 用户点击「返回」回到对话界面
5. 关闭页面
6. 重新进入灵感模式

**预期结果**:
```
步骤3（生成失败）：
  ├─ 项目状态仍为 'draft'  ✅
  └─ localStorage 仍保存项目ID  ✅（因为未成功生成蓝图）

步骤6（重新进入）：
  ├─ 从 localStorage 恢复项目ID
  ├─ restoreConversation 检查 status='draft'  ✅
  └─ 成功恢复对话界面  ✅
```

**验证点**:
- ✅ 蓝图未生成时，不清理缓存
- ✅ 用户可以继续之前的对话
- ✅ 只有真正完成蓝图生成后才清理

---

## 向后兼容性

### ⚠️ 不兼容变更

**影响**:
1. **已完成项目不会自动恢复**:
   - 之前：可能自动恢复并显示蓝图
   - 现在：拦截并询问是否跳转到详情页

2. **localStorage 清理时机提前**:
   - 之前：可能永远不清理
   - 现在：蓝图生成完成后立即清理

### 数据迁移

**不需要**数据库迁移，原因：
- 只修改了前端逻辑
- 不涉及数据库schema变更
- 不影响已有项目数据

### 旧数据检查

检查是否有用户的浏览器中存在过期的 localStorage 缓存：

**清理脚本**（可在管理后台提供）:
```javascript
// 在浏览器控制台执行，清理所有灵感模式缓存
const key = 'inspiration_project_id'
const cachedId = localStorage.getItem(key)

if (cachedId) {
  console.log(`发现缓存的项目ID: ${cachedId}`)

  // 可选：检查项目状态
  fetch(`/api/novels/${cachedId}`)
    .then(res => res.json())
    .then(project => {
      if (project.status !== 'draft') {
        console.log(`项目状态为 ${project.status}，清理缓存`)
        localStorage.removeItem(key)
      } else {
        console.log(`项目状态为 draft，保留缓存`)
      }
    })
    .catch(() => {
      console.log('项目不存在，清理缓存')
      localStorage.removeItem(key)
    })
} else {
  console.log('无缓存')
}
```

**或者简单粗暴地清理**:
```javascript
localStorage.removeItem('inspiration_project_id')
console.log('已清理灵感模式缓存')
```

---

## 错误排查

### 问题 1: 重新进入灵感模式仍显示已完成项目

**可能原因**:
1. **前端未重启**: 代码已更新但浏览器未刷新
   - 解决：强制刷新（Ctrl+Shift+R 或 Cmd+Shift+R）
   - 或清除浏览器缓存

2. **localStorage 污染**: 旧缓存仍然存在
   - 检查：
     ```javascript
     localStorage.getItem('inspiration_project_id')
     ```
   - 手动清理：
     ```javascript
     localStorage.removeItem('inspiration_project_id')
     ```

3. **后端项目状态错误**: 项目状态不是 'blueprint_ready'
   - 检查数据库：
     ```sql
     SELECT id, title, status FROM novel_projects WHERE id = '项目ID';
     ```
   - 如果状态错误，手动修正：
     ```sql
     UPDATE novel_projects SET status = 'blueprint_ready' WHERE id = '项目ID';
     ```

**验证命令**:
```bash
# 查看前端控制台日志
# 应该看到：
# "项目状态为 blueprint_ready，已完成灵感阶段，清除缓存"
```

---

### 问题 2: 点击「生成蓝图」后 localStorage 未清理

**排查步骤**:

1. **检查 handleBlueprintGenerated 是否触发**:
   ```javascript
   // 在 InspirationMode.vue 的 handleBlueprintGenerated 开头添加断点
   console.log('handleBlueprintGenerated 触发', response)
   ```

2. **检查 localStorage 操作**:
   ```javascript
   // 在控制台执行
   const key = 'inspiration_project_id'
   console.log('清理前:', localStorage.getItem(key))
   localStorage.removeItem(key)
   console.log('清理后:', localStorage.getItem(key))  // 应该是 null
   ```

3. **检查是否有异常阻止执行**:
   - 查看浏览器控制台是否有 JavaScript 错误
   - 检查 `globalAlert.showConfirm` 是否正常工作

**如果仍未清理**:
```javascript
// 在 BlueprintDisplay 组件的 @confirm 事件中添加额外清理
const handleConfirmBlueprint = async () => {
  // ... 现有逻辑

  // 额外保障：再次清理
  const key = 'inspiration_project_id'
  if (localStorage.getItem(key)) {
    console.warn('发现未清理的缓存，立即清理')
    localStorage.removeItem(key)
  }
}
```

---

### 问题 3: 状态检查未生效，已完成项目仍被恢复

**排查步骤**:

1. **确认 restoreConversation 代码已更新**:
   ```bash
   # 查看 InspirationMode.vue 第232行附近
   # 应该有：if (project.status !== 'draft')
   ```

2. **检查 project.status 的值**:
   ```javascript
   // 在 restoreConversation 中添加日志
   console.log('项目状态:', project.status, '类型:', typeof project.status)
   ```

3. **检查数据库中的状态值**:
   ```sql
   SELECT id, title, status FROM novel_projects WHERE id = '项目ID';
   ```

4. **检查 API 返回的数据**:
   ```javascript
   // 在浏览器控制台
   fetch('/api/novels/项目ID', {
     headers: { 'Authorization': 'Bearer ' + localStorage.getItem('token') }
   })
     .then(res => res.json())
     .then(data => console.log('项目数据:', data))
   ```

**可能的问题**:
- 数据库中 status 字段为 NULL 或空字符串
- 前端 Schema 解析错误
- 后端未正确更新项目状态

**修复**:
```sql
-- 统一修正所有已生成蓝图的项目状态
UPDATE novel_projects np
SET status = 'blueprint_ready'
WHERE EXISTS (
  SELECT 1 FROM novel_blueprints nb
  WHERE nb.project_id = np.id
)
AND (status IS NULL OR status = '' OR status = 'draft');
```

---

### 问题 4: findUnfinishedProject 找不到 draft 项目

**排查步骤**:

1. **检查是否有 draft 项目**:
   ```sql
   SELECT id, title, status, created_at
   FROM novel_projects
   WHERE user_id = '用户ID' AND status = 'draft'
   ORDER BY updated_at DESC;
   ```

2. **检查前端项目列表**:
   ```javascript
   // 在控制台
   novelStore.loadProjects().then(() => {
     console.log('所有项目:', novelStore.projects)
     console.log('draft项目:', novelStore.projects.filter(p => p.status === 'draft'))
   })
   ```

3. **检查 API 响应**:
   ```bash
   curl -H "Authorization: Bearer YOUR_TOKEN" \
     http://localhost:8000/api/novels
   ```

**可能的问题**:
- 用户确实没有未完成的项目
- API 未返回 status 字段
- 前端过滤逻辑有误

---

## 总结

### 修复的文件（1个）

**前端**:
1. `frontend/src/views/InspirationMode.vue` - 添加状态检查、清理localStorage、优化恢复逻辑

### 核心改进

1. **localStorage 清理时机正确**: 蓝图生成完成后立即清理，防止缓存污染
2. **状态检查严格**: 只恢复 `draft` 状态的项目，拒绝已完成的项目
3. **用户引导友好**: 误访问已完成项目时，询问是否跳转到详情页
4. **防御性编程**: 双重清理（生成完成 + 保存成功），确保缓存不泄漏
5. **日志记录完善**: 关键节点都有日志，方便排查问题

### 技术要点

- **状态机驱动**: 灵感模式只处理 `draft` 状态，严格执行工作流分离
- **缓存生命周期管理**: localStorage 缓存与项目状态同步，避免过期数据
- **用户体验优化**: 错误场景下提供明确引导，而非静默失败
- **防御性编程**: 多个清理点，即使某个环节失败，其他环节也能兜底

### 预期效果

- ✅ 灵感模式不会自动打开已完成的项目
- ✅ localStorage 缓存及时清理，不会污染后续会话
- ✅ 用户误访问已完成项目时，得到友好提示并引导到正确页面
- ✅ 工作流分离严格执行：draft 项目在灵感模式，已完成项目在详情页

---

## 相关文档

- [工作流分离修复](./workflow-separation-fix.md) - 蓝图与章节大纲分离
- [章节数显示修复](./chapter-count-display-fix.md) - 章节数提取问题（已被 workflow-separation-fix 替代）
- [灵感模式恢复修复](./inspiration-recovery-fix.md) - 对话恢复机制（如果存在）
- [工作流程文档](./novel_workflow.md) - 完整的小说生成流程

---

## 下一步优化建议

### 1. 添加状态迁移日志

在项目状态变更时记录日志：

```python
# 在 backend/app/services/novel_service.py
async def update_project_status(self, project_id: str, new_status: str):
    project = await self.get_project(project_id)
    old_status = project.status
    project.status = new_status
    await self.session.commit()

    logger.info(
        "项目 %s 状态变更：%s → %s",
        project_id,
        old_status,
        new_status
    )
```

### 2. 前端添加状态可视化

在项目列表中显示状态徽章：

```vue
<template>
  <div class="project-card">
    <span class="status-badge" :class="statusClass(project.status)">
      {{ statusLabel(project.status) }}
    </span>
    <h3>{{ project.title }}</h3>
  </div>
</template>

<script setup>
const statusLabel = (status) => {
  const labels = {
    'draft': '灵感中',
    'blueprint_ready': '蓝图完成',
    'chapter_outlines_ready': '大纲完成',
    'writing': '写作中'
  }
  return labels[status] || '未知'
}
</script>
```

### 3. 定期清理过期缓存

添加清理脚本，在应用启动时执行：

```javascript
// 在 frontend/src/main.ts 或 App.vue 的 onMounted
const cleanExpiredCache = async () => {
  const key = 'inspiration_project_id'
  const cachedId = localStorage.getItem(key)

  if (cachedId) {
    try {
      const response = await fetch(`/api/novels/${cachedId}`)
      const project = await response.json()

      if (project.status !== 'draft') {
        console.log('清理过期缓存:', cachedId)
        localStorage.removeItem(key)
      }
    } catch {
      console.log('清理无效缓存:', cachedId)
      localStorage.removeItem(key)
    }
  }
}
```

### 4. 添加状态迁移锁

防止并发请求导致的状态冲突：

```python
# 使用数据库锁
from sqlalchemy import select
from sqlalchemy.orm import selectinload

async def transition_status(self, project_id: str, expected_status: str, new_status: str):
    stmt = (
        select(NovelProject)
        .where(NovelProject.id == project_id)
        .with_for_update()  # 行锁
    )
    result = await self.session.execute(stmt)
    project = result.scalar_one_or_none()

    if not project:
        raise ValueError("项目不存在")

    if project.status != expected_status:
        raise ValueError(f"项目状态不正确，期望 {expected_status}，实际 {project.status}")

    project.status = new_status
    await self.session.commit()
```
