"""
迁移：为 Project 模型添加 actual_end_date 字段，
并回填历史已完成项目的实际完成日期（用 updated_at.date()；无则退回 end_date）。

修复 industry_reports.ProjectDeliveryReportView 中
getattr(p, 'actual_end_date', None) 恒返回 None 导致
on_time/delayed/on_time_rate 始终为 0 的 bug。
"""

from django.db import migrations, models


def backfill_actual_end_date(apps, schema_editor):
    """回填历史已完成项目的实际完成日期。"""
    Project = apps.get_model('projects', 'Project')
    qs = Project.objects.filter(status='COMPLETED', actual_end_date__isnull=True)
    for project in qs:
        # 优先使用 updated_at（项目最后一次变更时间近似实际完成时间）
        if project.updated_at:
            project.actual_end_date = project.updated_at.date()
        elif project.end_date:
            # 退回计划交期：至少让报表能算出周期，避免除 0
            project.actual_end_date = project.end_date
        project.save(update_fields=['actual_end_date'])


class Migration(migrations.Migration):

    dependencies = [
        ('projects', '0018_alter_proposalreview_reviewers'),
    ]

    operations = [
        migrations.AddField(
            model_name='project',
            name='actual_end_date',
            field=models.DateField(blank=True, null=True, verbose_name='实际完成日期'),
        ),
        migrations.RunPython(backfill_actual_end_date, migrations.RunPython.noop),
    ]
