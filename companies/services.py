from datetime import date

from django.db import transaction

from accounts.models import Role
from accounting.services import (
    create_default_accounts,
    ensure_year_periods,
    seed_default_cash_flow_categories,
    seed_default_report_templates,
)
from companies.models import Company
from modules.services import seed_default_modules


DEFAULT_ROLES = [
    (Role.OWNER, 'Owner', 'Pemilik usaha dengan akses penuh.'),
    (Role.ADMIN, 'Admin', 'Mengelola pengguna dan konfigurasi.'),
    (Role.ACCOUNTANT, 'Accountant', 'Membuat jurnal, posting, closing, dan laporan.'),
    (Role.VIEWER, 'Viewer', 'Melihat data dan laporan.'),
]


@transaction.atomic
def create_company(name, legal_name='', tax_number='', address='', base_currency='IDR'):
    company = Company.objects.create(
        name=name,
        legal_name=legal_name,
        tax_number=tax_number,
        address=address,
        base_currency=base_currency or 'IDR',
    )
    for key, role_name, description in DEFAULT_ROLES:
        Role.objects.create(company=company, key=key, name=role_name, description=description)
    create_default_accounts(company)
    ensure_year_periods(company, date.today().year)
    seed_default_report_templates(company)
    seed_default_cash_flow_categories(company)
    seed_default_modules(company)
    return company
