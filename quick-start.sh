#!/bin/bash

set -e

echo ""
echo "============================================"
echo "  Arboris Novel 快速初始化脚本"
echo "============================================"
echo ""

# 检查是否已存在 .env 文件
if [ -f "deploy/.env" ]; then
    echo "[警告] 检测到已存在 deploy/.env 文件"
    read -p "是否覆盖现有配置？(y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "已取消初始化"
        exit 0
    fi
fi

# 复制 .env.example 为 .env
echo "[1/4] 创建配置文件..."
cp deploy/.env.example deploy/.env
echo "      已创建 deploy/.env"

# 生成随机 SECRET_KEY
echo ""
echo "[2/4] 生成安全密钥..."
SECRET_KEY=$(openssl rand -hex 32 2>/dev/null || cat /dev/urandom | LC_ALL=C tr -dc 'a-zA-Z0-9' | fold -w 64 | head -n 1)
echo "      SECRET_KEY 已生成"

# 提示用户输入 OPENAI_API_KEY
echo ""
echo "[3/4] 配置 LLM API"
echo "      请输入您的 OpenAI API Key（或兼容的服务商 API Key）"
echo "      如果暂时没有，可以按回车跳过，稍后手动编辑 deploy/.env"
echo ""
read -p "API Key: " OPENAI_API_KEY

# 提示用户输入管理员密码
echo ""
echo "[4/4] 设置管理员密码"
echo "      默认管理员账号: admin"
echo "      请设置一个安全的密码（至少 8 位，建议包含大小写字母和数字）"
echo "      如果使用默认密码 ChangeMe123! 请按回车"
echo ""
read -sp "管理员密码: " ADMIN_PASSWORD
echo
if [ -z "$ADMIN_PASSWORD" ]; then
    ADMIN_PASSWORD="ChangeMe123!"
fi

# 更新 .env 文件
echo ""
echo "[配置中] 写入配置文件..."

# 使用 sed 进行配置文件替换（兼容 macOS 和 Linux）
if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS
    sed -i '' "s|^SECRET_KEY=.*|SECRET_KEY=$SECRET_KEY|" deploy/.env
    if [ -n "$OPENAI_API_KEY" ]; then
        sed -i '' "s|^OPENAI_API_KEY=.*|OPENAI_API_KEY=$OPENAI_API_KEY|" deploy/.env
    fi
    sed -i '' "s|^ADMIN_DEFAULT_PASSWORD=.*|ADMIN_DEFAULT_PASSWORD=$ADMIN_PASSWORD|" deploy/.env
else
    # Linux
    sed -i "s|^SECRET_KEY=.*|SECRET_KEY=$SECRET_KEY|" deploy/.env
    if [ -n "$OPENAI_API_KEY" ]; then
        sed -i "s|^OPENAI_API_KEY=.*|OPENAI_API_KEY=$OPENAI_API_KEY|" deploy/.env
    fi
    sed -i "s|^ADMIN_DEFAULT_PASSWORD=.*|ADMIN_DEFAULT_PASSWORD=$ADMIN_PASSWORD|" deploy/.env
fi

echo ""
echo "============================================"
echo "  配置完成！"
echo "============================================"
echo ""
echo "下一步操作："
echo ""
if [ -z "$OPENAI_API_KEY" ]; then
    echo "  [重要] 请编辑 deploy/.env 文件，填写 OPENAI_API_KEY"
    echo ""
fi
echo "  方式一：使用 Docker 启动（推荐）"
echo "    cd deploy"
echo "    docker compose up -d"
echo ""
echo "  方式二：本地开发模式"
echo "    后端: ./dev-start.sh"
echo "    前端: cd frontend && npm install && npm run dev"
echo ""
echo "  启动后访问: http://localhost（Docker）或 http://localhost:5173（本地）"
echo "  管理员账号: admin"
echo "  管理员密码: $ADMIN_PASSWORD"
echo ""
echo "============================================"
