from django.contrib import admin

from accounting.models import (
    Account,
    AccountCashFlowMapping,
    AccountingPeriod,
    AccountPeriodBalance,
    CashFlowCategory,
    FinancialReportLine,
    FinancialReportTemplate,
    FiscalYearClosing,
    JournalEntry,
    JournalLine,
)


@admin.register(Account)
class AccountAdmin(admin.ModelAdmin):
    list_display = ('company', 'code', 'name', 'account_type', 'normal_balance', 'is_cash_equivalent', 'is_postable', 'is_active')
    list_filter = ('company', 'account_type', 'normal_balance', 'is_cash_equivalent', 'is_postable')
    search_fields = ('code', 'name')


class JournalLineInline(admin.TabularInline):
    model = JournalLine
    extra = 0


@admin.register(JournalEntry)
class JournalEntryAdmin(admin.ModelAdmin):
    list_display = ('company', 'number', 'date', 'status', 'source_module', 'posted_at')
    list_filter = ('company', 'status', 'source_module')
    search_fields = ('number', 'memo', 'source_id')
    inlines = [JournalLineInline]


@admin.register(AccountingPeriod)
class AccountingPeriodAdmin(admin.ModelAdmin):
    list_display = ('company', 'year', 'month', 'status', 'closed_at')
    list_filter = ('company', 'year', 'status')


@admin.register(AccountPeriodBalance)
class AccountPeriodBalanceAdmin(admin.ModelAdmin):
    list_display = (
        'company',
        'period',
        'account',
        'opening_debit',
        'opening_credit',
        'movement_debit',
        'movement_credit',
        'closing_debit',
        'closing_credit',
    )
    list_filter = ('company', 'period__year', 'period__month')
    search_fields = ('account__code', 'account__name')


class FinancialReportLineInline(admin.TabularInline):
    model = FinancialReportLine
    extra = 0
    fields = ('sort_order', 'code', 'label', 'line_type', 'indent_level', 'is_bold', 'show_when_zero', 'formula')


@admin.register(FinancialReportTemplate)
class FinancialReportTemplateAdmin(admin.ModelAdmin):
    list_display = ('company', 'report_type', 'name', 'is_default', 'is_active')
    list_filter = ('company', 'report_type', 'is_default', 'is_active')
    search_fields = ('name',)
    inlines = [FinancialReportLineInline]


@admin.register(FinancialReportLine)
class FinancialReportLineAdmin(admin.ModelAdmin):
    list_display = ('template', 'sort_order', 'code', 'label', 'line_type', 'indent_level', 'is_bold')
    list_filter = ('template__company', 'template__report_type', 'line_type', 'is_bold')
    search_fields = ('code', 'label')


@admin.register(CashFlowCategory)
class CashFlowCategoryAdmin(admin.ModelAdmin):
    list_display = ('company', 'code', 'name', 'activity_type', 'sort_order', 'is_active')
    list_filter = ('company', 'activity_type', 'is_active')
    search_fields = ('code', 'name')


@admin.register(AccountCashFlowMapping)
class AccountCashFlowMappingAdmin(admin.ModelAdmin):
    list_display = ('company', 'account', 'category')
    list_filter = ('company', 'category__activity_type', 'category')
    search_fields = ('account__code', 'account__name', 'category__code', 'category__name')

@admin.register(FiscalYearClosing)
class FiscalYearClosingAdmin(admin.ModelAdmin):
    list_display = ('company', 'fiscal_year', 'start_date', 'end_date', 'closing_entry', 'closed_at')
    list_filter = ('company', 'fiscal_year')
    search_fields = ('closing_entry__number',)
# Register your models here.
