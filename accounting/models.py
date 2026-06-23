import uuid
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class Account(models.Model):
    ASSET = 'asset'
    LIABILITY = 'liability'
    EQUITY = 'equity'
    REVENUE = 'revenue'
    EXPENSE = 'expense'

    DEBIT = 'debit'
    CREDIT = 'credit'

    ACCOUNT_TYPES = [
        (ASSET, 'Aset'),
        (LIABILITY, 'Liabilitas'),
        (EQUITY, 'Ekuitas'),
        (REVENUE, 'Pendapatan'),
        (EXPENSE, 'Beban'),
    ]
    BALANCES = [(DEBIT, 'Debit'), (CREDIT, 'Kredit')]

    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, db_index=True)
    company = models.ForeignKey('companies.Company', on_delete=models.CASCADE, related_name='accounts')
    code = models.CharField(max_length=30)
    name = models.CharField(max_length=160)
    account_type = models.CharField(max_length=20, choices=ACCOUNT_TYPES)
    normal_balance = models.CharField(max_length=10, choices=BALANCES)
    parent = models.ForeignKey('self', on_delete=models.PROTECT, null=True, blank=True, related_name='children')
    is_cash_equivalent = models.BooleanField(default=False)
    is_postable = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['company', 'code'], name='unique_account_code_per_company')
        ]
        ordering = ['code']

    def __str__(self):
        return f'{self.code} - {self.name}'


class AccountingPeriod(models.Model):
    OPEN = 'open'
    CLOSED = 'closed'

    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, db_index=True)
    company = models.ForeignKey('companies.Company', on_delete=models.CASCADE, related_name='periods')
    year = models.PositiveIntegerField()
    month = models.PositiveSmallIntegerField()
    start_date = models.DateField()
    end_date = models.DateField()
    status = models.CharField(max_length=10, choices=[(OPEN, 'Open'), (CLOSED, 'Closed')], default=OPEN)
    closed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['company', 'year', 'month'], name='unique_period_per_company')
        ]
        ordering = ['year', 'month']

    def __str__(self):
        return f'{self.company} {self.year}-{self.month:02d}'


class AccountPeriodBalance(models.Model):
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, db_index=True)
    company = models.ForeignKey('companies.Company', on_delete=models.CASCADE, related_name='account_period_balances')
    account = models.ForeignKey(Account, on_delete=models.CASCADE, related_name='period_balances')
    period = models.ForeignKey(AccountingPeriod, on_delete=models.CASCADE, related_name='account_balances')
    opening_debit = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal('0.00'))
    opening_credit = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal('0.00'))
    movement_debit = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal('0.00'))
    movement_credit = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal('0.00'))
    closing_debit = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal('0.00'))
    closing_credit = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal('0.00'))
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['company', 'account', 'period'], name='unique_account_period_balance')
        ]
        ordering = ['period__year', 'period__month', 'account__code']

    def __str__(self):
        return f'{self.period} - {self.account}'


class JournalEntry(models.Model):
    DRAFT = 'draft'
    POSTED = 'posted'
    REVERSED = 'reversed'

    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, db_index=True)
    company = models.ForeignKey('companies.Company', on_delete=models.CASCADE, related_name='journal_entries')
    period = models.ForeignKey(AccountingPeriod, on_delete=models.PROTECT, related_name='journal_entries')
    number = models.CharField(max_length=30)
    date = models.DateField()
    memo = models.TextField(blank=True)
    status = models.CharField(
        max_length=12,
        choices=[(DRAFT, 'Draft'), (POSTED, 'Posted'), (REVERSED, 'Reversed')],
        default=DRAFT,
    )
    source_module = models.CharField(max_length=80, default='core')
    source_type = models.CharField(max_length=80, default='journal')
    source_id = models.CharField(max_length=80, blank=True)
    reversed_entry = models.ForeignKey('self', on_delete=models.PROTECT, null=True, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_journals')
    posted_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='posted_journals')
    posted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['company', 'number'], name='unique_journal_number_per_company')
        ]
        ordering = ['-date', '-id']

    def __str__(self):
        return self.number

    @property
    def total_debit(self):
        return self.lines.aggregate(total=models.Sum('debit'))['total'] or Decimal('0')

    @property
    def total_credit(self):
        return self.lines.aggregate(total=models.Sum('credit'))['total'] or Decimal('0')

    def clean(self):
        if self.period_id and self.period.status == AccountingPeriod.CLOSED:
            raise ValidationError('Cannot change journal in a closed period.')


