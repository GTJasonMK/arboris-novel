# SQLAlchemy Session 并发冲突解决方案

## 问题描述

### 错误信息
```
生成失败: Session is already flushing
```

### 错误场景
在启用章节并行生成功能后，生成多个章节版本时出现 SQLAlchemy session 并发冲突错误。

---

## 根本原因

### 真正的罪魁祸首：SQLAlchemy Autoflush 机制

经过深入排查，**真正的问题不是 `session.commit()` 或 `session.flush()` 的直接并发调用，而是 SQLAlchemy 的 autoflush 机制导致的隐式并发冲突**。

### 1. 并发数据库查询

在并行生成模式下，每个并行任务都会调用：

```python
# 版本 1、2、3 并行执行
async def _generate_single_version(idx):
    response = await llm_service.get_llm_response(...)  # 并行调用
```

每个 `get_llm_response()` 都会调用：

```python
async def _stream_and_collect(...):
    config = await self._resolve_llm_config(user_id)  # 查询数据库！
```

### 2. _resolve_llm_config 中的数据库查询

```python
async def _resolve_llm_config(self, user_id):
    if user_id:
        config = await self.llm_repo.get_by_user(user_id)  # ← 数据库查询
```

### 3. SQLAlchemy Autoflush 机制

**关键发现**：SQLAlchemy 默认启用 `autoflush=True`，任何数据库查询操作（如 `SELECT`）都会先自动 flush pending changes。

```python
# llm_repo.get_by_user() 内部执行 SELECT 查询
# SQLAlchemy 自动执行：
session.flush()  # ← 隐式 flush！

# 当多个并行协程同时查询时：
协程 1: llm_repo.get_by_user() → autoflush → session.flush()
协程 2: llm_repo.get_by_user() → autoflush → session.flush()  ← 冲突！
协程 3: llm_repo.get_by_user() → autoflush → session.flush()  ← 冲突！
```

当第一个协程的 `session.flush()` 正在执行时，其他协程也尝试 flush，就会抛出 **"Session is already flushing"** 错误。

### 4. 问题调用链

```
generate_chapter (writer.py)
  ├─ asyncio.gather([
  │    _generate_single_version(0),  ┐
  │    _generate_single_version(1),  ├─ 并行执行
  │    _generate_single_version(2)   ┘
  │  ])
  │
  ├─ llm_service.get_llm_response()
  │    ├─ _stream_and_collect()
  │    └─ _resolve_llm_config()
  │         └─ llm_repo.get_by_user()  ← 数据库查询
  │              └─ autoflush         ← 隐式 flush，并发冲突！
```

---

## 解决方案演进

### ❌ 第一次尝试：跳过 usage tracking

```python
# 只解决了 usage_service.increment() 的并发 commit
if not skip_usage_tracking:
    await self.usage_service.increment("api_request_count")
```

**结果**：失败，错误依然存在。因为问题不在 usage tracking，而在配置查询的 autoflush。

### ❌ 第二次尝试：跳过 daily limit check

```python
# 只解决了 _enforce_daily_limit() 的并发 commit
if user_id and not skip_daily_limit_check:
    await self._enforce_daily_limit(user_id)
```

**结果**：失败，错误依然存在。因为 `_resolve_llm_config()` 中还有 `llm_repo.get_by_user()` 的查询。

### ✅ 最终方案：缓存 LLM 配置，避免并行任务中的数据库访问

**核心思路**：在并行生成前，先获取 LLM 配置并缓存，然后将配置传递给所有并行任务，完全避免并行任务中的数据库查询。

---

## 实施步骤

### 1. 添加 `cached_config` 参数

在 `LLMService.get_llm_response` 中添加可选参数：

```python
# llm_service.py:38-63
async def get_llm_response(
    self,
    system_prompt: str,
    conversation_history: List[Dict[str, str]],
    *,
    cached_config: Optional[Dict[str, Optional[str]]] = None,  # 新增参数
) -> str:
    return await self._stream_and_collect(
        messages,
        cached_config=cached_config,  # 传递参数
    )
```

### 2. 在 _stream_and_collect 中使用缓存配置

```python
# llm_service.py:85-111
async def _stream_and_collect(
    self,
    messages: List[Dict[str, str]],
    *,
    cached_config: Optional[Dict[str, Optional[str]]] = None,
) -> str:
    """流式收集 LLM 响应，支持自动重试网络错误

    Args:
        cached_config: 缓存的 LLM 配置（用于并行模式，避免并发数据库查询）
    """
    # 使用缓存配置或实时查询配置
    if cached_config:
        config = cached_config  # 直接使用缓存，避免数据库查询
    else:
        config = await self._resolve_llm_config(user_id, skip_daily_limit_check)
```

### 3. 在并行生成前缓存配置

在章节生成时，根据并行模式缓存配置：

```python
# writer.py:215-236
# 在并行模式下，预先获取 LLM 配置并缓存，避免并行任务中的数据库查询导致 autoflush 冲突
llm_config: Optional[Dict[str, Optional[str]]] = None
if skip_usage_tracking:
    llm_config = await llm_service._resolve_llm_config(current_user.id, skip_daily_limit_check=True)
    logger.info("项目 %s 第 %s 章（并行模式）已缓存 LLM 配置", project_id, request.chapter_number)

async def _generate_single_version(idx: int) -> Dict:
    response = await llm_service.get_llm_response(
        system_prompt=writer_prompt,
        conversation_history=[{"role": "user", "content": prompt_input}],
        cached_config=llm_config,  # 使用缓存配置，避免并发查询
    )
```

