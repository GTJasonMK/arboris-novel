# 工作流分离优化 - 正确实现蓝图与章节大纲分离

## 问题重新定位

**用户反馈**:
1. ❌ 章节数应该由用户在灵感对话中决定，而不是让LLM"估算"
2. ❌ 当前蓝图生成会直接生成章节大纲，违反了工作流分离设计
3. ❌ 灵感收集阶段的"预期篇幅"信息没有被正确使用

**严重程度**: 🔴 高 - 违反核心设计原则，导致工作流混乱

---

## 核心设计原则

### 正确的工作流

```
灵感对话（收集章节数） → 蓝图生成（基础设定，章节数=用户输入） →
    章节大纲生成（单独步骤） → 内容生成
```

### 错误的旧流程

```
灵感对话（可能收集章节数） → 蓝图生成（LLM估算章节数 + 生成章节大纲） ❌
```

---

## 根本原因分析

### 问题 1: 章节数来源错误

**设计意图**: 用户在灵感对话中明确说"我想写200章"，蓝图应使用这个数字

**实际情况**:
- `concept.md` 第27行有 `预期篇幅 (Chapter Count)` 收集项
- 但 `screenwriting.md` 要求LLM"估算"章节数
- 导致用户输入被忽略，LLM自行决定

**错误示例**:
```
用户对话: "我计划写200章的史诗级小说"
LLM蓝图:  { "total_chapters": 0 }  ❌ 完全忽略用户输入
```

---

### 问题 2: 章节大纲不分离

**设计意图**: 蓝图生成阶段只包含基础设定，章节大纲在后续单独生成

**实际情况**:
- 虽然提示词要求 `chapter_outline: []`
- 但LLM可能不遵守，直接生成章节大纲
- 后端没有强制校验

**错误示例**:
```json
{
  "total_chapters": 200,
  "chapter_outline": [
    {"chapter_number": 1, "title": "序章", "summary": "..."},
    {"chapter_number": 2, "title": "觉醒", "summary": "..."},
    // ... LLM直接生成了200个章节大纲 ❌
  ]
}
```

---

## 完整修复方案

### 修复 1: 提示词 - 从对话中提取章节数 ⭐ 核心修复

**文件**: `backend/prompts/screenwriting.md`

**修改位置**: 第97-139行

**修改前**:
```markdown
1. **估算总章节数（必填）**：
   - 根据故事复杂度、情节密度、人物数量、世界观复杂度估算合理的总章节数
   - 设置 `total_chapters` 字段，必须是一个大于0的整数
```

**修改后**:
```markdown
### 步骤1: 从对话中提取用户指定的章节数（优先级最高）

**重要**：在灵感对话中，用户已经被询问过"预期篇幅 (Chapter Count)"。你必须：

1. **仔细检查对话历史**，寻找用户关于章节数的明确表述，例如：
   - "我想写200章"
   - "计划50章左右"
   - "大概100章吧"
   - "短篇，30章"

2. **提取数字**：
   - 如果用户说了"200章" → `total_chapters: 200`
   - 如果用户说了"50章左右" → `total_chapters: 50`
   - 如果用户说了"100多章" → `total_chapters: 100`

3. **如果用户未明确指定章节数**（对话中完全没有提到）：
   - 根据故事复杂度给出合理的默认值
   - 参考标准：
     * 简单短篇故事 → 30章
     * 中等复杂度 → 80章
     * 复杂史诗 → 150章
   - **注意**：这只是没有用户输入时的补救措施，优先使用用户明确指定的数字
```

**核心改进**:
1. ✅ 明确要求从对话中提取章节数
2. ✅ 提供多种用户表述的识别方式
3. ✅ 用户输入优先于LLM估算
4. ✅ 只有在用户未明确指定时才使用默认值

---

### 修复 2: 后端强制清空章节大纲

**文件**: `backend/app/api/routers/novels.py`

**修改位置**: 第258-266行

**新增代码**:
```python
# 强制工作流分离：蓝图生成阶段不包含章节大纲
# 即使LLM违反指令生成了章节大纲，也要强制清空
if blueprint.chapter_outline:
    logger.warning(
        "项目 %s 蓝图生成时包含了 %d 个章节大纲，违反工作流设计，已强制清空",
        project_id,
        len(blueprint.chapter_outline),
    )
    blueprint.chapter_outline = []
```

