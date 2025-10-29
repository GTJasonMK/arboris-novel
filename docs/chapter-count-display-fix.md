# 章节数显示矛盾问题修复

## 问题描述

**用户报告**: 完成灵感模式后点击"生成蓝图"，显示的信息矛盾：
- 一处可能提到 "200章——这将是宏大的史诗级叙事"（在灵感对话阶段）
- 另一处显示 "您的小说计划 0 章"（在蓝图生成后）

**严重程度**: 🔴 高 - 违反了工作流设计，导致用户困惑

**相关截图和文件**: `E:\code\arboris-novel\拯救小说家.html` (HTML文件第8642行显示"小说计划 0 章")

---

## 根本原因分析

### 问题核心

LLM 在蓝图生成阶段未正确遵守提示词指令，返回的蓝图数据中 `total_chapters` 字段为 0 或 null。

### 数据流分析

1. **灵感对话阶段**:
   - LLM 可能在对话中提到 "200章规模的史诗级小说"
   - 但这只是对话内容，不是结构化数据

2. **蓝图生成阶段**:
   - 提示词要求: `chapter_outline` 设为空数组 `[]`
   - 提示词要求: 估算 `total_chapters` 并设置
   - **实际问题**: LLM 返回 `total_chapters: 0` 或 `total_chapters: null`

3. **后端处理**:
   ```python
   total_chapters = blueprint.total_chapters or 0  # 得到 0
   ai_message = f"您的小说计划 {total_chapters} 章"  # 显示 "0 章"
   ```

### 为什么LLM返回0

**可能原因**:
1. 提示词不够明确，没有强调 `total_chapters` 是必填字段
2. 没有提供章节数的参考范围
3. 没有明确禁止0值
4. 后端没有数据校验，让错误数据流向前端

---

## 完整修复方案

### 修复 1: 加强提示词约束 ⭐ 核心修复

**文件**: `backend/prompts/screenwriting.md`

**修改前**:
```markdown
1. **估算总章节数**：根据故事复杂度和用户讨论的内容，估算合理的总章节数，设置 `total_chapters` 字段
```

**修改后**:
```markdown
1. **估算总章节数（必填）**：
   - 根据故事复杂度、情节密度、人物数量、世界观复杂度估算合理的总章节数
   - 设置 `total_chapters` 字段，必须是一个大于0的整数
   - 参考标准：
     * 简单短篇：10-30章
     * 中等长篇：30-80章
     * 长篇史诗：80-200章
     * 超长篇：200章以上
   - **重要**：`total_chapters` 不能为0、null或空值
```

**改进点**:
1. ✅ 明确标注"必填"
2. ✅ 提供具体的参考范围
3. ✅ 强调"必须是大于0的整数"
4. ✅ 明确禁止0、null、空值

---

### 修复 2: 后端数据校验

**文件**: `backend/app/api/routers/novels.py`

**修改位置**: `generate_blueprint` 函数的第258-285行

**修改前**:
```python
blueprint = Blueprint(**blueprint_data)

# 新流程：蓝图生成阶段不包含章节大纲，统一设置为 blueprint_ready
project.status = "blueprint_ready"

total_chapters = blueprint.total_chapters or 0  # ❌ 允许0值
needs_part_outlines = blueprint.needs_part_outlines

logger.info(
    "项目 %s 蓝图生成完成，总章节数=%d，需要部分大纲=%s",
    project_id,
    total_chapters,
    needs_part_outlines,
)
```

**修改后**:
```python
blueprint = Blueprint(**blueprint_data)

# 数据校验：total_chapters 必须大于0
total_chapters = blueprint.total_chapters or 0
if total_chapters <= 0:
    logger.warning(
        "项目 %s 蓝图生成失败：total_chapters=%s 无效，LLM未正确估算章节数",
        project_id,
        total_chapters,
    )
    raise HTTPException(
        status_code=500,
        detail=(
            "蓝图生成失败：AI未能正确估算小说章节数。"
            "这可能是因为灵感对话内容不够充分。"
            "请返回灵感模式，提供更多关于故事规模、情节复杂度的信息后重试。"
        ),
    )

# 新流程：蓝图生成阶段不包含章节大纲，统一设置为 blueprint_ready
project.status = "blueprint_ready"

needs_part_outlines = blueprint.needs_part_outlines

logger.info(
    "项目 %s 蓝图生成完成，总章节数=%d，需要部分大纲=%s",
    project_id,
    total_chapters,
    needs_part_outlines,
)
```

