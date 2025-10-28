-- SQLite 版本：为 novel_blueprints 表添加分阶段生成相关字段
-- 执行日期：2025-10-26
-- 说明：支持长篇小说（>50章）分阶段生成部分大纲和章节大纲

-- SQLite 不支持 AFTER 子句，只能按顺序添加列到表末尾
ALTER TABLE novel_blueprints ADD COLUMN needs_part_outlines INTEGER DEFAULT 0;
ALTER TABLE novel_blueprints ADD COLUMN total_chapters INTEGER;
ALTER TABLE novel_blueprints ADD COLUMN chapters_per_part INTEGER DEFAULT 25;