**核心改进**:
1. ✅ 防御性编程：不信任LLM的输出
2. ✅ 即使LLM违反指令，后端也会纠正
3. ✅ 记录警告日志，方便追踪问题
4. ✅ 确保工作流分离的强制执行

---

### 修复 3: 章节数校验错误消息优化

**文件**: `backend/app/api/routers/novels.py`

**修改位置**: 第268-283行

**修改前**:
```python
raise HTTPException(
    status_code=500,
    detail=(
        "蓝图生成失败：AI未能正确估算小说章节数。"
        "这可能是因为灵感对话内容不够充分。"
        "请返回灵感模式，提供更多关于故事规模、情节复杂度的信息后重试。"
    ),
)
```

**修改后**:
```python
raise HTTPException(
    status_code=500,
    detail=(
        "蓝图生成失败：未能从灵感对话中提取章节数信息。"
        "请返回灵感模式，在对话中明确说明您计划写多少章（例如：'我想写200章'），然后重试。"
        "如果您已经在对话中提到了章节数但仍出现此错误，请联系技术支持。"
    ),
)
```

**核心改进**:
1. ✅ 错误消息明确指出问题：未提取到章节数，而非"估算失败"
2. ✅ 提供具体示例："我想写200章"
3. ✅ 引导用户返回对话补充信息
4. ✅ 提供技术支持联系方式（边界情况处理）

---

## 工作流程图

### 修复后的正确流程

```
阶段1: 灵感对话
  ↓
AI: "您计划写多少章呢？"
用户: "我想写200章的史诗级小说"  ← 明确输入
  ↓
对话历史: [
  {"role": "user", "content": "我想写200章的史诗级小说"}
]
  ↓
阶段2: 蓝图生成
  ↓
【提示词指令】
  ├─ 步骤1: 从对话历史中提取章节数 → 200
  ├─ 步骤2: 判断分阶段生成 → needs_part_outlines: true
  └─ 步骤3: chapter_outline 设为空数组
  ↓
LLM返回: {
  "total_chapters": 200,  ✅ 来自用户输入
  "needs_part_outlines": true,
  "chapter_outline": []  ✅ 空数组
}
  ↓
【后端校验】
  ├─ 检查 chapter_outline → 如果非空，强制清空
  ├─ 检查 total_chapters > 0 → 通过
  └─ 保存到数据库
  ↓
项目状态: draft → blueprint_ready
  ↓
阶段3: 章节大纲生成（后续步骤）
  ├─ 短篇（≤50章）→ 一次性生成所有章节大纲
  └─ 长篇（>50章）→ 先生成部分大纲 → 分批生成章节大纲
```

---

## 数据流对比

### 旧流程（错误）

| 阶段 | 数据来源 | total_chapters | chapter_outline | 问题 |
|------|---------|----------------|-----------------|------|
| 灵感对话 | 用户输入 | 对话中提到"200章" | - | 用户明确输入 |
| 蓝图生成 | LLM估算 | 0（估算失败） | [1-200章大纲] | ❌ 忽略用户输入 + 违反分离原则 |

### 新流程（正确）

| 阶段 | 数据来源 | total_chapters | chapter_outline | 状态 |
|------|---------|----------------|-----------------|------|
| 灵感对话 | 用户输入 | 对话中提到"200章" | - | 用户明确输入 ✅ |
| 蓝图生成 | 从对话提取 | 200（提取自对话） | [] | ✅ 使用用户输入 + 强制空数组 |
| 章节大纲生成 | 单独步骤 | 200（已确定） | [1-200章大纲] | ✅ 工作流分离 |

---

## 测试验证

### 场景 1: 用户明确指定章节数（核心场景）

**步骤**:
1. 进入灵感模式
2. 对话中明确说："我想写200章的史诗级小说"
3. 完成对话后点击"生成蓝图"

**预期结果**:
```json
{
  "total_chapters": 200,  // ✅ 来自用户输入
  "needs_part_outlines": true,
  "chapter_outline": []  // ✅ 空数组
}
```

**前端显示**:
> 太棒了！基础蓝图已生成完成。您的小说计划 200 章，接下来请在详情页点击「生成部分大纲」按钮来规划整体结构，然后再生成详细的章节大纲。

**验证点**:
- ✅ total_chapters = 200（准确）
- ✅ chapter_outline 为空（工作流分离）
- ✅ 提示引导用户进入下一步

---

### 场景 2: 用户使用模糊表述