**改进点**:
1. ✅ 在使用数据前进行校验
2. ✅ 如果 `total_chapters <= 0`，立即抛出 HTTP 500 错误
3. ✅ 提供用户友好的错误提示
4. ✅ 记录警告日志，方便调试
5. ✅ 引导用户返回灵感模式补充信息

---

## 工作流程图

### 修复前的错误流程

```
灵感对话阶段
  ↓
AI: "建议规模200章的史诗级小说"（对话内容）
  ↓
生成蓝图阶段
  ↓
LLM 返回: { total_chapters: 0, chapter_outline: [] }  ❌ 错误数据
  ↓
后端接受: total_chapters = 0  ❌ 无校验
  ↓
ai_message = "您的小说计划 0 章"  ❌ 显示错误
  ↓
前端显示: "小说计划是0章"  ❌ 用户困惑
```

### 修复后的正确流程

```
灵感对话阶段
  ↓
AI: "建议规模200章的史诗级小说"（对话内容）
  ↓
生成蓝图阶段
  ↓
【强化提示词】
  ├─ 必填标注
  ├─ 参考范围（10-200+章）
  ├─ 禁止0值
  └─ 强调必须>0
  ↓
LLM 返回: { total_chapters: 200, chapter_outline: [] }  ✅ 正确数据
  ↓
【后端校验】
  ├─ 检查 total_chapters <= 0
  ├─ 如果无效 → HTTP 500 + 友好提示
  └─ 如果有效 → 继续处理
  ↓
total_chapters = 200  ✅ 有效数据
  ↓
ai_message = "您的小说计划 200 章，接下来请在详情页..."  ✅ 正确提示
  ↓
前端显示:
  ├─ "太棒了！基础蓝图已生成完成。"
  ├─ "您的小说计划 200 章"  ✅ 准确信息
  └─ "接下来请在详情页点击「生成部分大纲」按钮..."  ✅ 正确引导
```

---

## 测试验证

### 场景 1: 正常生成（短篇）

**步骤**:
1. 完成灵感对话，提到"简单的短篇故事"
2. 点击"生成蓝图"

**预期结果**:
```json
{
  "total_chapters": 25,
  "needs_part_outlines": false,
  "chapter_outline": []
}
```

**前端显示**:
> 太棒了！基础蓝图已生成完成。您的小说计划 25 章，接下来请在详情页点击「生成章节大纲」按钮来规划具体章节。

---

### 场景 2: 正常生成（长篇）

**步骤**:
1. 完成灵感对话，提到"宏大的史诗级小说，涉及多个势力、复杂世界观"
2. 点击"生成蓝图"

**预期结果**:
```json
{
  "total_chapters": 200,
  "needs_part_outlines": true,
  "chapters_per_part": 25,
  "chapter_outline": []
}
```

**前端显示**:
> 太棒了！基础蓝图已生成完成。您的小说计划 200 章，接下来请在详情页点击「生成部分大纲」按钮来规划整体结构，然后再生成详细的章节大纲。

---

### 场景 3: LLM未遵守指令（错误处理）

**触发条件**:
- LLM 仍然返回 `total_chapters: 0`（虽然概率大幅降低）

**后端行为**:
```python
# 检测到 total_chapters <= 0
raise HTTPException(
    status_code=500,
    detail="蓝图生成失败：AI未能正确估算小说章节数。这可能是因为灵感对话内容不够充分。请返回灵感模式，提供更多关于故事规模、情节复杂度的信息后重试。"
)
```

**前端显示**:
- 错误弹窗显示上述错误信息
- 不会显示 "小说计划 0 章"（因为请求已被拦截）
- 用户可以返回灵感模式补充信息

---

### 场景 4: 验证提示词改进效果

**测试方法**:
1. 使用相同的灵感对话历史
2. 调用蓝图生成API
3. 查看返回的 `total_chapters` 值

**验证命令**:
```bash
# 查看后端日志
tail -f backend/storage/debug.log | grep "蓝图生成完成"

# 预期输出（成功）：
# 项目 xxx 蓝图生成完成，总章节数=200，需要部分大纲=True

# 预期输出（失败）：
# 项目 xxx 蓝图生成失败：total_chapters=0 无效，LLM未正确估算章节数
```

---

## 向后兼容性

### ⚠️ 不兼容变更

**影响**:
- 如果 LLM 返回 `total_chapters: 0`，现在会直接报错，而不是显示 "0 章"
- 这是**有意的破坏性变更**，因为0章本身就是无效数据

