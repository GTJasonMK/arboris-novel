-- 数据库迁移：支持多LLM配置管理和测试功能
-- 执行日期：2025-10-28
-- 说明：将 llm_configs 表从单配置扩展为多配置，支持配置测试和切换
-- 数据库：MySQL 8.x

-- 步骤1：创建临时表，使用新结构
CREATE TABLE IF NOT EXISTS llm_configs_new (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    config_name VARCHAR(100) NOT NULL DEFAULT '默认配置',
    llm_provider_url TEXT NULL,
    llm_provider_api_key TEXT NULL,
    llm_provider_model TEXT NULL,
    is_active TINYINT(1) NOT NULL DEFAULT 0,
    is_verified TINYINT(1) NOT NULL DEFAULT 0,
    last_test_at TIMESTAMP NULL,
    test_status VARCHAR(50) NULL COMMENT 'success, failed, pending',
    test_message TEXT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_llm_configs_new_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    UNIQUE KEY uq_llm_configs_user_name (user_id, config_name),
    INDEX idx_llm_configs_user_id (user_id),
    INDEX idx_llm_configs_is_active (is_active)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 步骤2：迁移现有数据（如果存在）
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
    NOW() as created_at,
    NOW() as updated_at
FROM llm_configs;

-- 步骤3：删除旧表
DROP TABLE llm_configs;

-- 步骤4：重命名新表
ALTER TABLE llm_configs_new RENAME TO llm_configs;

-- 迁移完成提示
SELECT CONCAT(
    '迁移完成！已将 ',
    COUNT(*),
    ' 条配置迁移为默认激活配置'
) AS migration_summary
FROM llm_configs;