**步骤**:
1. 对话中说："大概100章左右吧"
2. 生成蓝图

**预期结果**:
```json
{
  "total_chapters": 100,  // ✅ 提取"100"
  "needs_part_outlines": true,
  "chapter_outline": []
}
```

---

### 场景 3: 用户未明确指定（降级处理）

**步骤**:
1. 对话中完全没有提到章节数
2. 生成蓝图

**预期结果**:
```json
{
  "total_chapters": 80,  // ✅ 默认值（基于故事复杂度）
  "needs_part_outlines": true,
  "chapter_outline": []
}
```

**注意**:
- 默认值是补救措施，不应该成为常态
- 如果频繁出现，说明灵感对话环节没有正确询问章节数

---

### 场景 4: LLM违反指令生成章节大纲（防御性测试）

**触发条件**:
- LLM忽略提示词，返回了 `chapter_outline: [...]`

**后端行为**:
```python
# 检测到违规
if blueprint.chapter_outline:
    logger.warning("项目 xxx 蓝图生成时包含了 200 个章节大纲，违反工作流设计，已强制清空")
    blueprint.chapter_outline = []
```

**结果**:
- ✅ 后端强制清空
- ✅ 记录警告日志
- ✅ 数据库中 chapter_outlines 表为空
- ✅ 工作流分离得以维持

---

### 场景 5: 用户说了章节数但LLM未提取（边界情况）

**触发条件**:
- 用户对话："我想写200章"
- LLM返回：`total_chapters: 0`

**后端行为**:
```python
# 检测到 total_chapters <= 0
raise HTTPException(
    status_code=500,
    detail="蓝图生成失败：未能从灵感对话中提取章节数信息。请返回灵感模式，在对话中明确说明您计划写多少章（例如：'我想写200章'），然后重试。"
)
```

**前端显示**:
- 错误弹窗显示上述消息
- 引导用户返回灵感模式重新明确

**分析**:
- 这种情况说明LLM的提取能力有问题
- 应该记录日志，分析是哪些表述方式导致提取失败
- 可能需要进一步优化提示词

---

## 向后兼容性

### ⚠️ 不兼容变更

**影响**:
1. **旧的蓝图生成逻辑改变**:
   - 之前：LLM估算章节数
   - 现在：从对话中提取章节数

2. **强制清空章节大纲**:
   - 之前：可能包含章节大纲
   - 现在：强制为空数组

### 数据迁移

**不需要**数据库迁移，原因：
- 只修改了提示词和API逻辑
- 不涉及数据库schema变更
- 旧项目的蓝图数据不受影响

### 旧数据检查

检查是否有项目在蓝图生成阶段就有章节大纲：

```sql
-- 查找可能的问题数据（蓝图已生成但状态仍是 blueprint_ready，却有章节大纲）
SELECT
    np.id,
    np.title,
    np.status,
    COUNT(co.chapter_number) as outline_count
FROM novel_projects np
LEFT JOIN chapter_outlines co ON np.id = co.project_id
WHERE np.status = 'blueprint_ready'
GROUP BY np.id, np.title, np.status
HAVING outline_count > 0;
```

**如果发现问题数据**:
```sql
-- 这些项目可能是在旧流程中生成的，章节大纲应该保留
-- 应该将状态更新为 chapter_outlines_ready
UPDATE novel_projects
SET status = 'chapter_outlines_ready'
WHERE id IN (
    SELECT DISTINCT np.id
    FROM novel_projects np
    JOIN chapter_outlines co ON np.id = co.project_id
    WHERE np.status = 'blueprint_ready'
);
```

---

## 错误排查

### 问题 1: 用户说了章节数但蓝图显示0

**排查步骤**:

1. **检查后端日志**:
   ```bash
   tail -f backend/storage/debug.log | grep "蓝图生成"
   ```

   预期看到：
   ```
   项目 xxx 蓝图生成失败：total_chapters=0 无效，LLM未从对话中提取章节数
   ```

2. **检查对话历史**:
   ```bash
   # 通过API查看对话历史
   curl -H "Authorization: Bearer {token}" \
     http://localhost:8000/api/novels/{project_id}
   ```

   确认用户是否确实在对话中提到了章节数

3. **分析LLM提取失败原因**:
   - 用户表述太模糊："可能写个几十章吧"
   - 章节数信息被其他内容覆盖
   - 提示词需要进一步优化

