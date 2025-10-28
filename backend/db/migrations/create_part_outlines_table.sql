-- 数据库迁移：创建 part_outlines 表和添加唯一约束
-- 执行日期：2025-10-26
-- 说明：支持长篇小说分层大纲管理

-- 创建 part_outlines 表
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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 为 chapter_outlines 表添加唯一约束（如果不存在）
-- 注意：如果已存在重复数据，需要先清理
ALTER TABLE chapter_outlines
ADD UNIQUE KEY uq_project_chapter (project_id, chapter_number);

-- 为 SQLite 用户的说明：
-- SQLite 不支持 ALTER TABLE ADD CONSTRAINT，需要手动在创建表时添加唯一约束
-- 或者创建新表、复制数据、删除旧表、重命名新表
