"""
Bug跟踪系统数据库迁移
"""
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('projects', '0004_aftersales'),
    ]

    operations = [
        # Bug表
        migrations.CreateModel(
            name='Bug',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='更新时间')),
                ('is_deleted', models.BooleanField(default=False, verbose_name='已删除')),
                ('deleted_at', models.DateTimeField(blank=True, null=True, verbose_name='删除时间')),
                ('bug_number', models.CharField(max_length=50, unique=True, verbose_name='Bug编号')),
                ('title', models.CharField(max_length=200, verbose_name='标题')),
                ('description', models.TextField(verbose_name='详细描述')),
                ('module', models.CharField(blank=True, max_length=100, verbose_name='模块/组件')),
                ('severity', models.CharField(choices=[('CRITICAL', '致命'), ('MAJOR', '严重'), ('NORMAL', '一般'), ('MINOR', '轻微'), ('SUGGESTION', '建议')], default='NORMAL', max_length=20, verbose_name='严重程度')),
                ('priority', models.CharField(choices=[('P0', 'P0-紧急'), ('P1', 'P1-高'), ('P2', 'P2-中'), ('P3', 'P3-低')], default='P2', max_length=10, verbose_name='优先级')),
                ('bug_type', models.CharField(choices=[('FUNCTION', '功能问题'), ('PERFORMANCE', '性能问题'), ('UI', '界面问题'), ('SECURITY', '安全问题'), ('DATA', '数据问题'), ('COMPATIBILITY', '兼容性问题'), ('OTHER', '其他')], default='FUNCTION', max_length=20, verbose_name='Bug类型')),
                ('status', models.CharField(choices=[('NEW', '新建'), ('CONFIRMED', '已确认'), ('IN_PROGRESS', '处理中'), ('RESOLVED', '已解决'), ('CLOSED', '已关闭'), ('REOPENED', '重新打开'), ('SUSPENDED', '挂起'), ('CANNOT_REPRODUCE', '无法复现'), ('BY_DESIGN', '设计如此'), ('DUPLICATE', '重复')], default='NEW', max_length=20, verbose_name='状态')),
                ('resolution', models.CharField(blank=True, choices=[('FIXED', '已修复'), ('WONT_FIX', '不予修复'), ('DUPLICATE', '重复问题'), ('INVALID', '无效问题'), ('CANNOT_REPRODUCE', '无法复现'), ('BY_DESIGN', '设计如此')], max_length=20, verbose_name='解决方式')),
                ('solution', models.TextField(blank=True, verbose_name='解决说明')),
                ('resolved_at', models.DateTimeField(blank=True, null=True, verbose_name='解决时间')),
                ('closed_at', models.DateTimeField(blank=True, null=True, verbose_name='关闭时间')),
                ('environment', models.CharField(blank=True, max_length=50, verbose_name='环境')),
                ('version', models.CharField(blank=True, max_length=50, verbose_name='版本')),
                ('assignee', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='assigned_bugs', to=settings.AUTH_USER_MODEL, verbose_name='处理人')),
                ('duplicate_of', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='duplicates', to='projects.bug', verbose_name='重复于')),
                ('project', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='bugs', to='projects.project', verbose_name='所属项目')),
                ('reporter', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='reported_bugs', to=settings.AUTH_USER_MODEL, verbose_name='报告人')),
                ('task', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='bugs', to='projects.projecttask', verbose_name='关联任务')),
            ],
            options={
                'verbose_name': 'Bug',
                'verbose_name_plural': 'Bug',
                'db_table': 'bug',
                'ordering': ['-created_at'],
            },
        ),
        # Bug评论表
        migrations.CreateModel(
            name='BugComment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='更新时间')),
                ('is_deleted', models.BooleanField(default=False, verbose_name='已删除')),
                ('deleted_at', models.DateTimeField(blank=True, null=True, verbose_name='删除时间')),
                ('content', models.TextField(verbose_name='评论内容')),
                ('bug', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='comments', to='projects.bug', verbose_name='Bug')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='bug_comments', to=settings.AUTH_USER_MODEL, verbose_name='评论人')),
            ],
            options={
                'verbose_name': 'Bug评论',
                'verbose_name_plural': 'Bug评论',
                'db_table': 'bug_comment',
                'ordering': ['created_at'],
            },
        ),
        # Bug附件表
        migrations.CreateModel(
            name='BugAttachment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='更新时间')),
                ('is_deleted', models.BooleanField(default=False, verbose_name='已删除')),
                ('deleted_at', models.DateTimeField(blank=True, null=True, verbose_name='删除时间')),
                ('file', models.FileField(upload_to='bugs/%Y/%m/', verbose_name='文件')),
                ('filename', models.CharField(max_length=255, verbose_name='文件名')),
                ('file_size', models.IntegerField(default=0, verbose_name='文件大小')),
                ('bug', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='attachments', to='projects.bug', verbose_name='Bug')),
                ('uploaded_by', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='bug_attachments', to=settings.AUTH_USER_MODEL, verbose_name='上传人')),
            ],
            options={
                'verbose_name': 'Bug附件',
                'verbose_name_plural': 'Bug附件',
                'db_table': 'bug_attachment',
                'ordering': ['-created_at'],
            },
        ),
        # Bug变更历史表
        migrations.CreateModel(
            name='BugHistory',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='更新时间')),
                ('is_deleted', models.BooleanField(default=False, verbose_name='已删除')),
                ('deleted_at', models.DateTimeField(blank=True, null=True, verbose_name='删除时间')),
                ('field_name', models.CharField(max_length=50, verbose_name='变更字段')),
                ('field_label', models.CharField(max_length=50, verbose_name='字段名称')),
                ('old_value', models.TextField(blank=True, verbose_name='原值')),
                ('new_value', models.TextField(blank=True, verbose_name='新值')),
                ('bug', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='histories', to='projects.bug', verbose_name='Bug')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='bug_histories', to=settings.AUTH_USER_MODEL, verbose_name='操作人')),
            ],
            options={
                'verbose_name': 'Bug变更历史',
                'verbose_name_plural': 'Bug变更历史',
                'db_table': 'bug_history',
                'ordering': ['-created_at'],
            },
        ),
    ]

