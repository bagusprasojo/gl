import uuid

from django.db import models


class Company(models.Model):
    MONTH_CHOICES = [
        (1, 'Januari'),
        (2, 'Februari'),
        (3, 'Maret'),
        (4, 'April'),
        (5, 'Mei'),
        (6, 'Juni'),
        (7, 'Juli'),
        (8, 'Agustus'),
        (9, 'September'),
        (10, 'Oktober'),
        (11, 'November'),
        (12, 'Desember'),
    ]

    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, db_index=True)
    name = models.CharField(max_length=180)
    legal_name = models.CharField(max_length=220, blank=True)
    tax_number = models.CharField(max_length=60, blank=True)
    address = models.TextField(blank=True)
    base_currency = models.CharField(max_length=3, default='IDR')
    fiscal_year_start_month = models.PositiveSmallIntegerField(choices=MONTH_CHOICES, default=1)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name

# Create your models here.
