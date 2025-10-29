# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

Arboris-Novel 是一个基于 AI 的长篇小说创作辅助平台，通过概念对话、蓝图生成、RAG 增强的章节生成流程，帮助作者管理复杂的世界观、角色关系和剧情逻辑。

## 核心技术栈

- **后端**: Python 3.10+ + FastAPI + SQLAlchemy (异步)
- **前端**: Vue 3 + TypeScript + Vite + TailwindCSS + Naive UI
- **数据库**: MySQL (asyncmy) 或 SQLite (aiosqlite)，通过 `DB_PROVIDER` 环境变量切换
- **向量存储**: libsql (用于 RAG 章节检索)
- **LLM 集成**: OpenAI API 兼容接口 + Ollama (可选的嵌入模型提供方)

## 常用开发命令

### 后端开发

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 启动开发服务器（热重载）
uvicorn app.main:app --reload

# 指定端口
uvicorn app.main:app --reload --port 8000

# 暴露到局域网
uvicorn app.main:app --reload --host 0.0.0.0
```

### 前端开发

```bash
cd frontend
npm install

# 启动开发服务器（默认 http://localhost:5173）
npm run dev

# 类型检查
npm run type-check

# 构建生产版本
npm run build

# 代码格式化
npm run format
```

### 数据库迁移

项目使用 Alembic 管理数据库迁移：

```bash
cd backend

# 生成新迁移文件
alembic revision --autogenerate -m "描述变更内容"

# 应用迁移
alembic upgrade head

# 回滚迁移
alembic downgrade -1
```

### Docker 部署

```bash
# 使用 SQLite（默认）
docker compose up -d

# 使用 MySQL
DB_PROVIDER=mysql docker compose --profile mysql up -d

# 重新构建镜像
docker compose up -d --build

