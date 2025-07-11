"""
审查分析和统计API模块。
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from pulse_guard.database import DatabaseManager, PRReviewRecord, close_db, get_db

logger = logging.getLogger(__name__)

router = APIRouter()


class ReviewSummary(BaseModel):
    """审查摘要模型"""

    review_id: str
    repo_full_name: str
    pr_number: int
    pr_title: str
    overall_score: float
    business_score: float
    code_quality_score: float
    security_score: float
    total_issues: int
    critical_issues: int
    standards_passed: int
    standards_total: int
    created_at: datetime


class RepoStatistics(BaseModel):
    """仓库统计模型"""

    repo_full_name: str
    total_reviews: int
    avg_score: float
    total_issues: int
    critical_issues: int
    avg_standards_pass_rate: float
    recent_trend: str  # improving, declining, stable


class DetailedAnalysis(BaseModel):
    """详细分析模型"""

    review_summary: ReviewSummary
    file_analyses: List[Dict[str, Any]]
    standard_checks: List[Dict[str, Any]]
    recommendations: List[str]


@router.get("/reviews/{repo_owner}/{repo_name}", response_model=List[ReviewSummary])
async def get_review_history(
    repo_owner: str,
    repo_name: str,
    limit: int = Query(default=20, le=100),
    offset: int = Query(default=0, ge=0),
):
    """获取仓库的审查历史"""
    repo_full_name = f"{repo_owner}/{repo_name}"

    try:
        db = get_db()
        reviews = (
            db.query(PRReviewRecord)
            .filter(PRReviewRecord.repo_full_name == repo_full_name)
            .order_by(PRReviewRecord.created_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )

        return [
            ReviewSummary(
                review_id=review.review_id,
                repo_full_name=review.repo_full_name,
                pr_number=review.pr_number,
                pr_title=review.pr_title or "",
                overall_score=review.overall_score,
                business_score=review.business_score,
                code_quality_score=review.code_quality_score,
                security_score=review.security_score,
                total_issues=review.total_issues,
                critical_issues=review.critical_issues,
                standards_passed=review.standards_passed,
                standards_total=review.standards_total,
                created_at=review.created_at,
            )
            for review in reviews
        ]
    except Exception as e:
        logger.error(f"获取审查历史失败: {e}")
        raise HTTPException(status_code=500, detail="获取审查历史失败")
    finally:
        close_db(db)


@router.get("/statistics/{repo_owner}/{repo_name}", response_model=RepoStatistics)
async def get_repo_statistics(
    repo_owner: str, repo_name: str, days: int = Query(default=30, ge=1, le=365)
):
    """获取仓库统计信息"""
    repo_full_name = f"{repo_owner}/{repo_name}"

    try:
        # 获取基础统计
        stats = DatabaseManager.get_review_statistics(repo_full_name, days)

        # 计算趋势
        trend = await _calculate_trend(repo_full_name, days)

        # 计算规范通过率
        db = get_db()
        start_date = datetime.utcnow() - timedelta(days=days)

        from sqlalchemy import Float, cast, func

        avg_pass_rate_result = (
            db.query(
                func.avg(
                    cast(PRReviewRecord.standards_passed, Float)
                    / func.nullif(PRReviewRecord.standards_total, 0)
                    * 100
                )
            )
            .filter(
                PRReviewRecord.repo_full_name == repo_full_name,
                PRReviewRecord.created_at >= start_date,
                PRReviewRecord.standards_total > 0,
            )
            .scalar()
        )

        avg_standards_pass_rate = avg_pass_rate_result or 0.0

        return RepoStatistics(
            repo_full_name=repo_full_name,
            total_reviews=stats["total_reviews"],
            avg_score=stats["avg_score"],
            total_issues=stats["total_issues"],
            critical_issues=stats["critical_issues"],
            avg_standards_pass_rate=round(avg_standards_pass_rate, 2),
            recent_trend=trend,
        )
    except Exception as e:
        logger.error(f"获取仓库统计失败: {e}")
        raise HTTPException(status_code=500, detail="获取仓库统计失败")
    finally:
        close_db(db)


@router.get("/analysis/{review_id}", response_model=DetailedAnalysis)
async def get_detailed_analysis(review_id: str):
    """获取详细分析结果"""
    try:
        db = get_db()

        # 获取PR审查记录
        pr_review = (
            db.query(PRReviewRecord)
            .filter(PRReviewRecord.review_id == review_id)
            .first()
        )

        if not pr_review:
            raise HTTPException(status_code=404, detail="审查记录不存在")

        # 构建审查摘要
        review_summary = ReviewSummary(
            review_id=pr_review.review_id,
            repo_full_name=pr_review.repo_full_name,
            pr_number=pr_review.pr_number,
            pr_title=pr_review.pr_title or "",
            overall_score=pr_review.overall_score,
            business_score=pr_review.business_score,
            code_quality_score=pr_review.code_quality_score,
            security_score=pr_review.security_score,
            total_issues=pr_review.total_issues,
            critical_issues=pr_review.critical_issues,
            standards_passed=pr_review.standards_passed,
            standards_total=pr_review.standards_total,
            created_at=pr_review.created_at,
        )

        # 获取文件分析
        file_analyses = []
        for file_review in pr_review.file_reviews:
            file_analyses.append(
                {
                    "filename": file_review.filename,
                    "score": file_review.score,
                    "issues_count": file_review.issues_count,
                    "change_type": file_review.change_type,
                    "impact_level": file_review.impact_level,
                    "business_impact": file_review.business_impact,
                    "summary": file_review.summary,
                    "issues": [
                        {
                            "title": issue.title,
                            "description": issue.description,
                            "severity": issue.severity,
                            "category": issue.category,
                            "line_start": issue.line_start,
                            "line_end": issue.line_end,
                            "suggestion": issue.suggestion,
                        }
                        for issue in file_review.issues
                    ],
                }
            )

        # 获取规范检查
        standard_checks = []
        for check in pr_review.standard_checks:
            standard_checks.append(
                {
                    "standard_id": check.standard_id,
                    "standard_title": check.standard_title,
                    "standard_category": check.standard_category,
                    "passed": check.passed,
                    "score": check.score,
                    "violations_count": check.violations_count,
                    "files_affected": check.files_affected,
                }
            )

        # 生成建议
        recommendations = _generate_recommendations(
            pr_review, file_analyses, standard_checks
        )

        return DetailedAnalysis(
            review_summary=review_summary,
            file_analyses=file_analyses,
            standard_checks=standard_checks,
            recommendations=recommendations,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取详细分析失败: {e}")
        raise HTTPException(status_code=500, detail="获取详细分析失败")
    finally:
        close_db(db)


@router.get("/dashboard/{repo_owner}/{repo_name}")
async def get_dashboard_data(
    repo_owner: str, repo_name: str, days: int = Query(default=30, ge=1, le=365)
):
    """获取仪表板数据"""
    repo_full_name = f"{repo_owner}/{repo_name}"

    try:
        db = get_db()

        # 获取基础统计
        stats = DatabaseManager.get_review_statistics(repo_full_name, days)

        # 获取最近的审查
        recent_reviews = (
            db.query(PRReviewRecord)
            .filter(PRReviewRecord.repo_full_name == repo_full_name)
            .order_by(PRReviewRecord.created_at.desc())
            .limit(5)
            .all()
        )

        recent_reviews_data = [
            {
                "review_id": review.review_id,
                "pr_number": review.pr_number,
                "pr_title": review.pr_title or "",
                "overall_score": review.overall_score,
                "created_at": review.created_at.isoformat(),
            }
            for review in recent_reviews
        ]

        # 获取问题分布
        issue_distribution = await _get_issue_distribution(repo_full_name, days)

        # 获取评分趋势
        score_trend = await _get_score_trend(repo_full_name, days)

        return {
            "statistics": stats,
            "recent_reviews": recent_reviews_data,
            "issue_distribution": issue_distribution,
            "score_trend": score_trend,
        }

    except Exception as e:
        logger.error(f"获取仪表板数据失败: {e}")
        raise HTTPException(status_code=500, detail="获取仪表板数据失败")
    finally:
        close_db(db)


async def _calculate_trend(repo_full_name: str, days: int) -> str:
    """计算趋势"""
    try:
        db = get_db()

        # 获取前半段和后半段的平均分
        mid_point = days // 2
        end_date = datetime.utcnow()
        mid_date = end_date - timedelta(days=mid_point)
        start_date = end_date - timedelta(days=days)

        from sqlalchemy import func

        # 前半段平均分
        early_avg = (
            db.query(func.avg(PRReviewRecord.overall_score))
            .filter(
                PRReviewRecord.repo_full_name == repo_full_name,
                PRReviewRecord.created_at >= start_date,
                PRReviewRecord.created_at < mid_date,
            )
            .scalar()
            or 0
        )

        # 后半段平均分
        recent_avg = (
            db.query(func.avg(PRReviewRecord.overall_score))
            .filter(
                PRReviewRecord.repo_full_name == repo_full_name,
                PRReviewRecord.created_at >= mid_date,
            )
            .scalar()
            or 0
        )

        diff = recent_avg - early_avg

        if diff > 5:
            return "improving"
        elif diff < -5:
            return "declining"
        else:
            return "stable"

    except Exception as e:
        logger.error(f"计算趋势失败: {e}")
        return "unknown"
    finally:
        close_db(db)


async def _get_issue_distribution(repo_full_name: str, days: int) -> Dict[str, int]:
    """获取问题分布"""
    try:
        db = get_db()
        start_date = datetime.utcnow() - timedelta(days=days)

        # 这里简化处理，实际应该从IssueRecord表查询
        from sqlalchemy import func

        result = (
            db.query(
                func.sum(PRReviewRecord.critical_issues).label("critical"),
                func.sum(PRReviewRecord.error_issues).label("error"),
                func.sum(PRReviewRecord.warning_issues).label("warning"),
                func.sum(PRReviewRecord.info_issues).label("info"),
            )
            .filter(
                PRReviewRecord.repo_full_name == repo_full_name,
                PRReviewRecord.created_at >= start_date,
            )
            .first()
        )

        return {
            "critical": result.critical or 0,
            "error": result.error or 0,
            "warning": result.warning or 0,
            "info": result.info or 0,
        }

    except Exception as e:
        logger.error(f"获取问题分布失败: {e}")
        return {"critical": 0, "error": 0, "warning": 0, "info": 0}
    finally:
        close_db(db)


async def _get_score_trend(repo_full_name: str, days: int) -> List[Dict[str, Any]]:
    """获取评分趋势"""
    try:
        db = get_db()
        start_date = datetime.utcnow() - timedelta(days=days)

        reviews = (
            db.query(PRReviewRecord)
            .filter(
                PRReviewRecord.repo_full_name == repo_full_name,
                PRReviewRecord.created_at >= start_date,
            )
            .order_by(PRReviewRecord.created_at)
            .all()
        )

        return [
            {
                "date": review.created_at.isoformat(),
                "overall_score": review.overall_score,
                "code_quality_score": review.code_quality_score,
                "security_score": review.security_score,
                "business_score": review.business_score,
            }
            for review in reviews
        ]

    except Exception as e:
        logger.error(f"获取评分趋势失败: {e}")
        return []
    finally:
        close_db(db)


def _generate_recommendations(
    pr_review: PRReviewRecord, file_analyses: List[Dict], standard_checks: List[Dict]
) -> List[str]:
    """生成改进建议"""
    recommendations = []

    # 基于总体评分
    if pr_review.overall_score < 70:
        recommendations.append("代码质量需要显著改进，建议重点关注代码规范和最佳实践")

    # 基于安全评分
    if pr_review.security_score < 80:
        recommendations.append("发现安全问题，建议进行安全代码审查和漏洞修复")

    # 基于业务评分
    if pr_review.business_score < 75:
        recommendations.append("业务逻辑需要优化，建议与产品团队确认需求实现")

    # 基于规范通过率
    if pr_review.standards_total > 0:
        pass_rate = pr_review.standards_passed / pr_review.standards_total
        if pass_rate < 0.8:
            recommendations.append(
                "代码规范通过率较低，建议使用代码格式化工具和静态分析工具"
            )

    # 基于问题严重程度
    if pr_review.critical_issues > 0:
        recommendations.append(
            f"发现 {pr_review.critical_issues} 个严重问题，必须在合并前修复"
        )

    # 基于文件影响
    high_impact_files = [
        fa for fa in file_analyses if fa.get("impact_level") in ["high", "critical"]
    ]
    if high_impact_files:
        recommendations.append(
            f"有 {len(high_impact_files)} 个高影响文件，建议进行额外的测试和验证"
        )

    return recommendations if recommendations else ["代码质量良好，继续保持！"]
