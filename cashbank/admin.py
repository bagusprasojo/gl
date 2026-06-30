from django.contrib import admin

from cashbank.models import CashBankAccount, CashBankTransaction, CashBankTransactionLine


@admin.register(CashBankAccount)
class CashBankAccountAdmin(admin.ModelAdmin):
    list_display = ('company', 'name', 'account_kind', 'bank_name', 'account_number', 'account', 'is_active')
    list_filter = ('company', 'account_kind', 'is_active')
    search_fields = ('name', 'bank_name', 'account_number', 'account_holder', 'account__code', 'account__name')


class CashBankTransactionLineInline(admin.TabularInline):
    model = CashBankTransactionLine
    extra = 0


@admin.register(CashBankTransaction)
class CashBankTransactionAdmin(admin.ModelAdmin):
    list_display = ('company', 'number', 'date', 'transaction_type', 'status', 'amount', 'journal_entry')
    list_filter = ('company', 'transaction_type', 'status')
    search_fields = ('number', 'memo', 'counterparty')
    inlines = [CashBankTransactionLineInline]