# 查看日志
docker compose logs -f backend
```

## 架构设计要点

### 后端分层架构

项目采用严格的分层架构，遵循单一职责原则：

1. **Models** (`app/models/`): SQLAlchemy ORM 模型定义，映射数据库表结构
2. **Schemas** (`app/schemas/`): Pydantic 模型，用于请求/响应验证和序列化
3. **Repositories** (`app/repositories/`): 数据访问层，封装所有数据库操作
4. **Services** (`app/services/`): 业务逻辑层，协调 Repositories 和外部服务
5. **Routers** (`app/api/routers/`): API 路由定义，仅负责请求解析和响应返回

**重要约定**：
- Repository 只负责数据库 CRUD，不包含业务逻辑
- Service 调用 Repository 和其他 Service，处理业务流程
- Router 通过依赖注入获取数据库 session，传递给 Service
- 所有数据库操作必须使用异步方法（`async/await`）

**核心数据模型关系**：
- `User` (用户) → 1:N → `Novel` (小说项目)
- `Novel` → 1:1 → `NovelBlueprint` (蓝图)
- `Novel` → 1:N → `NovelConversation` (概念对话记录)
- `Novel` → 1:N → `Chapter` (章节)
- `Chapter` → 1:N → `ChapterVersion` (候选版本)
- `Chapter` → 0:1 → `ChapterEvaluation` (评审报告)
- `Novel` → 向量库 `rag_chunks` / `rag_summaries` (通过 project_id 关联)

### 小说生成流水线

核心工作流程分为五个阶段（详见 `docs/novel_workflow.md`）：

1. **概念对话** (`POST /api/novels/{id}/concept/converse`)
   - 使用 `concept` 提示词 + JSON schema 约束
   - 温度 0.8，引导用户梳理世界观和剧情要素
   - 对话完成后允许进入蓝图阶段

2. **蓝图生成** (`POST /api/novels/{id}/blueprint/generate`)
   - 使用 `screenwriting` 提示词
   - 温度 0.3，基于概念对话生成结构化蓝图
   - 输出世界观、角色档案、章节纲要等 JSON 结构

3. **章节生成** (`POST /api/writer/novels/{id}/chapters/generate`)
   - 使用 `writing` 提示词
   - 温度 0.9，生成多个候选版本（默认 2 个）
   - 支持并行生成以提升速度（默认启用，最多 3 个并发请求）
   - 上下文组装顺序：
     - 精简蓝图（剔除章节细节）
     - 上一章摘要 + 正文末尾 500 字
     - RAG 检索结果（Top-K chunks + summaries）
     - 当前章节目标（标题、纲要、写作指令）

4. **版本选择与评审**
   - 选择版本：`POST /api/writer/novels/{id}/chapters/select`
   - 评审所有版本：`POST /api/writer/novels/{id}/chapters/evaluate` (使用 `evaluation` 提示词，温度 0.3)

5. **摘要提取与向量化**
   - 使用 `extraction` 提示词，温度 0.15
   - 触发 `ChapterIngestionService.ingest_chapter` 切分正文并写入向量库
   - 为后续 RAG 检索提供真实内容

### RAG 向量检索系统

向量存储由 `VectorStoreService` 管理，基于 libsql 实现：

**表结构**：
- `rag_chunks`: 章节正文分块（project_id, chapter_number, content, embedding）
- `rag_summaries`: 章节摘要（project_id, chapter_number, summary, embedding）

**切分策略**：
- 优先使用 `langchain-text-splitters` 的 `RecursiveCharacterTextSplitter`
- `chunk_size=480`（默认），`chunk_overlap=120`
- 分隔符优先级：双换行 > 单换行 > 句号/问号/感叹号 > 逗号 > 空格
- 未安装依赖时回退到内置段落切分

**检索流程**：
1. 将章节标题 + 纲要摘要转为查询向量（`LLMService.get_embedding`）
2. 从向量库检索相关 chunks (Top-5) 和 summaries (Top-3)
3. 优先使用 libsql 的 `vector_distance_cosine` 函数
4. 若数据库不支持向量函数，回退到 Python 端余弦距离计算

**向量生命周期**：
- 插入/更新：章节确认或编辑后，先删除旧向量，再批量写入
- 删除：调用 `delete_chapters` 接口时同步清理向量库

### 配置管理

所有配置集中在 `app/core/config.py` 的 `Settings` 类：

- 环境变量优先级：`.env` > 系统配置表 (`system_configs`)
- 数据库 URL 自动生成（支持 MySQL 密码特殊字符转义）
- LLM 配置支持用户级覆盖（通过 `llm_configs` 表）
- 向量检索参数可通过环境变量调整：
  - `VECTOR_TOP_K_CHUNKS` (默认 5)
  - `VECTOR_TOP_K_SUMMARIES` (默认 3)
  - `VECTOR_CHUNK_SIZE` (默认 480)
  - `VECTOR_CHUNK_OVERLAP` (默认 120)

**关键配置项**：
- `DB_PROVIDER`: 数据库类型 (mysql/sqlite)
- `OPENAI_API_KEY` / `OPENAI_API_BASE_URL`: 默认 LLM 配置
- `EMBEDDING_PROVIDER`: 嵌入模型提供方 (openai/ollama)
- `VECTOR_DB_URL`: libsql 连接地址（支持 `file:` 本地路径）
- `WRITER_CHAPTER_VERSION_COUNT`: 章节生成候选版本数
- `WRITER_PARALLEL_GENERATION`: 是否启用并行生成（默认 true，大幅提升速度）
- `WRITER_MAX_PARALLEL_REQUESTS`: 最大并行请求数（默认 3，避免 API 限流）

### 提示词管理

所有提示词存储在 `backend/prompts/` 目录，通过 `PromptService` 加载：

- `concept.md`: 概念对话引导
- `screenwriting.md`: 蓝图生成
- `writing.md`: 章节正文生成
- `evaluation.md`: 章节版本评审
- `extraction.md`: 摘要提取
- `outline.md`: 大纲生成
- `part_outline.md`: 分卷大纲生成

**使用方式**：
```python
prompt_service = PromptService(session)
system_prompt = await prompt_service.get_prompt("writing")
```

提示词在应用启动时预加载到内存（`app/main.py` 的 `lifespan` 钩子），支持通过管理后台动态更新。

### 前端架构

- **路由**: Vue Router 4，定义在 `frontend/src/router/index.ts`
- **状态管理**: Pinia，主要 stores:
  - `auth.ts`: 用户认证状态
  - `novel.ts`: 小说项目状态
- **组件组织**:
  - `components/`: 通用组件
  - `components/admin/`: 管理后台专用组件
  - `components/novel-detail/`: 小说详情页分区组件
  - `components/writing-desk/`: 写作台专用组件
  - `views/`: 页面级组件
- **样式**: TailwindCSS 4.x + `@tailwindcss/typography` 用于富文本渲染
- **UI 组件库**: Naive UI 2.x

**API 调用约定**：
- 所有 API 请求统一使用 `httpx` 或 `fetch`
- 携带 JWT Token：`Authorization: Bearer <token>`
- 后端基础路径：`/api/`（生产环境通过 Nginx 代理）

## 常见开发任务

### 添加新的 API 路由

1. 在 `app/schemas/` 创建请求/响应模型
2. 在对应 Repository 添加数据访问方法
3. 在对应 Service 添加业务逻辑
4. 在 `app/api/routers/` 添加路由处理函数
5. 在 `app/api/routers/__init__.py` 中注册路由

### 修改数据库模型

1. 编辑 `app/models/` 中的模型类
2. 生成迁移：`alembic revision --autogenerate -m "描述"`
3. 检查生成的迁移文件（`backend/alembic/versions/`）
4. 应用迁移：`alembic upgrade head`
5. 更新对应的 Pydantic Schema

### 调整提示词

1. 直接编辑 `backend/prompts/*.md` 文件
2. 或通过管理后台 `/admin` 的"提示词管理"界面在线编辑
3. 修改后需重启后端服务或等待缓存刷新

### 调试 RAG 检索

- 检查向量库连接：查看启动日志中的 "初始化 libsql 客户端" 信息
- 验证向量写入：`ChapterIngestionService` 会在每次入库时打印日志
- 查看检索结果：`ChapterContextService.build_chapter_context` 包含详细的检索日志
- 若检索失败，系统会降级为"蓝图 + 历史摘要"模式继续生成

### 切换数据库提供者

```bash
# 在 .env 中修改
DB_PROVIDER=sqlite  # 或 mysql

# SQLite 数据存储路径（默认 backend/storage/arboris.db）
# MySQL 需配置 MYSQL_HOST, MYSQL_PORT, MYSQL_USER, MYSQL_PASSWORD, MYSQL_DATABASE
```

重启后端服务后，首次启动会自动建表。

### 验证安装和配置

```bash
# 检查后端健康状态
curl http://localhost:8000/health

# 查看后端日志（关键启动信息）
tail -f backend/storage/debug.log

# 测试数据库连接（检查日志中的数据库初始化信息）
# 测试向量库连接（检查日志中的 "初始化 libsql 客户端" 信息）
```

## 开发注意事项

1. **异步编程**：所有数据库操作必须使用 `async/await`，避免阻塞事件循环
2. **Session 管理**：数据库 session 由 `get_db` 依赖注入提供，自动提交/回滚
3. **错误处理**：使用 `HTTPException` 抛出 HTTP 错误，避免未捕获异常
4. **日志记录**：
   - 使用 `logging` 模块，日志级别通过 `LOGGING_LEVEL` 环境变量控制
   - 日志文件位于 `backend/storage/debug.log`
   - 关键业务逻辑（LLM 调用、RAG 检索、向量入库）都有详细日志
   - 日志配置在 `app/main.py` 中完成，必须在导入路由前配置
5. **环境隔离**：开发环境使用 `.env`，生产环境通过 Docker 环境变量注入
6. **代码风格**：后端遵循 PEP 8，前端使用 Prettier 格式化
7. **类型注解**：Python 代码必须添加类型注解，前端 TypeScript 避免使用 `any`
8. **依赖注入**：FastAPI 路由使用依赖注入获取 session、当前用户等资源
9. **中文注释**：项目中所有注释和文档使用中文，符合团队规范
10. **LLM 调用**：
    - 所有 LLM 调用通过 `LLMService` 统一管理
    - 支持重试机制（默认最多重试 3 次）
    - 超时设置根据任务类型调整（概念对话 240s，蓝图生成 480s，章节生成 600s）
    - 支持用户级 LLM 配置覆盖（通过 `llm_configs` 表）

## 项目特殊约定

- **不使用 emoji**：代码、注释、提交信息中避免使用 emoji，防止编码问题
- **Repository 模式**：数据访问层统一继承 `BaseRepository`，提供通用 CRUD 方法
- **配置优先级**：用户级 LLM 配置 > 系统配置表 > 环境变量默认值
- **向量检索降级**：若向量库未配置或查询失败，章节生成仍可继续（无 RAG 增强）
- **多版本生成**：章节生成默认返回多个候选版本，用户可评审后选择或手动编辑