class JournalLine(models.Model):
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, db_index=True)
    entry = models.ForeignKey(JournalEntry, on_delete=models.CASCADE, related_name='lines')
    account = models.ForeignKey(Account, on_delete=models.PROTECT, related_name='journal_lines')
    description = models.CharField(max_length=255, blank=True)
    debit = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal('0.00'))
    credit = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal('0.00'))

    class Meta:
        ordering = ['id']

    def clean(self):
        if self.debit < 0 or self.credit < 0:
            raise ValidationError('Debit and credit must not be negative.')
        if self.debit and self.credit:
            raise ValidationError('A journal line cannot have both debit and credit.')
        if not self.debit and not self.credit:
            raise ValidationError('A journal line must have debit or credit.')
        if self.account_id and self.entry_id and self.account.company_id != self.entry.company_id:
            raise ValidationError('Account must belong to the same company as the journal.')
        if self.account_id and not self.account.is_postable:
            raise ValidationError('Account is not postable.')

class FiscalYearClosing(models.Model):
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, db_index=True)
    company = models.ForeignKey('companies.Company', on_delete=models.CASCADE, related_name='fiscal_year_closings')
    fiscal_year = models.PositiveIntegerField()
    start_date = models.DateField()
    end_date = models.DateField()
    closing_entry = models.ForeignKey(JournalEntry, on_delete=models.PROTECT, related_name='fiscal_year_closings')
    closed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    closed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['company', 'fiscal_year'], name='unique_fiscal_year_closing_per_company')
        ]
        ordering = ['-fiscal_year']

    def __str__(self):
        return f'{self.company} FY {self.fiscal_year}'

class FinancialReportTemplate(models.Model):
    INCOME_STATEMENT = 'income_statement'
    BALANCE_SHEET = 'balance_sheet'

    REPORT_TYPES = [
        (INCOME_STATEMENT, 'Laba Rugi'),
        (BALANCE_SHEET, 'Neraca'),
    ]

    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, db_index=True)
    company = models.ForeignKey('companies.Company', on_delete=models.CASCADE, related_name='financial_report_templates')
    report_type = models.CharField(max_length=40, choices=REPORT_TYPES)
    name = models.CharField(max_length=160)
    is_default = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'report_type', 'name'],
                name='unique_report_template_name_per_company_type',
            )
        ]
        ordering = ['company__name', 'report_type', 'name']

    def __str__(self):
        return f'{self.company} - {self.name}'


class FinancialReportLine(models.Model):
    HEADING = 'heading'
    ACCOUNT_GROUP = 'account_group'
    FORMULA = 'formula'
    BLANK = 'blank'

    LINE_TYPES = [
        (HEADING, 'Heading'),
        (ACCOUNT_GROUP, 'Account group'),
        (FORMULA, 'Formula'),
        (BLANK, 'Blank'),
    ]

    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, db_index=True)
    template = models.ForeignKey(FinancialReportTemplate, on_delete=models.CASCADE, related_name='lines')
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='children')
    sort_order = models.PositiveIntegerField(default=0)
    code = models.SlugField(max_length=80)
    label = models.CharField(max_length=180, blank=True)
    line_type = models.CharField(max_length=30, choices=LINE_TYPES)
    indent_level = models.PositiveSmallIntegerField(default=0)
    is_bold = models.BooleanField(default=False)
    show_when_zero = models.BooleanField(default=True)
    accounts = models.ManyToManyField(Account, blank=True, related_name='report_lines')
    formula = models.CharField(max_length=255, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['template', 'code'], name='unique_report_line_code_per_template')
        ]
        ordering = ['template', 'sort_order', 'id']

    def __str__(self):
        return f'{self.template} - {self.code}'


class CashFlowCategory(models.Model):
    OPERATING = 'operating'
    INVESTING = 'investing'
    FINANCING = 'financing'

    ACTIVITY_TYPES = [
        (OPERATING, 'Operasi'),
        (INVESTING, 'Investasi'),
        (FINANCING, 'Pendanaan'),
    ]

    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, db_index=True)
    company = models.ForeignKey('companies.Company', on_delete=models.CASCADE, related_name='cash_flow_categories')
    code = models.SlugField(max_length=80)
    name = models.CharField(max_length=180)
    activity_type = models.CharField(max_length=20, choices=ACTIVITY_TYPES)
    sort_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['company', 'code'], name='unique_cash_flow_category_code_per_company')
        ]
        ordering = ['company__name', 'activity_type', 'sort_order', 'name']

    def __str__(self):
        return f'{self.company} - {self.name}'


class AccountCashFlowMapping(models.Model):
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, db_index=True)
    company = models.ForeignKey('companies.Company', on_delete=models.CASCADE, related_name='account_cash_flow_mappings')
    account = models.ForeignKey(Account, on_delete=models.CASCADE, related_name='cash_flow_mappings')
    category = models.ForeignKey(CashFlowCategory, on_delete=models.PROTECT, related_name='account_mappings')

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['company', 'account'], name='unique_cash_flow_mapping_per_account')
        ]
        ordering = ['company__name', 'account__code']

    def __str__(self):
        return f'{self.account} -> {self.category}'

# Create your models here.