**解决方案**:
- 优化 `concept.md`，在询问章节数时更明确
- 优化 `screenwriting.md`，提供更多用户表述的识别示例
- 考虑在灵感对话最后增加一个确认环节："您计划写多少章？"

---

### 问题 2: 蓝图生成后仍有章节大纲

**排查步骤**:

1. **检查后端日志**:
   ```bash
   tail -f backend/storage/debug.log | grep "违反工作流设计"
   ```

   应该看到：
   ```
   项目 xxx 蓝图生成时包含了 200 个章节大纲，违反工作流设计，已强制清空
   ```

2. **检查数据库**:
   ```sql
   SELECT COUNT(*) FROM chapter_outlines WHERE project_id = '{project_id}';
   ```

   应该返回 0

**如果仍有章节大纲**:
- 检查后端是否重启（代码更新后必须重启）
- 检查 `novel_service.py` 的 `replace_blueprint` 方法是否正确执行
- 可能是旧数据，手动清理：
  ```sql
  DELETE FROM chapter_outlines WHERE project_id = '{project_id}';
  ```

---

### 问题 3: 前端跳过了章节大纲生成步骤

**症状**:
- 蓝图生成后直接跳到内容生成界面
- 没有"生成章节大纲"或"生成部分大纲"的按钮

**排查**:

1. **检查前端组件**:
   - `frontend/src/components/novel-detail/ChapterOutlineSection.vue`
   - 确认条件渲染逻辑：
     ```vue
     <ChapterOutlineGenerator v-if="showChapterOutlineGenerator" />
     ```

2. **检查显示条件**:
   ```javascript
   const showChapterOutlineGenerator = computed(() =>
     !needsPartOutlines.value && props.outline.length === 0
   )
   ```

3. **检查API返回数据**:
   ```javascript
   console.log('blueprint:', novelStore.currentProject?.blueprint)
   console.log('chapter_outline:', novelStore.currentProject?.blueprint?.chapter_outline)
   ```

---

## 总结

### 修复的文件（2个）

**后端**:
1. `backend/prompts/screenwriting.md` - 改为从对话中提取章节数
2. `backend/app/api/routers/novels.py` - 强制清空章节大纲 + 优化错误消息

### 核心改进

1. **章节数来源正确**: 用户输入 > 默认值（不再让LLM估算）
2. **工作流强制分离**: 后端强制清空章节大纲
3. **错误消息精确**: 明确告诉用户问题和解决方案
4. **防御性编程**: 不信任LLM输出，后端强制纠正

### 技术要点

- **信息提取 vs 信息生成**: LLM应该提取用户输入，而非自行决定
- **用户主导**: 章节数这种核心参数必须由用户决定
- **工作流分离**: 蓝图、章节大纲、内容生成是三个独立步骤
- **防御性编程**: 即使提示词失效，后端也能确保正确性

### 预期效果

- ✅ 用户输入的章节数被正确使用
- ✅ 蓝图生成阶段不包含章节大纲
- ✅ 工作流分离严格执行
- ✅ 错误情况下有明确引导

---

## 下一步优化建议

### 1. 灵感对话优化

在 `concept.md` 中增加章节数询问的权重，确保每次对话都明确收集：

```markdown
- [ ] **预期篇幅 (Chapter Count) ⭐ 必须明确**：故事的大致章节数量，必须从用户获得明确数字。
```

### 2. 章节数验证范围

添加合理性检查：

```python
# 在 backend/app/api/routers/novels.py
MIN_CHAPTERS = 5
MAX_CHAPTERS = 1000

if not (MIN_CHAPTERS <= total_chapters <= MAX_CHAPTERS):
    raise HTTPException(
        status_code=500,
        detail=f"章节数 {total_chapters} 超出合理范围({MIN_CHAPTERS}-{MAX_CHAPTERS}章)"
    )
```

### 3. 对话确认环节

在灵感对话最后增加确认：

```markdown
**Phase II: Blueprint Generation**
1.  **Transition:**
    *   **AI Says:** "完美！让我确认一下：您计划写 [提取的章节数] 章，对吗？如果不对，请告诉我正确的章节数。"
```

---

## 相关文档

- [工作流程文档](./novel_workflow.md) - 完整的小说生成流程
- [章节数显示修复](./chapter-count-display-fix.md) - 之前的修复（现已被本次优化替代）
- [灵感模式恢复修复](./inspiration-recovery-fix.md) - 对话恢复机制