### 数据迁移

**不需要**数据库迁移，原因：
- 只修改了提示词和API逻辑
- 不涉及数据库schema变更
- 旧的蓝图数据不受影响（已有项目的 `total_chapters` 已经确定）

### 旧数据检查

如果怀疑数据库中存在 `total_chapters = 0` 的蓝图：

```sql
-- 查找可能的问题数据
SELECT
    np.id,
    np.title,
    np.status,
    nb.total_chapters
FROM novel_projects np
JOIN novel_blueprints nb ON np.id = nb.project_id
WHERE nb.total_chapters IS NULL OR nb.total_chapters <= 0;
```

**数据修复**（如果发现问题数据）:
```sql
-- 手动设置合理的章节数（示例：根据实际情况调整）
UPDATE novel_blueprints
SET total_chapters = 50  -- 或其他合理值
WHERE total_chapters IS NULL OR total_chapters <= 0;
```

---

## 错误排查

### 问题 1: 仍然显示 "0 章"

**可能原因**:
1. **后端未重启**: 代码已更新但服务未重启
   ```bash
   # 重启后端服务
   cd backend
   pkill -f "uvicorn app.main:app"
   uvicorn app.main:app --reload
   ```

2. **提示词未刷新**: Prompt 缓存未更新
   - 检查 `app/main.py` 的 `lifespan` 钩子是否正确加载提示词
   - 重启应该自动刷新，如果没有，检查日志

3. **旧项目数据**: 测试的项目已经生成过蓝图
   - 创建新项目测试
   - 或者删除旧项目的蓝图数据重新生成

**验证命令**:
```bash
# 查看后端日志，确认校验逻辑执行
tail -f backend/storage/debug.log | grep "蓝图生成"
```

---

### 问题 2: 报错 "AI未能正确估算小说章节数"

**这是正常行为**，说明校验生效了。

**解决方法**:
1. 返回灵感模式
2. 在对话中补充更多信息：
   - 故事的规模（大概多少情节点）
   - 计划的篇幅（短篇/中篇/长篇）
   - 世界观的复杂度
   - 主要角色数量
3. 重新生成蓝图

**示例对话**:
```
用户: "我希望这是一个包含多条故事线的长篇小说，涉及至少5个主要角色，横跨3个不同的势力，时间跨度2年。"
```

这样的信息能帮助AI更准确地估算章节数。

---

### 问题 3: 提示词改进后LLM仍返回不合理的章节数

**不合理的定义**:
- 简单故事返回 500 章（过高）
- 复杂史诗返回 5 章（过低）

**解决方案**:
1. **进一步优化提示词**: 添加更多约束
2. **添加上下限校验**:
   ```python
   # 在 backend/app/api/routers/novels.py
   MIN_CHAPTERS = 5
   MAX_CHAPTERS = 1000

   if not (MIN_CHAPTERS <= total_chapters <= MAX_CHAPTERS):
       raise HTTPException(
           status_code=500,
           detail=f"章节数 {total_chapters} 不在合理范围({MIN_CHAPTERS}-{MAX_CHAPTERS})内"
       )
   ```

---

## 总结

### 修复的文件（2个）

**后端**:
1. `backend/prompts/screenwriting.md` - 加强提示词约束
2. `backend/app/api/routers/novels.py` - 添加数据校验

### 核心改进

1. **提示词层面**: 明确必填、提供范围、禁止无效值
2. **后端层面**: 校验数据，拦截错误，提供友好提示
3. **用户体验**: 不再显示 "0 章"，错误情况下有明确引导

### 技术要点

- **防御性编程**: 不信任LLM的输出，必须校验
- **用户引导**: 错误提示不只说"失败"，还要说"为什么"和"怎么办"
- **提示词工程**: 使用"必填"、"禁止"、"参考范围"等明确约束
- **日志记录**: 关键校验点都有日志，方便追踪问题

### 预期效果

- ✅ 不再出现 "小说计划 0 章"
- ✅ LLM 正确估算章节数的概率大幅提升
- ✅ 即使 LLM 返回无效数据，后端也会拦截并提示
- ✅ 用户能得到明确的错误反馈和解决方案

---

## 相关文档

- [工作流程文档](./novel_workflow.md) - 完整的小说生成流程
- [蓝图显示错误修复](./blueprint-display-bug-fix.md) - 相关的前端逻辑修复
- [灵感模式恢复修复](./inspiration-recovery-fix.md) - 对话恢复机制修复
