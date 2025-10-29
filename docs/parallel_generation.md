# 章节并行生成性能优化

## 概述

章节并行生成是 Arboris-Novel v1.1 引入的重大性能优化功能，通过同时发起多个 LLM 请求来生成章节的多个候选版本，**大幅缩短生成时间**。

---

## 性能提升对比

### 串行模式（v1.0）
```
版本 1 生成中... (10分钟)
版本 1 完成 ✓

版本 2 生成中... (10分钟)
版本 2 完成 ✓

版本 3 生成中... (10分钟)
版本 3 完成 ✓

总耗时：30 分钟
```

### 并行模式（v1.1，默认启用）
```
版本 1 生成中... ┐
版本 2 生成中... ├─ 同时进行 (10分钟)
版本 3 生成中... ┘

所有版本完成 ✓

总耗时：10 分钟
```

**性能提升**：
- **3 个版本**：从 30 分钟降至 10 分钟（**提速 67%**）
- **2 个版本**：从 20 分钟降至 10 分钟（**提速 50%**）

---

## 技术实现

### 核心机制

使用 Python `asyncio` 的并发控制机制：

1. **asyncio.Semaphore**：控制最大并发请求数，避免 API 限流
2. **asyncio.gather**：并行执行多个异步任务，等待所有任务完成
3. **return_exceptions=True**：允许部分版本失败，不影响其他版本

### 代码架构（writer.py:235-298）

```python
# 创建信号量控制并发数
semaphore = asyncio.Semaphore(settings.writer_max_parallel_requests)

async def _generate_with_semaphore(idx: int) -> Dict:
    """带并发控制的生成函数"""
    async with semaphore:  # 获取信号量
        logger.info("开始生成版本 %s/%s", idx + 1, version_count)
        result = await _generate_single_version(idx)
        logger.info("版本 %s/%s 生成完成", idx + 1, version_count)
        return result

# 创建所有任务并并行执行
tasks = [_generate_with_semaphore(idx) for idx in range(version_count)]
raw_versions = await asyncio.gather(*tasks, return_exceptions=True)

# 处理异常结果
for idx, result in enumerate(raw_versions):
    if isinstance(result, Exception):
        logger.error("版本 %s 生成失败: %s", idx + 1, result)
        processed_versions.append({"content": f"生成失败: {result}"})
    else:
        processed_versions.append(result)
```

### 并发控制流程

```
┌─────────────────────────────────────────────────────┐
│  用户请求生成 3 个章节版本                             │
└────────────────┬────────────────────────────────────┘
                 │
                 ▼
        ┌────────────────┐
        │ 创建 Semaphore  │
        │ (最大并发数 3)  │
        └────────┬───────┘
                 │
                 ▼
    ┌────────────────────────┐
    │  创建 3 个并行任务       │
    │  Task 1: 生成版本 1     │
    │  Task 2: 生成版本 2     │
    │  Task 3: 生成版本 3     │
    └────┬───────┬───────┬───┘
         │       │       │
         │ Semaphore 获取成功 (3/3)
         │       │       │
         ▼       ▼       ▼
    ┌────────┐ ┌────────┐ ┌────────┐
    │ 调用   │ │ 调用   │ │ 调用   │
    │ LLM    │ │ LLM    │ │ LLM    │
    │ API    │ │ API    │ │ API    │
    └────┬───┘ └────┬───┘ └────┬───┘
         │         │         │
         │ (10 分钟，并行执行)
         │         │         │
         ▼         ▼         ▼
    ┌────────┐ ┌────────┐ ┌────────┐
    │ 版本 1 │ │ 版本 2 │ │ 版本 3 │
    │ 完成   │ │ 完成   │ │ 完成   │
    └────┬───┘ └────┬───┘ └────┬───┘
         │         │         │
         └─────────┴─────────┘
                   │
                   ▼
          ┌────────────────┐
          │ 所有版本完成    │
          │ 耗时 10 分钟   │
          └────────────────┘
```

---

## 配置说明

