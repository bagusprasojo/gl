from django.contrib import admin

from cashbank.models import CashBankAccount, CashBankTransaction, CashBankTransactionLine


@admin.register(CashBankAccount)
class CashBankAccountAdmin(admin.ModelAdmin):
    list_display = ('company', 'name', 'account', 'is_active')
    list_filter = ('company', 'is_active')
    search_fields = ('name', 'account__code', 'account__name')


class CashBankTransactionLineInline(admin.TabularInline):
    model = CashBankTransactionLine
    extra = 0


@admin.register(CashBankTransaction)
class CashBankTransactionAdmin(admin.ModelAdmin):
    list_display = ('company', 'number', 'date', 'transaction_type', 'status', 'amount', 'journal_entry')
    list_filter = ('company', 'transaction_type', 'status')
    search_fields = ('number', 'memo', 'counterparty')
    inlines = [CashBankTransactionLineInline]