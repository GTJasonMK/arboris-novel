# DeepSeek API 连接问题排查与解决方案

## 问题描述

### 错误信息
```
生成失败: 503: AI 服务连接被意外中断，请稍后重试
```

### 错误类型
- **HTTP 状态码**: 503 Service Unavailable
- **异常类型**: `httpx.RemoteProtocolError`
- **发生场景**: 章节生成、蓝图生成、对话等所有 LLM 调用

## 根本原因分析

### 1. DeepSeek API 服务端问题
- **服务不稳定**: DeepSeek API 服务可能因负载过高或维护导致连接中断
- **主动断开**: 服务端检测到异常请求或限流时主动断开连接
- **超时保护**: 长时间请求（如章节生成）可能触发服务端超时保护

### 2. 网络层问题
- **中间代理**: 网络中间层（如公司代理、防火墙）关闭长时间空闲的 TCP 连接
- **NAT 超时**: NAT 网关的连接超时设置可能短于请求完成时间
- **运营商限制**: ISP 对长连接的限制

### 3. 客户端配置问题
- **超时设置**: 客户端超时设置与服务端不匹配
- **缺少重试**: 临时性网络错误未自动重试

## 解决方案

### 已实施的改进（v1.0）

#### 1. 自动重试机制

在 `backend/app/services/llm_service.py` 中实现了智能重试逻辑：

```python
async def _stream_and_collect(
    self,
    messages: List[Dict[str, str]],
    *,
    temperature: float,
    user_id: Optional[int],
    timeout: float,
    response_format: Optional[str] = None,
    max_tokens: Optional[int] = None,
    max_retries: int = 2,  # 新增：默认重试2次
) -> str:
    """流式收集 LLM 响应，支持自动重试网络错误"""
```

**重试策略**:
- **最大重试次数**: 2 次（总共最多 3 次尝试）
- **指数退避**:
  - 第 1 次重试前等待 2 秒
  - 第 2 次重试前等待 4 秒
- **重试条件**: 仅对以下网络错误重试
  - `httpx.RemoteProtocolError` - 连接被意外中断
  - `httpx.ReadTimeout` - 读取超时
  - `APIConnectionError` - 连接错误
  - `APITimeoutError` - API 超时

**不重试的错误**:
- `InternalServerError` - DeepSeek 服务内部错误（500）
- 业务逻辑错误（如响应截断、空响应）

#### 2. 优化的错误提示

**修改前**:
```
AI 服务连接被意外中断，请稍后重试
```

**修改后**:
```
AI 服务连接被意外中断，请稍后重试（已尝试 3 次）
```

用户可以清楚知道系统已经自动重试过，而不是首次失败。

#### 3. 详细的日志记录

```python
logger.error(
    "LLM stream failed: model=%s user_id=%s attempt=%d/%d detail=%s",
    config.get("model"),
    user_id,
    attempt + 1,
    max_retries + 1,
    detail,
    exc_info=exc,
)
```

便于排查问题和监控 API 稳定性。

### 超时配置总览

| 操作类型 | 超时时间 | 文件位置 | 说明 |
|---------|---------|---------|------|
| 概念对话 | 240s (4分钟) | `novels.py:170` | 灵感模式对话 |
| 蓝图生成 | 480s (8分钟) | `novels.py:246` | 生成完整蓝图 |
| 蓝图优化 | 480s (8分钟) | `novels.py:359` | 优化现有蓝图 |
| 章节生成 | 600s (10分钟) | `writer.py:203` | 生成章节版本 |
| 章节评审 | 360s (6分钟) | `writer.py:389` | 评审所有版本 |
| 大纲生成 | 360s (6分钟) | `writer.py:438` | 生成章节大纲 |
| 摘要提取 | 180s (3分钟) | `writer.py:92,306,584` | 提取章节摘要 |

## 使用建议

### 对于用户

1. **遇到 503 错误时**:
   - 系统已自动重试 3 次，无需立即重试
   - 等待 1-2 分钟后再次尝试
   - 如果持续失败，检查网络连接

