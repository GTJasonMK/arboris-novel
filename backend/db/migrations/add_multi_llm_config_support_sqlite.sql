-- 数据库迁移：支持多LLM配置管理和测试功能（SQLite版本）
-- 执行日期：2025-10-28
-- 说明：将 llm_configs 表从单配置扩展为多配置，支持配置测试和切换
-- 数据库：SQLite 3.x
-- 注意：SQLite 不支持复杂的 ALTER TABLE 操作，需要重建表

-- 步骤1：创建新表结构
CREATE TABLE IF NOT EXISTS llm_configs_new (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    config_name TEXT NOT NULL DEFAULT '默认配置',
    llm_provider_url TEXT,
    llm_provider_api_key TEXT,
    llm_provider_model TEXT,
    is_active INTEGER NOT NULL DEFAULT 0,
    is_verified INTEGER NOT NULL DEFAULT 0,
    last_test_at TEXT,  -- SQLite 使用 TEXT 存储时间戳
    test_status TEXT,  -- success, failed, pending
    test_message TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    UNIQUE (user_id, config_name)
);

-- 步骤2：创建索引
CREATE INDEX IF NOT EXISTS idx_llm_configs_user_id ON llm_configs_new(user_id);
CREATE INDEX IF NOT EXISTS idx_llm_configs_is_active ON llm_configs_new(is_active);

-- 步骤3：迁移现有数据（如果存在）
-- 将现有配置迁移为用户的"默认配置"并设置为激活状态
INSERT INTO llm_configs_new (
    user_id,
    config_name,
    llm_provider_url,
    llm_provider_api_key,
    llm_provider_model,
    is_active,
    is_verified,
    created_at,
    updated_at
)
SELECT
    user_id,
    '默认配置' as config_name,
    llm_provider_url,
    llm_provider_api_key,
    llm_provider_model,
    1 as is_active,  -- 现有配置默认激活
    0 as is_verified,  -- 未经过测试
    datetime('now') as created_at,
    datetime('now') as updated_at
FROM llm_configs
WHERE EXISTS (SELECT 1 FROM llm_configs);  -- 仅当表存在数据时执行

-- 步骤4：删除旧表
DROP TABLE IF EXISTS llm_configs;

-- 步骤5：重命名新表
ALTER TABLE llm_configs_new RENAME TO llm_configs;

-- 迁移完成
SELECT '迁移完成！已将现有配置迁移为默认激活配置' AS migration_summary;
