import os
import sys
from datetime import datetime, timedelta
from typing import Tuple

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import gradio as gr
import pandas as pd

from backend.database import (
    FileReviewRecord,
    IssueRecord,
    PRReviewRecord,
    close_db,
    get_db,
)


class PRReviewApp:
    """AI PR代码审查结果可视化系统前端应用"""

    def __init__(self):
        self.current_repo = None

    def get_pr_reviews(self, repo_name: str = "", limit: int = 50) -> pd.DataFrame:
        """获取PR审查记录列表"""
        db = get_db()
        try:
            query = db.query(PRReviewRecord)

            if repo_name.strip():
                query = query.filter(
                    PRReviewRecord.repo_full_name.contains(repo_name.strip())
                )

            reviews = (
                query.order_by(PRReviewRecord.created_at.desc()).limit(limit).all()
            )

            if not reviews:
                return pd.DataFrame(
                    columns=[
                        "ID",
                        "仓库",
                        "PR编号",
                        "标题",
                        "作者",
                        "平台",
                        "总体评分",
                        "代码质量",
                        "安全性",
                        "业务逻辑",
                        "总问题数",
                        "严重问题",
                        "创建时间",
                    ]
                )

            data = []
            for review in reviews:
                data.append(
                    {
                        "ID": review.id,
                        "仓库": review.repo_full_name,
                        "PR编号": review.pr_number,
                        "标题": (
                            review.pr_title[:50] + "..."
                            if len(review.pr_title) > 50
                            else review.pr_title
                        ),
                        "作者": review.pr_author,
                        "平台": review.platform,
                        "总体评分": f"{review.overall_score:.1f}",
                        "代码质量": f"{review.code_quality_score:.1f}",
                        "安全性": f"{review.security_score:.1f}",
                        "业务逻辑": f"{review.business_score:.1f}",
                        "总问题数": review.total_issues,
                        "严重问题": review.critical_issues,
                        "创建时间": review.created_at.strftime("%Y-%m-%d %H:%M"),
                    }
                )

            return pd.DataFrame(data)

        except Exception as e:
            return pd.DataFrame({"错误": [f"查询失败: {str(e)}"]})
        finally:
            close_db(db)

    def get_pr_detail(
            self, pr_review_id: int
    ) -> Tuple[str, pd.DataFrame, pd.DataFrame]:
        """获取PR审查详情"""
        if not pr_review_id:
            return "请选择一个PR审查记录", pd.DataFrame(), pd.DataFrame()

        db = get_db()
        try:
            # 获取PR审查记录
            pr_review = (
                db.query(PRReviewRecord)
                .filter(PRReviewRecord.id == pr_review_id)
                .first()
            )
            if not pr_review:
                return "未找到指定的PR审查记录", pd.DataFrame(), pd.DataFrame()

            # 构建基本信息
            basic_info = f"""
# PR审查详情

**仓库**: {pr_review.repo_full_name}
**PR编号**: #{pr_review.pr_number}
**标题**: {pr_review.pr_title}
**作者**: {pr_review.pr_author}
**平台**: {pr_review.platform}
**审查时间**: {pr_review.created_at.strftime("%Y-%m-%d %H:%M:%S")}

## 评分概览
- **总体评分**: {pr_review.overall_score:.1f}/100
- **代码质量**: {pr_review.code_quality_score:.1f}/100
- **安全性**: {pr_review.security_score:.1f}/100
- **业务逻辑**: {pr_review.business_score:.1f}/100

## 问题统计
- **总问题数**: {pr_review.total_issues}
- **严重问题**: {pr_review.critical_issues}
- **错误**: {pr_review.error_issues}
- **警告**: {pr_review.warning_issues}
- **信息**: {pr_review.info_issues}

## 规范检查
- **通过**: {pr_review.standards_passed}/{pr_review.standards_total}
- **失败**: {pr_review.standards_failed}/{pr_review.standards_total}
"""

            # 获取文件审查记录
            file_reviews = (
                db.query(FileReviewRecord)
                .filter(FileReviewRecord.pr_review_id == pr_review_id)
                .all()
            )

            file_data = []
            for file_review in file_reviews:
                file_data.append(
                    {
                        "文件名": file_review.filename,
                        "评分": f"{file_review.score:.1f}",
                        "问题数": file_review.issues_count,
                        "影响级别": file_review.impact_level,
                        "摘要": (
                            file_review.summary[:200] + "..."
                            if len(file_review.summary) > 200
                            else file_review.summary
                        ),
                    }
                )

            file_df = (
                pd.DataFrame(file_data)
                if file_data
                else pd.DataFrame(
                    columns=["文件名", "评分", "问题数", "影响级别", "摘要"]
                )
            )

            # 获取问题记录
            issues = (
                db.query(IssueRecord)
                .join(FileReviewRecord)
                .filter(FileReviewRecord.pr_review_id == pr_review_id)
                .all()
            )

            issue_data = []
            for issue in issues:
                issue_data.append(
                    {
                        "文件": issue.file_review.filename,
                        "标题": issue.title,
                        "严重程度": issue.severity,
                        "类别": issue.category,
                        "行号": issue.line_start or "",
                        "描述": (
                            issue.description[:150] + "..."
                            if len(issue.description) > 150
                            else issue.description
                        ),
                        "建议": (
                            issue.suggestion[:150] + "..."
                            if issue.suggestion and len(issue.suggestion) > 150
                            else issue.suggestion or ""
                        ),
                    }
                )

            issue_df = (
                pd.DataFrame(issue_data)
                if issue_data
                else pd.DataFrame(
                    columns=["文件", "标题", "严重程度", "类别", "行号", "描述", "建议"]
                )
            )

            return basic_info, file_df, issue_df

        except Exception as e:
            return f"获取详情失败: {str(e)}", pd.DataFrame(), pd.DataFrame()
        finally:
            close_db(db)

    def get_repository_statistics(self, repo_name: str = "", days: int = 30) -> str:
        """获取仓库统计信息"""
        db = get_db()
        try:

            start_date = datetime.utcnow() - timedelta(days=days)

            query = db.query(PRReviewRecord).filter(
                PRReviewRecord.created_at >= start_date
            )

            if repo_name.strip():
                query = query.filter(
                    PRReviewRecord.repo_full_name.contains(repo_name.strip())
                )

            reviews = query.all()

            if not reviews:
                return "指定时间范围内没有审查记录"

            # 计算统计信息
            total_reviews = len(reviews)
            avg_score = sum(r.overall_score for r in reviews) / total_reviews
            total_issues = sum(r.total_issues for r in reviews)
            critical_issues = sum(r.critical_issues for r in reviews)

            # 按平台统计
            platform_stats = {}
            for review in reviews:
                platform = review.platform
                if platform not in platform_stats:
                    platform_stats[platform] = {
                        "count": 0,
                        "avg_score": 0,
                        "total_score": 0,
                    }
                platform_stats[platform]["count"] += 1
                platform_stats[platform]["total_score"] += review.overall_score

            for platform in platform_stats:
                platform_stats[platform]["avg_score"] = (
                        platform_stats[platform]["total_score"]
                        / platform_stats[platform]["count"]
                )

            # 评分分布
            score_ranges = {"90-100": 0, "80-89": 0, "70-79": 0, "60-69": 0, "<60": 0}
            for review in reviews:
                score = review.overall_score
                if score >= 90:
                    score_ranges["90-100"] += 1
                elif score >= 80:
                    score_ranges["80-89"] += 1
                elif score >= 70:
                    score_ranges["70-79"] += 1
                elif score >= 60:
                    score_ranges["60-69"] += 1
                else:
                    score_ranges["<60"] += 1

            stats_text = f"""
# 仓库统计信息 (最近{days}天)

## 总体概览
- **总审查数**: {total_reviews}
- **平均评分**: {avg_score:.1f}/100
- **总问题数**: {total_issues}
- **严重问题**: {critical_issues}

## 平台分布
"""
            for platform, stats in platform_stats.items():
                stats_text += f"- **{platform}**: {stats['count']} 次审查，平均评分 {stats['avg_score']:.1f}\n"

            stats_text += f"""
## 评分分布
- **90-100分**: {score_ranges['90-100']} 次
- **80-89分**: {score_ranges['80-89']} 次
- **70-79分**: {score_ranges['70-79']} 次
- **60-69分**: {score_ranges['60-69']} 次
- **60分以下**: {score_ranges['<60']} 次

## 详细分析
- **平均问题密度**: {total_issues / total_reviews:.1f} 问题/PR
- **严重问题比例**: {(critical_issues / total_issues * 100) if total_issues > 0 else 0:.1f}%
- **高质量PR比例** (≥90分): {(score_ranges['90-100'] / total_reviews * 100):.1f}%
"""

            return stats_text

        except Exception as e:
            return f"获取统计信息失败: {str(e)}"
        finally:
            close_db(db)

    def search_issues(
            self, keyword: str = "", severity: str = "all", limit: int = 100
    ) -> pd.DataFrame:
        """搜索问题记录"""
        db = get_db()
        try:
            query = db.query(IssueRecord).join(FileReviewRecord).join(PRReviewRecord)

            if keyword.strip():
                query = query.filter(
                    IssueRecord.title.contains(keyword.strip())
                    | IssueRecord.description.contains(keyword.strip())
                )

            if severity != "all":
                query = query.filter(IssueRecord.severity == severity)

            issues = query.order_by(IssueRecord.created_at.desc()).limit(limit).all()

            if not issues:
                return pd.DataFrame(
                    columns=[
                        "仓库",
                        "PR编号",
                        "文件",
                        "标题",
                        "严重程度",
                        "类别",
                        "行号",
                        "描述",
                        "建议",
                        "创建时间",
                    ]
                )

            data = []
            for issue in issues:
                data.append(
                    {
                        "仓库": issue.file_review.pr_review.repo_full_name,
                        "PR编号": issue.file_review.pr_review.pr_number,
                        "文件": issue.file_review.filename,
                        "标题": issue.title,
                        "严重程度": issue.severity,
                        "类别": issue.category,
                        "行号": issue.line_start or "",
                        "描述": (
                            issue.description[:100] + "..."
                            if len(issue.description) > 100
                            else issue.description
                        ),
                        "建议": (
                            issue.suggestion[:100] + "..."
                            if issue.suggestion and len(issue.suggestion) > 100
                            else issue.suggestion or ""
                        ),
                        "创建时间": issue.created_at.strftime("%Y-%m-%d %H:%M"),
                    }
                )

            return pd.DataFrame(data)

        except Exception as e:
            return pd.DataFrame({"错误": [f"搜索失败: {str(e)}"]})
        finally:
            close_db(db)