### 环境变量配置（.env）

```env
# 章节生成配置
WRITER_CHAPTER_VERSION_COUNT=2          # 每次生成的版本数量
WRITER_PARALLEL_GENERATION=true         # 启用并行生成
WRITER_MAX_PARALLEL_REQUESTS=3          # 最大并发请求数
```

### 配置项详解

#### 1. WRITER_CHAPTER_VERSION_COUNT
- **默认值**: 2
- **取值范围**: 1-10
- **说明**: 每次生成章节时创建的候选版本数量
- **建议值**:
  - 快速草稿：1 个版本
  - 标准创作：2-3 个版本
  - 精细打磨：3-5 个版本

#### 2. WRITER_PARALLEL_GENERATION
- **默认值**: true（启用）
- **说明**: 是否启用并行生成
- **何时禁用**:
  - API 有严格的限流限制
  - 服务器内存不足
  - 需要调试单个版本的生成过程

#### 3. WRITER_MAX_PARALLEL_REQUESTS
- **默认值**: 3
- **取值范围**: 1-10
- **说明**: 最大并发请求数（Semaphore 限制）
- **建议值**:
  - DeepSeek API：3-5（官方建议）
  - OpenAI API：5-10（Plus 账户）
  - 自建 API：根据服务器负载调整

---

## 错误处理

### 部分版本失败

并行生成使用了 `return_exceptions=True`，允许部分版本失败：

```python
# 示例：3 个版本中 1 个失败
版本 1: 成功 ✓
版本 2: 失败 ✗ (网络错误)
版本 3: 成功 ✓

结果：2 个可用版本，1 个失败版本（显示错误信息）
```

**失败版本的处理**：
- 在候选版本列表中显示为"生成失败：[错误信息]"
- 用户可以选择成功的版本或重新生成
- 不会阻塞其他版本的生成

### 全部版本失败

如果所有版本都失败（极少情况），系统会：
1. 记录详细错误日志
2. 返回错误提示给用户
3. 建议用户检查网络或 API 配置

---

## 性能监控

### 日志示例

**并行模式**：
```
INFO: 项目 xxx 第 1 章计划生成 3 个版本（并行模式：True）
INFO: 项目 xxx 第 1 章开始生成版本 1/3
INFO: 项目 xxx 第 1 章开始生成版本 2/3
INFO: 项目 xxx 第 1 章开始生成版本 3/3
INFO: 项目 xxx 第 1 章版本 1/3 生成完成
INFO: 项目 xxx 第 1 章版本 2/3 生成完成
INFO: 项目 xxx 第 1 章版本 3/3 生成完成
INFO: 项目 xxx 第 1 章所有版本生成完成，耗时 612.34 秒（并行模式：True）
```

**串行模式**：
```
INFO: 项目 xxx 第 1 章计划生成 3 个版本（并行模式：False）
INFO: 项目 xxx 第 1 章开始生成版本 1/3（串行模式）
INFO: 项目 xxx 第 1 章开始生成版本 2/3（串行模式）
INFO: 项目 xxx 第 1 章开始生成版本 3/3（串行模式）
INFO: 项目 xxx 第 1 章所有版本生成完成，耗时 1834.12 秒（并行模式：False）
```

### 性能指标

从日志中可以提取：
- **总耗时**：elapsed_time（秒）
- **平均每版本耗时**：total_time / version_count
- **并行效率**：(串行耗时 - 并行耗时) / 串行耗时 × 100%

---

## 常见问题

### Q1: 启用并行生成后遇到 429 限流错误？

**原因**：并发请求超过 API 提供商的限流限制

**解决方案**：
1. 降低 `WRITER_MAX_PARALLEL_REQUESTS` 值（如从 5 降至 3）
2. 减少 `WRITER_CHAPTER_VERSION_COUNT`（如从 5 降至 2）
3. 升级 API 账户等级或使用自己的 API Key

### Q2: 并行生成是否会消耗更多 API 额度？

**答案**：不会。