---

## 修复效果

### Before（有问题）

```
版本 1 生成中... → _resolve_llm_config() → llm_repo.get_by_user() → autoflush ┐
版本 2 生成中... → _resolve_llm_config() → llm_repo.get_by_user() → autoflush ├─ 并发冲突！
版本 3 生成中... → _resolve_llm_config() → llm_repo.get_by_user() → autoflush ┘

错误: Session is already flushing
```

### After（已修复）

```
并行生成前 → 获取并缓存 LLM 配置（单次查询）✓

版本 1 生成中... → 使用缓存配置（无数据库访问）✓
版本 2 生成中... → 使用缓存配置（无数据库访问）✓
版本 3 生成中... → 使用缓存配置（无数据库访问）✓

所有版本完成 → 统一更新计数 3 次 ✓
```

---

## 技术细节

### SQLAlchemy Autoflush 机制详解

SQLAlchemy 的 Session 默认启用 `autoflush=True`：

```python
# 当执行查询时
result = await session.execute(select(User).where(User.id == user_id))

# SQLAlchemy 内部自动执行：
if session.is_modified:  # 如果有 pending changes
    session.flush()      # 自动 flush！
# 然后才执行查询
```

这个机制的目的是确保查询结果的一致性，但在并发场景下会导致问题：

```python
# 并发场景
协程 1: 开始查询 → 检查 pending changes → 开始 flush → [正在 flush]
协程 2: 开始查询 → 检查 pending changes → 尝试 flush → 错误："Session is already flushing"
```

### 为什么缓存配置能解决问题？

**方案对比**：

| 方案 | 并行任务中的数据库操作 | 是否触发 autoflush | 结果 |
|------|----------------------|-------------------|------|
| 原始代码 | 每个任务查询 LLM 配置 | ✓ 是 | ❌ 冲突 |
| 跳过 usage tracking | 每个任务查询 LLM 配置 | ✓ 是 | ❌ 冲突 |
| 跳过 daily limit | 每个任务查询 LLM 配置 | ✓ 是 | ❌ 冲突 |
| **缓存配置** | 无数据库操作 | ✗ 否 | ✅ 成功 |

**缓存配置方案的优势**：
1. **彻底避免并发冲突**：并行任务中完全没有数据库访问
2. **性能提升**：避免重复查询，节省数据库连接
3. **代码简洁**：不需要复杂的锁机制或 session 管理
4. **向后兼容**：`cached_config` 是可选参数，不影响现有代码

---

## 相关代码文件

### 核心修改
- `backend/app/services/llm_service.py:50, 97, 107-111` - 添加 cached_config 参数并使用
- `backend/app/api/routers/writer.py:215-236` - 在并行生成前缓存 LLM 配置

### 相关依赖
- `backend/app/services/usage_service.py` - Usage tracking 服务（已跳过并发调用）
- `backend/app/core/config.py:80-91` - 并行配置项
- `backend/app/repositories/llm_config_repository.py` - LLM 配置查询（已通过缓存避免并发）

---

## 最佳实践

### 1. 并发操作中避免数据库访问

**黄金法则**：并行任务中尽量避免任何数据库操作（包括查询）。

**错误示例**：
```python
async def parallel_task(session, user_id):
    config = await get_config_from_db(session, user_id)  # ❌ 并发查询
    return await process(config)

tasks = [parallel_task(session, uid) for uid in user_ids]
await asyncio.gather(*tasks)  # 触发 autoflush 冲突
```

**正确示例**：
```python
# 先查询所有配置
configs = {uid: await get_config_from_db(session, uid) for uid in user_ids}

async def parallel_task(config):
    return await process(config)  # ✓ 无数据库访问

tasks = [parallel_task(configs[uid]) for uid in user_ids]
await asyncio.gather(*tasks)  # 无冲突
```

### 2. 理解 Autoflush 的触发时机

以下操作会触发 autoflush：
- `session.execute(select(...))` - 任何查询操作
- `session.refresh(obj)` - 刷新对象状态
- `session.merge(obj)` - 合并对象
- `session.query(...).all()` - ORM 查询

不会触发 autoflush：
- 访问已加载的对象属性
- 纯内存计算
- 使用缓存数据

### 3. 配置缓存模式

在并发场景下，遵循以下模式：

```python
# 1. 并发前：查询并缓存
cache = await fetch_config_from_db(session)

# 2. 并发中：只使用缓存
async def task(item, cache):
    # 使用 cache，不访问 session
    return await process(item, cache)

# 3. 并发后：统一更新数据库
results = await asyncio.gather(*[task(item, cache) for item in items])
await update_db(session, results)
```

---

## 总结

### 问题
并行生成导致多个协程同时查询数据库配置，触发 SQLAlchemy autoflush 机制的并发冲突。

### 解决方案
在并行生成前缓存 LLM 配置，并行任务直接使用缓存，完全避免数据库访问。

### 关键原则
1. **识别隐式数据库操作**：查询操作也会触发 autoflush
2. **并发前缓存数据**：在并行任务开始前查询并缓存所需数据
3. **并发中避免 DB 访问**：并行任务只使用缓存数据或纯计算
4. **并发后统一更新**：所有任务完成后，统一更新数据库

### 修复文件
- `llm_service.py`: 添加 `cached_config` 参数，支持配置缓存
- `writer.py`: 在并行生成前缓存配置，并行任务使用缓存

---

**最后更新**: 2025-01-25
**版本**: v1.1.2
**作者**: Arboris-Novel 开发团队
