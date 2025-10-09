-- 为 PR 审查记录表添加代码行数统计字段
-- 迁移脚本: 20251009.sql
-- 创建时间: 2025-10-09

-- 添加代码行数统计字段到 pr_reviews 表
ALTER TABLE pr_reviews
ADD COLUMN total_files INTEGER DEFAULT 0 COMMENT '涉及文件总数',
ADD COLUMN total_lines_added INTEGER DEFAULT 0 COMMENT '新增代码行数',
ADD COLUMN total_lines_deleted INTEGER DEFAULT 0 COMMENT '删除代码行数',
ADD COLUMN total_lines_changed INTEGER DEFAULT 0 COMMENT '总变更行数';

-- 更新现有记录的统计数据（从 file_reviews 表聚合）
UPDATE pr_reviews pr
SET
    total_files = (
        SELECT COUNT(*)
        FROM file_reviews fr
        WHERE fr.pr_review_id = pr.id
    ),
    total_lines_added = (
        SELECT COALESCE(SUM(lines_added), 0)
        FROM file_reviews fr
        WHERE fr.pr_review_id = pr.id
    ),
    total_lines_deleted = (
        SELECT COALESCE(SUM(lines_deleted), 0)
        FROM file_reviews fr
        WHERE fr.pr_review_id = pr.id
    ),
    total_lines_changed = (
        SELECT COALESCE(SUM(lines_changed), 0)
        FROM file_reviews fr
        WHERE fr.pr_review_id = pr.id
    )
WHERE EXISTS (
    SELECT 1 FROM file_reviews fr WHERE fr.pr_review_id = pr.id
);

-- 添加索引以提高查询性能
CREATE INDEX idx_pr_reviews_total_files ON pr_reviews(total_files);
CREATE INDEX idx_pr_reviews_total_lines_changed ON pr_reviews(total_lines_changed);

-- 验证迁移结果
SELECT
    COUNT(*) as total_records,
    AVG(total_files) as avg_files,
    AVG(total_lines_added) as avg_lines_added,
    AVG(total_lines_deleted) as avg_lines_deleted,
    AVG(total_lines_changed) as avg_lines_changed
FROM pr_reviews
WHERE total_files > 0;
