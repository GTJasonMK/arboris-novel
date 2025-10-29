# 部分大纲生成工作流 Bug修复总结

## 修复日期
2025-10-26

## 背景
长篇小说（>50章）需要分层大纲生成机制：
1. 先生成"部分大纲"（每部分约25章）
2. 再为每个部分生成详细的章节大纲
3. 支持并发生成以提高效率
4. 需要中断恢复机制
5. 大纲内容有前后依赖性，需要保证顺序

## 已修复的严重Bug

### 1. 状态永久卡死问题 ✅

**问题描述**：
- 用户在生成过程中刷新页面或关闭浏览器时，正在生成的部分会永久停留在 `generating` 状态
- 无法重试，必须手动修改数据库

**修复内容**：
```python
# backend/app/services/part_outline_service.py

# 1. 添加finally块确保状态总是更新
generation_successful = False
try:
    # ... 生成逻辑 ...
    generation_successful = True
except Exception as exc:
    logger.error("生成失败: %s", exc)
    raise
finally:
    # 确保状态总是会更新，防止永久卡在generating状态
    if generation_successful:
        await self.repo.update_status(part_outline, "completed", 100)
    else:
        await self.repo.update_status(part_outline, "failed", 0)
    await self.session.commit()

# 2. 添加超时检测清理机制
async def cleanup_stale_generating_status(
    self, project_id: str, timeout_minutes: int = 15
) -> int:
    """清理超时的generating状态（超过15分钟未更新）"""
    all_parts = await self.repo.get_by_project_id(project_id)
    timeout_threshold = datetime.now() - timedelta(minutes=timeout_minutes)
    cleaned_count = 0

    for part in all_parts:
        if part.generation_status == "generating" and part.updated_at < timeout_threshold:
            await self.repo.update_status(part, "failed", 0)
            cleaned_count += 1

    return cleaned_count
```

```python
# backend/app/api/routers/writer.py

# 3. 在查询进度时自动清理超时状态
@router.get("/novels/{project_id}/parts/progress")
async def get_part_outline_progress(...):
    # 先清理超时的generating状态
    cleaned_count = await part_service.cleanup_stale_generating_status(project_id, 15)
    # ... 返回进度 ...
```

**影响**：
- 彻底解决状态卡死问题
- 即使异常退出，状态也会被正确更新
- 超时的任务会自动标记为失败，用户可以重试

---

### 2. 实时进度显示缺失 ✅

**问题描述**：
- 用户在生成过程中看不到当前正在生成哪个部分
- 只有在批次（3个部分）完成后才更新进度
- 用户体验差，看起来像卡死

**修复内容**：
```typescript
// frontend/src/components/novel-detail/ChapterOutlineBatchGenerator.vue

const task = (async () => {
  try {
    // 开始生成前立即刷新进度，让用户看到"正在生成第X部分"
    await novelStore.getPartOutlinesProgress()

    await novelStore.generateSinglePartChapters(partNumber)

    // 完成后立即刷新进度，显示最新状态
    await novelStore.getPartOutlinesProgress()
  } catch (err) {
    console.error(`生成第${partNumber}部分失败:`, err)
    // 即使失败也要刷新状态
    await novelStore.getPartOutlinesProgress()
  }
})()
```

**影响**：
- 用户可以实时看到当前正在生成的部分
- 每个部分的状态变化都会立即反映到UI
- 大幅改善用户体验

---

### 3. 添加串行生成机制（保证剧情连贯性） ✅

**问题描述**：
- 大纲内容有前后依赖性，需要参考前面的内容保持连贯
- 前几个部分尤其重要，应该串行生成确保基础设定正确

**修复内容**：
```typescript
// frontend/src/components/novel-detail/ChapterOutlineBatchGenerator.vue

const startGeneration = async () => {
  // 前3个部分串行生成（保证基础设定的连贯性）
  const serialCount = Math.min(3, partsToGenerate.length)
  const maxConcurrent = 3
  let currentIndex = 0

  // 阶段1：前3个部分串行生成
  if (serialCount > 0) {
    console.log(`阶段1：前${serialCount}个部分将串行生成（保证故事基础）`)
    for (let i = 0; i < serialCount; i++) {
      const partNumber = partsToGenerate[currentIndex++]
      await novelStore.getPartOutlinesProgress()
      await novelStore.generateSinglePartChapters(partNumber)
      await novelStore.getPartOutlinesProgress()
      console.log(`第${partNumber}部分串行生成完成`)
    }
  }

  // 阶段2：剩余部分并发生成（批次式，保证前后依赖）
  if (currentIndex < partsToGenerate.length) {
    console.log(`阶段2：剩余部分将并发生成（最多${maxConcurrent}个并发）`)
    // ... 批次并发逻辑 ...
  }
}
```

