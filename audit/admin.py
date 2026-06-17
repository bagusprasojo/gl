from django.contrib import admin

from audit.models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'company', 'user', 'action', 'model_name', 'object_id', 'message')
    list_filter = ('company', 'action', 'model_name')
    search_fields = ('object_id', 'message')
    readonly_fields = ('company', 'user', 'action', 'model_name', 'object_id', 'message', 'created_at')

# Register your models here.
