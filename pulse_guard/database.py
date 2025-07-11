"""
数据库配置和模型定义模块。
"""

import uuid
from datetime import datetime
from typing import Any, Dict, List

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    create_engine,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session, relationship, sessionmaker

from pulse_guard.config import config

# 创建数据库引擎
engine = create_engine(
    config.database.url,
    echo=config.database.echo,
    pool_pre_ping=True,
)

# 创建会话工厂
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 创建基类
Base = declarative_base()


class PRReviewRecord(Base):
    """PR审查记录表"""

    __tablename__ = "pr_reviews"

    id = Column(Integer, primary_key=True, index=True)
    review_id = Column(
        String(36), unique=True, index=True, default=lambda: str(uuid.uuid4())
    )

    # PR基本信息
    repo_full_name = Column(String(255), nullable=False, index=True)
    pr_number = Column(Integer, nullable=False, index=True)
    pr_title = Column(String(500))
    pr_description = Column(Text)
    pr_author = Column(String(100))
    platform = Column(String(20), default="github")  # github, gitee

    # 审查结果
    overall_score = Column(Float, default=0.0)  # 总体评分 0-100
    total_issues = Column(Integer, default=0)
    critical_issues = Column(Integer, default=0)
    error_issues = Column(Integer, default=0)
    warning_issues = Column(Integer, default=0)
    info_issues = Column(Integer, default=0)

    # 规范检查结果
    standards_passed = Column(Integer, default=0)  # 通过的规范数量
    standards_failed = Column(Integer, default=0)  # 未通过的规范数量
    standards_total = Column(Integer, default=0)  # 总规范数量

    # 业务审查结果
    business_score = Column(Float, default=0.0)  # 业务逻辑评分
    code_quality_score = Column(Float, default=0.0)  # 代码质量评分
    security_score = Column(Float, default=0.0)  # 安全评分

    # 审查状态
    status = Column(String(20), default="completed")  # pending, completed, failed
    review_comment_posted = Column(Boolean, default=False)

    # 时间戳
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 关联关系
    file_reviews = relationship(
        "FileReviewRecord", back_populates="pr_review", cascade="all, delete-orphan"
    )
    standard_checks = relationship(
        "StandardCheckRecord", back_populates="pr_review", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<PRReviewRecord(repo={self.repo_full_name}, pr={self.pr_number}, score={self.overall_score})>"


class FileReviewRecord(Base):
    """文件审查记录表"""

    __tablename__ = "file_reviews"

    id = Column(Integer, primary_key=True, index=True)
    pr_review_id = Column(Integer, ForeignKey("pr_reviews.id"), nullable=False)

    # 文件信息
    filename = Column(String(500), nullable=False)
    file_type = Column(String(50))
    file_size = Column(Integer, default=0)
    lines_added = Column(Integer, default=0)
    lines_deleted = Column(Integer, default=0)
    lines_changed = Column(Integer, default=0)

    # 审查结果
    summary = Column(Text)
    score = Column(Float, default=0.0)  # 文件评分 0-100
    issues_count = Column(Integer, default=0)

    # 修改分析
    change_type = Column(String(20))  # added, modified, deleted, renamed
    impact_level = Column(String(20), default="low")  # low, medium, high, critical
    business_impact = Column(Text)  # 业务影响分析

    # 时间戳
    created_at = Column(DateTime, default=datetime.utcnow)

    # 关联关系
    pr_review = relationship("PRReviewRecord", back_populates="file_reviews")
    issues = relationship(
        "IssueRecord", back_populates="file_review", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<FileReviewRecord(filename={self.filename}, score={self.score})>"


class IssueRecord(Base):
    """问题记录表"""

    __tablename__ = "issues"

    id = Column(Integer, primary_key=True, index=True)
    file_review_id = Column(Integer, ForeignKey("file_reviews.id"), nullable=False)

    # 问题信息
    title = Column(String(500), nullable=False)
    description = Column(Text)
    category = Column(String(50), nullable=False)  # code_quality, security, etc.
    severity = Column(String(20), nullable=False)  # info, warning, error, critical

    # 位置信息
    line_start = Column(Integer)
    line_end = Column(Integer)
    code_snippet = Column(Text)  # 相关代码片段

    # 建议和修复
    suggestion = Column(Text)
    auto_fixable = Column(Boolean, default=False)
    fix_confidence = Column(Float, default=0.0)  # 修复建议的置信度

    # 规范关联
    standard_id = Column(String(20))  # 关联的规范ID
    rule_violated = Column(String(200))  # 违反的具体规则

    # 时间戳
    created_at = Column(DateTime, default=datetime.utcnow)

    # 关联关系
    file_review = relationship("FileReviewRecord", back_populates="issues")

    def __repr__(self):
        return f"<IssueRecord(title={self.title}, severity={self.severity})>"


class StandardCheckRecord(Base):
    """规范检查记录表"""

    __tablename__ = "standard_checks"

    id = Column(Integer, primary_key=True, index=True)
    pr_review_id = Column(Integer, ForeignKey("pr_reviews.id"), nullable=False)

    # 规范信息
    standard_id = Column(String(20), nullable=False)
    standard_title = Column(String(200), nullable=False)
    standard_category = Column(String(50), nullable=False)
    standard_level = Column(String(20), nullable=False)  # must, should, could, wont

    # 检查结果
    passed = Column(Boolean, nullable=False)
    score = Column(Float, default=0.0)  # 该规范的得分
    weight = Column(Integer, default=1)  # 权重

    # 检查详情
    check_details = Column(JSON)  # 检查详细信息
    violations_count = Column(Integer, default=0)  # 违规次数
    files_affected = Column(JSON)  # 受影响的文件列表

    # 时间戳
    created_at = Column(DateTime, default=datetime.utcnow)

    # 关联关系
    pr_review = relationship("PRReviewRecord", back_populates="standard_checks")

    def __repr__(self):
        return f"<StandardCheckRecord(standard_id={self.standard_id}, passed={self.passed})>"


class ReviewMetrics(Base):
    """审查指标统计表"""

    __tablename__ = "review_metrics"

    id = Column(Integer, primary_key=True, index=True)

    # 统计维度
    repo_full_name = Column(String(255), index=True)
    date = Column(DateTime, index=True)
    period_type = Column(String(20), default="daily")  # daily, weekly, monthly

    # 统计数据
    total_reviews = Column(Integer, default=0)
    avg_score = Column(Float, default=0.0)
    total_issues = Column(Integer, default=0)
    critical_issues = Column(Integer, default=0)

    # 规范通过率
    standards_pass_rate = Column(Float, default=0.0)

    # 分类统计
    security_issues = Column(Integer, default=0)
    quality_issues = Column(Integer, default=0)
    business_issues = Column(Integer, default=0)

    # 时间戳
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<ReviewMetrics(repo={self.repo_full_name}, date={self.date})>"


def get_db() -> Session:
    """获取数据库会话"""
    db = SessionLocal()
    try:
        return db
    finally:
        pass  # 不在这里关闭，由调用者负责


def init_database():
    """初始化数据库"""
    Base.metadata.create_all(bind=engine)


def close_db(db: Session):
    """关闭数据库会话"""
    db.close()


# 数据库操作辅助函数
class DatabaseManager:
    """数据库管理器"""

    @staticmethod
    def save_pr_review(
        repo_full_name: str,
        pr_number: int,
        pr_title: str,
        pr_description: str,
        pr_author: str,
        platform: str = "github",
    ) -> PRReviewRecord:
        """保存PR审查记录"""
        db = get_db()
        try:
            pr_review = PRReviewRecord(
                repo_full_name=repo_full_name,
                pr_number=pr_number,
                pr_title=pr_title,
                pr_description=pr_description,
                pr_author=pr_author,
                platform=platform,
            )
            db.add(pr_review)
            db.commit()
            db.refresh(pr_review)
            return pr_review
        finally:
            close_db(db)

    @staticmethod
    def update_pr_review_scores(
        pr_review_id: int,
        overall_score: float,
        business_score: float,
        code_quality_score: float,
        security_score: float,
        standards_passed: int,
        standards_failed: int,
        standards_total: int,
    ):
        """更新PR审查评分"""
        db = get_db()
        try:
            pr_review = (
                db.query(PRReviewRecord)
                .filter(PRReviewRecord.id == pr_review_id)
                .first()
            )
            if pr_review:
                pr_review.overall_score = overall_score
                pr_review.business_score = business_score
                pr_review.code_quality_score = code_quality_score
                pr_review.security_score = security_score
                pr_review.standards_passed = standards_passed
                pr_review.standards_failed = standards_failed
                pr_review.standards_total = standards_total
                pr_review.updated_at = datetime.utcnow()
                db.commit()
        finally:
            close_db(db)

    @staticmethod
    def get_pr_review_history(
        repo_full_name: str, limit: int = 50
    ) -> List[PRReviewRecord]:
        """获取PR审查历史"""
        db = get_db()
        try:
            return (
                db.query(PRReviewRecord)
                .filter(PRReviewRecord.repo_full_name == repo_full_name)
                .order_by(PRReviewRecord.created_at.desc())
                .limit(limit)
                .all()
            )
        finally:
            close_db(db)

    @staticmethod
    def get_review_statistics(repo_full_name: str, days: int = 30) -> Dict[str, Any]:
        """获取审查统计信息"""
        db = get_db()
        try:
            from datetime import timedelta

            from sqlalchemy import func

            start_date = datetime.utcnow() - timedelta(days=days)

            stats = (
                db.query(
                    func.count(PRReviewRecord.id).label("total_reviews"),
                    func.avg(PRReviewRecord.overall_score).label("avg_score"),
                    func.sum(PRReviewRecord.total_issues).label("total_issues"),
                    func.sum(PRReviewRecord.critical_issues).label("critical_issues"),
                )
                .filter(
                    PRReviewRecord.repo_full_name == repo_full_name,
                    PRReviewRecord.created_at >= start_date,
                )
                .first()
            )

            return {
                "total_reviews": stats.total_reviews or 0,
                "avg_score": round(stats.avg_score or 0, 2),
                "total_issues": stats.total_issues or 0,
                "critical_issues": stats.critical_issues or 0,
            }
        finally:
            close_db(db)

    @staticmethod
    def save_complete_review_result(
        repo_full_name: str,
        pr_number: int,
        pr_title: str,
        pr_description: str,
        pr_author: str,
        platform: str,
        review_result: Dict[str, Any],
    ) -> int:
        """保存完整的审查结果到数据库

        Args:
            repo_full_name: 仓库全名
            pr_number: PR编号
            pr_title: PR标题
            pr_description: PR描述
            pr_author: PR作者
            platform: 平台名称
            review_result: 审查结果字典，包含enhanced_analysis和file_reviews

        Returns:
            PR审查记录的ID
        """
        db = get_db()
        try:
            # 获取审查结果数据
            enhanced_analysis = review_result.get("enhanced_analysis", {})
            file_reviews = review_result.get("file_reviews", [])

            # 创建PR审查记录
            pr_review = PRReviewRecord(
                repo_full_name=repo_full_name,
                pr_number=pr_number,
                pr_title=pr_title,
                pr_description=pr_description,
                pr_author=pr_author,
                platform=platform,
                overall_score=enhanced_analysis.get("overall_score", 0.0),
                business_score=enhanced_analysis.get("business_score", 0.0),
                code_quality_score=enhanced_analysis.get("code_quality_score", 0.0),
                security_score=enhanced_analysis.get("security_score", 0.0),
                standards_passed=enhanced_analysis.get("standards_passed", 0),
                standards_failed=enhanced_analysis.get("standards_failed", 0),
                standards_total=enhanced_analysis.get("standards_total", 0),
                status="completed",
            )

            # 计算问题统计
            total_issues = 0
            critical_issues = 0
            error_issues = 0
            warning_issues = 0
            info_issues = 0

            for file_review in file_reviews:
                issues = file_review.get("issues", [])
                total_issues += len(issues)

                for issue in issues:
                    severity = issue.get("severity", "info").lower()
                    if severity == "critical":
                        critical_issues += 1
                    elif severity == "error":
                        error_issues += 1
                    elif severity == "warning":
                        warning_issues += 1
                    else:
                        info_issues += 1

            pr_review.total_issues = total_issues
            pr_review.critical_issues = critical_issues
            pr_review.error_issues = error_issues
            pr_review.warning_issues = warning_issues
            pr_review.info_issues = info_issues

            db.add(pr_review)
            db.flush()  # 获取ID但不提交

            # 保存文件审查记录
            for file_review in file_reviews:
                file_record = FileReviewRecord(
                    pr_review_id=pr_review.id,
                    filename=file_review.get("filename", ""),
                    score=file_review.get("score", 0.0),
                    summary=file_review.get("summary", ""),
                    issues_count=len(file_review.get("issues", [])),
                    change_type="modified",  # 默认值，可以后续优化
                    impact_level="medium",  # 默认值，可以后续优化
                )
                db.add(file_record)
                db.flush()  # 获取ID但不提交

                # 保存问题记录
                for issue in file_review.get("issues", []):
                    issue_record = IssueRecord(
                        file_review_id=file_record.id,
                        title=issue.get("title", ""),
                        description=issue.get("description", ""),
                        category=issue.get("category", "other"),
                        severity=issue.get("severity", "info"),
                        line_start=issue.get("line"),
                        suggestion=issue.get("suggestion", ""),
                        auto_fixable=False,  # 默认值
                        fix_confidence=0.0,  # 默认值
                    )
                    db.add(issue_record)

            db.commit()
            return pr_review.id

        except Exception as e:
            db.rollback()
            raise e
        finally:
            close_db(db)