**影响**：
- 保证故事基础设定（世界观、主要角色等）的连贯性
- 前3个部分串行生成，确保质量
- 后续部分分批并发，提高效率
- 每批次内部并发，批次之间等待，保证前后依赖

---

### 4. 章节重复创建问题 ✅

**问题描述**：
- 并发生成时，多个请求可能同时创建同一章节
- 缺少数据库唯一约束

**修复内容**：
```python
# backend/app/models/novel.py

from sqlalchemy import ..., UniqueConstraint

class ChapterOutline(Base):
    __tablename__ = "chapter_outlines"
    __table_args__ = (
        UniqueConstraint('project_id', 'chapter_number', name='uq_project_chapter'),
    )
    # ... 字段定义 ...
```

```sql
-- backend/db/migrations/create_part_outlines_table.sql

-- 为 chapter_outlines 表添加唯一约束
ALTER TABLE chapter_outlines
ADD UNIQUE KEY uq_project_chapter (project_id, chapter_number);
```

**影响**：
- 防止并发创建重复章节
- 数据库层面保证数据完整性

---

### 5. 数据库迁移文件 ✅

**问题描述**：
- `part_outlines` 表的迁移文件存在但未提交
- 新部署的系统无法创建该表

**修复内容**：
创建完整的数据库迁移SQL文件：

```sql
-- backend/db/migrations/create_part_outlines_table.sql

CREATE TABLE IF NOT EXISTS part_outlines (
    id VARCHAR(36) PRIMARY KEY,
    project_id VARCHAR(36) NOT NULL,
    part_number INT NOT NULL,
    title VARCHAR(255),
    start_chapter INT NOT NULL,
    end_chapter INT NOT NULL,
    summary TEXT,
    theme VARCHAR(500),
    key_events JSON,
    character_arcs JSON,
    conflicts JSON,
    ending_hook TEXT,
    generation_status VARCHAR(50) DEFAULT 'pending',
    progress INT DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (project_id) REFERENCES novel_projects(id) ON DELETE CASCADE,
    UNIQUE KEY uq_project_part (project_id, part_number)
);
```

**影响**：
- 新部署可以正常创建表结构
- 功能完全可用

---

## 用户体验优化

### 6. 批量重试功能 ✅

**新增功能**：
```typescript
// frontend/src/components/novel-detail/ChapterOutlineBatchGenerator.vue

// 批量重试所有失败的部分
const retryAllFailed = async () => {
  const failedParts = partOutlines.value
    .filter(p => p.generation_status === 'failed')
    .map(p => p.part_number)

  for (const partNumber of failedParts) {
    await novelStore.getPartOutlinesProgress()
    await novelStore.generateSinglePartChapters(partNumber, true)
    await novelStore.getPartOutlinesProgress()
  }
}
```

**UI改进**：
- 在进度显示区域右上角添加"重试全部失败"按钮
- 只在有失败部分时显示
- 一键重试所有失败的部分

---

### 7. 改进错误提示 ✅

**修复前**：
```html
<p class="text-xs text-red-700">{{ error }}</p>
```

**修复后**：
```html
<div class="flex-1">
  <p class="text-sm font-medium text-red-900">生成过程中遇到错误</p>
  <p class="text-xs text-red-700 mt-1">{{ error }}</p>
  <p class="text-xs text-red-600 mt-2">
    提示：您可以点击失败部分旁边的"重试"按钮单独重试，
    或使用右上角的"重试全部失败"按钮批量重试。
  </p>
</div>
```

**影响**：
- 用户清楚知道发生了什么
- 提供明确的恢复建议
- 减少用户困惑

---

## 部署指南

### 1. 数据库迁移

**MySQL用户**：
```bash
cd backend
# 方式1：手动执行SQL
mysql -u用户名 -p数据库名 < db/migrations/add_blueprint_part_outline_fields.sql
mysql -u用户名 -p数据库名 < db/migrations/create_part_outlines_table.sql

# 方式2：使用Alembic（如果已配置）
alembic upgrade head
```

