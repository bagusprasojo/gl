import uuid

from django.db import models


class ModuleRegistry(models.Model):
    CORE = 'core'
    ADDON = 'addon'

    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, db_index=True)
    company = models.ForeignKey('companies.Company', on_delete=models.CASCADE, related_name='modules')
    key = models.SlugField(max_length=80)
    name = models.CharField(max_length=120)
    module_type = models.CharField(max_length=20, choices=[(CORE, 'Core'), (ADDON, 'Add-on')], default=ADDON)
    is_active = models.BooleanField(default=False)
    activated_at = models.DateTimeField(null=True, blank=True)
    deactivated_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['company', 'key'], name='unique_module_per_company')
        ]
        ordering = ['company__name', 'name']

    def __str__(self):
        return f'{self.company} - {self.name}'

# Create your models here.