def create_interface():
    """创建PR审查结果可视化界面"""
    app = PRReviewApp()

    with gr.Blocks(
            title="AI PR代码审查结果可视化系统", theme=gr.themes.Soft()
    ) as interface:
        gr.Markdown("# 🔍 AI PR代码审查结果可视化系统")
        gr.Markdown("查看和分析AI代码审查结果，包括PR评分、问题统计、文件分析等")

        with gr.Tabs():
            # Tab 1: PR审查记录查询
            with gr.TabItem("📋 PR审查记录"):
                gr.Markdown("## 查询PR审查记录")

                with gr.Row():
                    repo_filter = gr.Textbox(
                        label="仓库名称过滤", placeholder="输入仓库名称进行过滤（可选）"
                    )
                    limit_input = gr.Number(
                        label="显示数量", value=50, minimum=1, maximum=200
                    )
                    search_btn = gr.Button("🔍 查询", variant="primary")

                pr_reviews_table = gr.Dataframe(
                    label="PR审查记录", interactive=False, wrap=True
                )

                search_btn.click(
                    app.get_pr_reviews,
                    inputs=[repo_filter, limit_input],
                    outputs=[pr_reviews_table],
                )

            # Tab 2: PR详情查看
            with gr.TabItem("📄 PR详情"):
                gr.Markdown("## 查看PR审查详情")

                with gr.Row():
                    pr_id_input = gr.Number(label="PR审查记录ID", value=0, minimum=0)
                    detail_btn = gr.Button("📖 查看详情", variant="primary")

                # PR基本信息区域
                pr_detail_info = gr.Markdown(
                    label="PR基本信息", elem_id="pr_detail_info"
                )

                # 文件审查结果区域 - 独立占用全宽
                gr.Markdown("### 📁 文件审查结果")
                file_reviews_table = gr.Dataframe(
                    label="文件审查记录", interactive=False, wrap=True
                )

                # 问题详情区域 - 独立占用全宽
                gr.Markdown("### 🐛 问题详情")
                issues_table = gr.Dataframe(
                    label="问题记录", interactive=False, wrap=True
                )

                detail_btn.click(
                    app.get_pr_detail,
                    inputs=[pr_id_input],
                    outputs=[pr_detail_info, file_reviews_table, issues_table],
                )

            # Tab 3: 统计分析
            with gr.TabItem("📊 统计分析"):
                gr.Markdown("## 仓库审查统计")

                with gr.Row():
                    stats_repo_filter = gr.Textbox(
                        label="仓库名称过滤", placeholder="输入仓库名称进行过滤（可选）"
                    )
                    stats_days = gr.Number(
                        label="统计天数", value=30, minimum=1, maximum=365
                    )
                    stats_btn = gr.Button("📈 生成统计", variant="primary")

                stats_info = gr.Markdown(label="统计信息")

                stats_btn.click(
                    app.get_repository_statistics,
                    inputs=[stats_repo_filter, stats_days],
                    outputs=[stats_info],
                )

            # Tab 4: 问题搜索
            with gr.TabItem("🔍 问题搜索"):
                gr.Markdown("## 搜索代码问题")

                with gr.Row():
                    keyword_input = gr.Textbox(
                        label="关键词", placeholder="输入问题标题或描述关键词"
                    )
                    severity_filter = gr.Dropdown(
                        label="严重程度",
                        choices=["all", "critical", "error", "warning", "info"],
                        value="all",
                    )
                    issue_limit = gr.Number(
                        label="显示数量", value=100, minimum=1, maximum=500
                    )
                    issue_search_btn = gr.Button("🔍 搜索问题", variant="primary")

                issues_search_table = gr.Dataframe(
                    label="问题搜索结果", interactive=False, wrap=True
                )

                issue_search_btn.click(
                    app.search_issues,
                    inputs=[keyword_input, severity_filter, issue_limit],
                    outputs=[issues_search_table],
                )

        # 页面加载时初始化
        interface.load(lambda: app.get_pr_reviews("", 20), outputs=[pr_reviews_table])

    return interface


if __name__ == "__main__":
    # 初始化数据库
    from backend.database import init_database

    init_database()

    interface = create_interface()
    interface.launch(
        server_name="0.0.0.0", server_port=7860, share=True, debug=False
    )
