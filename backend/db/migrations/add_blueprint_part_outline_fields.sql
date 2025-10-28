-- 数据库迁移：为 novel_blueprints 表添加分阶段生成相关字段
-- 执行日期：2025-10-26
-- 说明：支持长篇小说（>50章）分阶段生成部分大纲和章节大纲

-- 为 novel_blueprints 表添加3个新字段
ALTER TABLE novel_blueprints
ADD COLUMN needs_part_outlines TINYINT(1) DEFAULT 0 AFTER world_setting,
ADD COLUMN total_chapters INT NULL AFTER needs_part_outlines,
ADD COLUMN chapters_per_part INT DEFAULT 25 AFTER total_chapters;

-- 为已存在的蓝图设置默认值
UPDATE novel_blueprints
SET needs_part_outlines = 0,
    chapters_per_part = 25
WHERE needs_part_outlines IS NULL OR chapters_per_part IS NULL;
