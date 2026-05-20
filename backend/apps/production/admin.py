from django.contrib import admin

from .models import (
    DebugCheckItem,
    DebugRecord,
    InspectionItem,
    ProductionLog,
    ProductionPlan,
    ProductionPlanProcess,
    ProductionProcess,
    QualityInspection,
)


@admin.register(ProductionProcess)
class ProductionProcessAdmin(admin.ModelAdmin):
    list_display = ['process_no', 'name', 'project', 'process_type', 'sequence', 'assignee']
    list_filter = ['process_type', 'project']
    search_fields = ['process_no', 'name']


@admin.register(ProductionPlan)
class ProductionPlanAdmin(admin.ModelAdmin):
    list_display = ['plan_no', 'title', 'project', 'status', 'progress_percent', 'planned_start', 'planned_end']
    list_filter = ['status', 'project']
    search_fields = ['plan_no', 'title']


@admin.register(ProductionPlanProcess)
class ProductionPlanProcessAdmin(admin.ModelAdmin):
    list_display = ['plan', 'process', 'status', 'progress_percent', 'planned_start', 'planned_end']
    list_filter = ['status']


@admin.register(ProductionLog)
class ProductionLogAdmin(admin.ModelAdmin):
    list_display = ['plan_process', 'log_date', 'operator', 'work_hours', 'progress_percent']
    list_filter = ['log_date']


@admin.register(DebugRecord)
class DebugRecordAdmin(admin.ModelAdmin):
    list_display = ['record_no', 'title', 'project', 'debug_type', 'status', 'result', 'debugger']
    list_filter = ['debug_type', 'status', 'result', 'project']
    search_fields = ['record_no', 'title']


@admin.register(DebugCheckItem)
class DebugCheckItemAdmin(admin.ModelAdmin):
    list_display = ['debug_record', 'sequence', 'item_name', 'result']
    list_filter = ['result']


@admin.register(QualityInspection)
class QualityInspectionAdmin(admin.ModelAdmin):
    list_display = ['inspection_no', 'title', 'project', 'inspection_type', 'status', 'result', 'inspector']
    list_filter = ['inspection_type', 'status', 'result', 'project']
    search_fields = ['inspection_no', 'title']


@admin.register(InspectionItem)
class InspectionItemAdmin(admin.ModelAdmin):
    list_display = ['inspection', 'sequence', 'item_name', 'result']
    list_filter = ['result']