并行生成只是改变了**执行顺序**，总的 API 调用次数不变：
- 串行：3 次调用，依次执行
- 并行：3 次调用，同时执行

### Q3: 如何验证并行生成是否生效？

**方法**：
1. 查看后端日志，确认日志中显示 "并行模式：True"
2. 观察生成时间，3 个版本应接近单个版本的耗时
3. 检查日志中多个版本是否几乎同时开始

### Q4: 并行生成是否安全？

**答案**：是的。

- ✅ **数据隔离**：每个版本独立生成，不会相互影响
- ✅ **异常隔离**：部分版本失败不影响其他版本
- ✅ **资源控制**：使用 Semaphore 限制并发，避免过载
- ✅ **向后兼容**：可随时切换回串行模式

### Q5: 内存占用会增加吗？

**答案**：会略有增加，但在可接受范围内。

- 串行模式：同一时间只有 1 个请求在内存中
- 并行模式：同一时间有 N 个请求在内存中（N = MAX_PARALLEL_REQUESTS）

对于默认配置（3 个并发），额外内存占用约为 **50-100MB**，对现代服务器影响不大。

---

## 未来优化方向

### 1. 自适应并发控制
根据 API 响应时间和错误率动态调整并发数：
```python
if error_rate > 0.2:
    max_parallel_requests -= 1  # 降低并发
elif avg_response_time < 5.0:
    max_parallel_requests += 1  # 提升并发
```

### 2. 请求队列
对于大批量生成任务（如生成整本书），使用队列系统避免同时发起过多请求：
```python
from celery import Celery

@celery.task
def generate_chapter_async(project_id, chapter_number):
    # 异步生成章节
    pass
```

### 3. 结果缓存
缓存已生成的版本，避免重复请求：
```python
cache_key = f"chapter:{project_id}:{chapter_number}:version:{idx}"
if cached := redis.get(cache_key):
    return json.loads(cached)
```

### 4. 负载均衡
支持多个 API Key 轮流使用，分散压力：
```python
api_keys = [key1, key2, key3]
selected_key = api_keys[idx % len(api_keys)]
```

---

## 技术细节

### 为什么使用 Semaphore 而不是直接 gather？

**不使用 Semaphore**（不推荐）：
```python
# 所有请求立即发起，可能超过 API 限流
tasks = [generate(idx) for idx in range(100)]
await asyncio.gather(*tasks)
```

**使用 Semaphore**（推荐）：
```python
# 最多同时 3 个请求，其他请求排队等待
semaphore = asyncio.Semaphore(3)
async def generate_with_limit(idx):
    async with semaphore:  # 获取许可
        return await generate(idx)

tasks = [generate_with_limit(idx) for idx in range(100)]
await asyncio.gather(*tasks)
```

### return_exceptions=True 的作用

**不使用**（默认行为）：
```python
# 任何一个版本失败，所有任务都会被取消
await asyncio.gather(*tasks)  # 版本 2 失败 → 取消版本 1 和 3
```

**使用**（推荐）：
```python
# 版本 2 失败，但版本 1 和 3 继续执行
results = await asyncio.gather(*tasks, return_exceptions=True)
# results = [版本1内容, Exception(...), 版本3内容]
```

---

## 相关代码文件

- `backend/app/api/routers/writer.py:235-298` - 并行生成实现
- `backend/app/core/config.py:80-91` - 配置项定义
- `backend/.env:32-35` - 环境变量配置

---

## 变更日志

### v1.1 (2025-01-25)
- ✨ 新增：章节并行生成功能
- ✨ 新增：WRITER_PARALLEL_GENERATION 配置项
- ✨ 新增：WRITER_MAX_PARALLEL_REQUESTS 配置项
- ⚡ 性能：生成速度提升 50-67%
- 🐛 修复：部分版本失败不影响其他版本
- 📝 文档：新增并行生成性能优化文档

---

**最后更新**: 2025-01-25
**版本**: v1.1
**作者**: Arboris-Novel 开发团队
