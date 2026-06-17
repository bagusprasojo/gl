import uuid

from django.contrib.auth.models import AbstractUser
from django.db import models


class Role(models.Model):
    OWNER = 'owner'
    ADMIN = 'admin'
    ACCOUNTANT = 'accountant'
    VIEWER = 'viewer'

    DEFAULT_KEYS = [OWNER, ADMIN, ACCOUNTANT, VIEWER]

    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, db_index=True)
    company = models.ForeignKey('companies.Company', on_delete=models.CASCADE, related_name='roles')
    key = models.SlugField(max_length=40)
    name = models.CharField(max_length=80)
    description = models.CharField(max_length=255, blank=True)
    is_system = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['company', 'key'], name='unique_role_per_company')
        ]
        ordering = ['company__name', 'name']

    def __str__(self):
        return f'{self.company} - {self.name}'


class User(AbstractUser):
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, db_index=True)
    company = models.ForeignKey(
        'companies.Company',
        on_delete=models.PROTECT,
        related_name='users',
        null=True,
        blank=True,
    )
    role = models.ForeignKey(
        Role,
        on_delete=models.PROTECT,
        related_name='users',
        null=True,
        blank=True,
    )

    def save(self, *args, **kwargs):
        if self.role and self.role.company_id != self.company_id:
            raise ValueError('Role must belong to the same company as the user.')
        super().save(*args, **kwargs)

# Create your models here.