2. **提高成功率的方法**:
   - 避免生成过长的内容（使用更短的章节大纲）
   - 选择网络稳定的时段进行创作
   - 考虑使用自己的 API Key（绕过共享限流）

3. **紧急情况**:
   - 可以在设置中配置自己的 DeepSeek API Key
   - 或切换到其他兼容 OpenAI 格式的 LLM 提供商

### 对于管理员

1. **监控 API 健康状态**:
   ```bash
   # 查看后端日志中的重试记录
   grep "Retrying LLM request" backend/logs/app.log

   # 统计失败率
   grep "LLM stream failed" backend/logs/app.log | wc -l
   ```

2. **调整重试参数** (可选):
   ```python
   # 在 llm_service.py:88 修改默认重试次数
   max_retries: int = 3,  # 增加到3次重试
   ```

3. **优化超时设置** (可选):
   ```python
   # 在 writer.py:203 调整章节生成超时
   timeout=900.0,  # 从10分钟增加到15分钟
   ```

## 未来优化方向

### 1. 可配置的重试策略
在 `.env` 中添加配置项:
```env
LLM_MAX_RETRIES=2
LLM_RETRY_DELAY_BASE=2
LLM_ENABLE_CIRCUIT_BREAKER=true
```

### 2. 断路器模式
当 DeepSeek API 持续失败时，自动切换到备用提供商或降级服务。

### 3. 请求队列
对于大批量生成任务，使用队列系统避免同时发起过多请求。

### 4. 本地缓存
缓存已生成的内容，避免重复请求。

### 5. 负载均衡
支持多个 API Key 轮流使用，分散压力。

## 技术细节

### 重试流程图

```
┌─────────────────────────────────────────────┐
│         发起 LLM 请求                        │
└────────────────┬────────────────────────────┘
                 │
                 ▼
        ┌────────────────┐
        │  尝试连接 API   │
        └────┬───────────┘
             │
    ┌────────┴────────┐
    │   请求成功？     │
    └────┬────────┬───┘
         │ 是     │ 否
         │        │
         │        ├─── 网络错误 ───┐
         │        │                │
         │        ├─── 内部错误 ───┼─── 直接抛出异常
         │        │                │
         │        └─── 其他错误 ───┘
         │                         │
         │                         ▼
         │                ┌────────────────┐
         │                │ 已重试次数 < 2?│
         │                └───┬────────┬───┘
         │                    │ 是     │ 否
         │                    │        │
         │                    │        └─── 抛出 503 错误
         │                    │             (已尝试 3 次)
         │                    ▼
         │            ┌───────────────┐
         │            │ 指数退避等待   │
         │            │ (2^n 秒)      │
         │            └───────┬───────┘
         │                    │
         │                    └─── 重新尝试
         │
         ▼
    ┌────────────┐
    │ 返回响应    │
    └────────────┘
```

### 异常处理层级

1. **网络层异常** (可重试):
   - `httpx.RemoteProtocolError`
   - `httpx.ReadTimeout`
   - `APIConnectionError`
   - `APITimeoutError`

2. **服务层异常** (不重试):
   - `InternalServerError` (500)
   - HTTP 4xx 错误

3. **业务层异常** (不重试):
   - 响应截断 (`finish_reason == "length"`)
   - 空响应
   - JSON 解析失败

## 相关代码文件

- `backend/app/services/llm_service.py:79-239` - 重试逻辑实现
- `backend/app/api/routers/writer.py` - 章节生成超时配置
- `backend/app/api/routers/novels.py` - 蓝图生成超时配置
- `backend/app/utils/llm_tool.py` - LLMClient 封装

## 问题反馈

如果仍然遇到持续的 503 错误，请提供以下信息：

1. **错误发生时间**: 精确到分钟
2. **操作类型**: 章节生成/蓝图生成/对话等
3. **后端日志**: `backend/logs/app.log` 中的相关错误
4. **网络环境**: 是否使用代理、VPN 等
5. **DeepSeek 状态**: 访问 https://api.deepseek.com 查看服务状态

---

**最后更新**: 2025-01-25
**版本**: v1.0
**作者**: Arboris-Novel 开发团队
