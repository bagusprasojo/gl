import uuid

from django.conf import settings
from django.db import models


class AuditLog(models.Model):
    CREATE = 'create'
    UPDATE = 'update'
    DELETE = 'delete'
    POST = 'post'
    REVERSE = 'reverse'
    CLOSE_PERIOD = 'close_period'
    CLOSE_FISCAL_YEAR = 'close_fiscal_year'
    ACTIVATE_MODULE = 'activate_module'
    DEACTIVATE_MODULE = 'deactivate_module'

    ACTION_CHOICES = [
        (CREATE, 'Create'),
        (UPDATE, 'Update'),
        (DELETE, 'Delete'),
        (POST, 'Post'),
        (REVERSE, 'Reverse'),
        (CLOSE_PERIOD, 'Close period'),
        (CLOSE_FISCAL_YEAR, 'Close fiscal year'),
        (ACTIVATE_MODULE, 'Activate module'),
        (DEACTIVATE_MODULE, 'Deactivate module'),
    ]

    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, db_index=True)
    company = models.ForeignKey('companies.Company', on_delete=models.CASCADE, related_name='audit_logs')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    action = models.CharField(max_length=40, choices=ACTION_CHOICES)
    model_name = models.CharField(max_length=120)
    object_id = models.CharField(max_length=80)
    message = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.created_at:%Y-%m-%d %H:%M} {self.action} {self.model_name}#{self.object_id}'

# Create your models here.