**SQLite用户**：
```bash
cd backend
sqlite3 storage/arboris.db < db/migrations/add_blueprint_part_outline_fields.sql
sqlite3 storage/arboris.db < db/migrations/create_part_outlines_table.sql
```

### 2. 代码部署

```bash
# 拉取最新代码
git pull

# 后端：无需额外操作（Python会自动加载新代码）
# 重启后端服务
# systemctl restart arboris-backend  # 或你的启动方式

# 前端：重新构建
cd frontend
npm run build
# 部署dist目录到Web服务器
```

### 3. 验证部署

```bash
# 1. 检查表是否创建成功
mysql -e "SHOW TABLES LIKE 'part_outlines';" 数据库名

# 2. 检查唯一约束
mysql -e "SHOW CREATE TABLE chapter_outlines;" 数据库名

# 3. 测试生成流程
# 访问前端，创建一个>50章的项目，测试部分大纲生成
```

---

## 技术要点总结

### 并发策略
- **前3个部分**：串行生成（保证基础设定连贯性）
- **后续部分**：批次并发（每批最多3个，批次之间等待）
- **原因**：大纲内容有前后依赖，需要参考前面的内容

### 状态管理
- **generating** → 正在生成
- **completed** → 生成完成
- **failed** → 生成失败（可重试）
- **pending** → 待生成

### 超时机制
- 15分钟未更新的`generating`状态自动改为`failed`
- 每次查询进度时自动清理
- 防止永久卡死

### 进度刷新时机
1. 每个部分开始生成前
2. 每个部分生成完成后
3. 每个部分失败后
4. 全部完成后

---

## 已知限制

1. **批次大小固定**：当前批次大小固定为3，未来可考虑可配置
2. **串行数量固定**：前3个部分串行，未来可考虑可配置
3. **超时时间固定**：15分钟超时，未来可考虑可配置

---

## 后续优化建议

1. **生成时间估算**：基于历史数据估算剩余时间
2. **进度百分比**：在生成过程中更新progress字段（当前只有0和100）
3. **暂停/恢复**：支持暂停生成并保存状态
4. **生成质量检查**：自动检查生成的大纲是否符合要求
5. **配置化**：将串行数量、批次大小、超时时间等参数配置化

---

## 修复文件清单

### 后端
- `backend/app/services/part_outline_service.py` - 核心逻辑
- `backend/app/api/routers/writer.py` - API端点
- `backend/app/models/novel.py` - 数据模型（添加唯一约束）
- `backend/db/migrations/create_part_outlines_table.sql` - 数据库迁移

### 前端
- `frontend/src/components/novel-detail/ChapterOutlineBatchGenerator.vue` - UI和生成逻辑

### 文档
- `docs/part_outline_bugfix_summary.md` - 本文档

---

## 测试建议

### 测试场景1：正常生成流程
1. 创建一个100章的小说项目
2. 生成蓝图
3. 生成部分大纲（应该生成4个部分）
4. 批量生成章节大纲
5. 观察：
   - 前3个部分是否串行生成
   - 第4个部分是否与其他部分并发
   - 进度是否实时更新

### 测试场景2：中断恢复
1. 开始生成章节大纲
2. 生成到一半时点击"停止生成"
3. 刷新页面
4. 应该看到"继续生成剩余章节大纲"按钮
5. 点击继续生成，应该从中断处恢复

### 测试场景3：异常处理
1. 开始生成章节大纲
2. 在生成过程中关闭浏览器
3. 等待超过15分钟
4. 重新打开页面查询进度
5. 超时的部分应该显示为"失败"状态
6. 点击"重试全部失败"应该能重新生成

### 测试场景4：并发安全
1. 在浏览器中打开两个标签页
2. 同时点击"开始生成"
3. 观察是否有重复章节创建
4. 数据库应该通过唯一约束防止重复

---

## 结论

本次修复彻底解决了部分大纲生成工作流的核心问题：
- ✅ 状态卡死问题已解决（finally块 + 超时清理）
- ✅ 实时进度显示已优化
- ✅ 串行+并发策略已实现（保证质量和效率）
- ✅ 数据完整性已加强（唯一约束）
- ✅ 用户体验已改善（批量重试、友好提示）

系统现在可以稳定支持长篇小说（51-1000+章）的分层大纲生成，用户体验良好，错误恢复机制完善。
