# 开发脚本使用说明

本目录包含了一组用于快速启动、重启和停止 Arboris Novel 开发环境的批处理脚本。

## 📋 脚本清单

### 🚀 启动脚本

| 脚本名称 | 说明 | 使用场景 |
|---------|------|---------|
| `dev-start.bat` | 启动前端和后端 | 首次启动开发环境 |
| `dev-restart.bat` | 重启前端和后端 | **最常用**：修改代码后快速重启 |
| `dev-restart-backend.bat` | 只重启后端 | 仅修改了后端代码 |
| `dev-restart-frontend.bat` | 只重启前端 | 仅修改了前端代码 |
| `dev-stop.bat` | 停止所有服务 | 结束开发工作 |

## 🎯 使用方法

### 快速开始

1. **首次启动**：
   ```
   双击 dev-start.bat
   ```

2. **日常开发（推荐）**：
   ```
   双击 dev-restart.bat
   ```
   自动停止旧进程，启动新进程

### 单独重启

- **只改了后端代码**：
  ```
  双击 dev-restart-backend.bat
  ```

- **只改了前端代码**：
  ```
  双击 dev-restart-frontend.bat
  ```

### 停止服务

```
双击 dev-stop.bat
```

## 📝 注意事项

### 首次使用前的准备

#### 1. 后端环境配置
```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

#### 2. 前端环境配置
```bash
cd frontend
npm install
```

#### 3. 环境变量配置
复制 `.env.example` 为 `.env` 并配置必要的环境变量：
```bash
cp .env.example .env
# 编辑 .env 文件，填写必要的配置
```

### 服务地址

启动成功后，可通过以下地址访问：

- 🎨 **前端界面**: http://localhost:5173
- ⚙️ **后端API**: http://localhost:8000
- 📚 **API文档**: http://localhost:8000/docs

### 故障排查

#### 问题1：脚本执行失败
**原因**：可能是虚拟环境未创建或依赖未安装
**解决**：按照"首次使用前的准备"步骤重新配置

#### 问题2：端口被占用
**症状**：启动时提示端口已被使用
**解决方案**：
1. 运行 `dev-stop.bat` 停止所有服务
2. 如果仍然被占用，手动查找并结束进程：
   ```bash
   # 查找占用8000端口的进程
   netstat -ano | findstr :8000
   # 结束进程（PID为上一步查到的进程ID）
   taskkill /PID <PID> /F

   # 查找占用5173端口的进程
   netstat -ano | findstr :5173
   taskkill /PID <PID> /F
   ```

#### 问题3：后端窗口一闪而过
**原因**：Python 虚拟环境路径错误或未激活
**解决**：
1. 确认 `backend\.venv` 目录存在
2. 手动测试：
   ```bash
   cd backend
   .venv\Scripts\activate
   uvicorn app.main:app --reload
   ```

#### 问题4：前端编译错误
**原因**：依赖包未安装或版本不兼容
**解决**：
```bash
cd frontend
rm -rf node_modules package-lock.json
npm install
```

## 💡 开发技巧

### 推荐工作流

1. **启动开发环境**：`dev-restart.bat`
2. **编写代码**：使用 VSCode 或其他编辑器
3. **修改后快速重启**：
   - 前后端都改了：`dev-restart.bat`
   - 只改后端：`dev-restart-backend.bat`
   - 只改前端：`dev-restart-frontend.bat`（前端有热重载，通常不需要）
4. **结束开发**：`dev-stop.bat`

### 热重载说明

- ✅ **后端热重载**：修改 `.py` 文件后自动重启（uvicorn --reload）
- ✅ **前端热重载**：修改 `.vue`、`.ts` 文件后自动更新（Vite HMR）

**大多数情况下不需要手动重启**，脚本主要用于：
- 解决热重载失效的情况
- 清理旧进程
- 环境配置更改后的完全重启

## 🔧 自定义配置

### 修改端口

如需修改默认端口，编辑对应的 `.bat` 文件：

**后端端口**（默认 8000）：
```batch
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
                                                    ^^^^
                                                    修改这里
```

**前端端口**（默认 5173）：
在 `frontend/vite.config.ts` 中修改：
```typescript
export default defineConfig({
  server: {
    port: 5173,  // 修改这里
  },
})
```

## 📚 相关文档

- [项目README](./README.md)
- [CLAUDE.md](./CLAUDE.md) - Claude Code 项目指南
- [后端API文档](http://localhost:8000/docs) - 启动后可访问

## 🆘 获取帮助

如遇到其他问题，请查看：
1. 项目主 README
2. 后端日志：`backend/storage/debug.log`
3. 前端控制台：浏览器开发者工具
4. GitHub Issues

---

**提示**：这些脚本是为 Windows 系统设计的。Linux/Mac 用户请使用终端直接运行命令。
