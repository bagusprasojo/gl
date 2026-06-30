import uuid
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from accounting.models import Account, JournalEntry


class CashBankAccount(models.Model):
    CASH = 'cash'
    BANK = 'bank'
    EWALLET = 'ewallet'

    ACCOUNT_KINDS = [
        (CASH, 'Kas'),
        (BANK, 'Bank'),
        (EWALLET, 'E-Wallet'),
    ]

    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, db_index=True)
    company = models.ForeignKey('companies.Company', on_delete=models.CASCADE, related_name='cashbank_accounts')
    name = models.CharField(max_length=160)
    account_kind = models.CharField(max_length=20, choices=ACCOUNT_KINDS, default=BANK)
    bank_name = models.CharField(max_length=120, blank=True)
    account_number = models.CharField(max_length=80, blank=True)
    account_holder = models.CharField(max_length=160, blank=True)
    account = models.ForeignKey(Account, on_delete=models.PROTECT, related_name='cashbank_accounts')
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['company', 'name'], name='unique_cashbank_account_name_per_company'),
            models.UniqueConstraint(
                fields=['company', 'account_number'],
                condition=~models.Q(account_number=''),
                name='unique_cashbank_account_number_per_company',
            ),
        ]
        ordering = ['company__name', 'name']

    def __str__(self):
        identifier = self.account_number or self.account.code
        return f'{self.name} ({identifier})'

    def clean(self):
        if self.account_id:
            if self.account.company_id != self.company_id:
                raise ValidationError('Account must belong to the same company.')
            if not self.account.is_cash_equivalent:
                raise ValidationError('Cash/bank account must map to a cash equivalent account.')
            if not self.account.is_postable:
                raise ValidationError('Cash/bank account must map to a postable account.')


class CashBankTransaction(models.Model):
    INCOMING = 'incoming'
    OUTGOING = 'outgoing'
    TRANSFER = 'transfer'
    DRAFT = 'draft'
    POSTED = 'posted'
    REVERSED = 'reversed'
    ADMIN_FEE_SOURCE = 'source'
    ADMIN_FEE_DESTINATION = 'destination'

    TRANSACTION_TYPES = [
        (INCOMING, 'Kas/Bank Masuk'),
        (OUTGOING, 'Kas/Bank Keluar'),
        (TRANSFER, 'Transfer'),
    ]
    STATUS_CHOICES = [
        (DRAFT, 'Draft'),
        (POSTED, 'Posted'),
        (REVERSED, 'Reversed'),
    ]
    ADMIN_FEE_BORNE_BY_CHOICES = [
        (ADMIN_FEE_SOURCE, 'Rekening sumber'),
        (ADMIN_FEE_DESTINATION, 'Rekening tujuan'),
    ]

    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, db_index=True)
    company = models.ForeignKey('companies.Company', on_delete=models.CASCADE, related_name='cashbank_transactions')
    number = models.CharField(max_length=30)
    date = models.DateField()
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPES)
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default=DRAFT)
    cash_account = models.ForeignKey(CashBankAccount, on_delete=models.PROTECT, null=True, blank=True, related_name='transactions')
    from_account = models.ForeignKey(CashBankAccount, on_delete=models.PROTECT, null=True, blank=True, related_name='outgoing_transfers')
    to_account = models.ForeignKey(CashBankAccount, on_delete=models.PROTECT, null=True, blank=True, related_name='incoming_transfers')
    counterparty = models.CharField(max_length=180, blank=True)
    memo = models.TextField(blank=True)
    amount = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal('0.00'))
    admin_fee = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal('0.00'))
    admin_fee_borne_by = models.CharField(max_length=20, choices=ADMIN_FEE_BORNE_BY_CHOICES, default=ADMIN_FEE_DESTINATION)
    admin_fee_account = models.ForeignKey(Account, on_delete=models.PROTECT, null=True, blank=True, related_name='cashbank_admin_fee_transactions')
    journal_entry = models.ForeignKey(JournalEntry, on_delete=models.PROTECT, null=True, blank=True, related_name='cashbank_transactions')
    reversed_transaction = models.ForeignKey('self', on_delete=models.PROTECT, null=True, blank=True, related_name='reversal_transactions')
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_cashbank_transactions')
    posted_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='posted_cashbank_transactions')
    posted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['company', 'number'], name='unique_cashbank_transaction_number_per_company')
        ]
        ordering = ['-date', '-id']

    def __str__(self):
        return self.number

    def clean(self):
        if self.amount < 0 or self.admin_fee < 0:
            raise ValidationError('Amount must not be negative.')
        if self.transaction_type in [self.INCOMING, self.OUTGOING] and not self.cash_account_id:
            raise ValidationError('Cash/bank account is required.')
        if self.transaction_type == self.TRANSFER:
            if not self.from_account_id or not self.to_account_id:
                raise ValidationError('Transfer requires source and destination accounts.')
            if self.from_account_id == self.to_account_id:
                raise ValidationError('Transfer source and destination must be different.')
            if self.admin_fee and not self.admin_fee_account_id:
                raise ValidationError('Admin fee account is required when admin fee is filled.')


class CashBankTransactionLine(models.Model):
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, db_index=True)
    transaction = models.ForeignKey(CashBankTransaction, on_delete=models.CASCADE, related_name='lines')
    account = models.ForeignKey(Account, on_delete=models.PROTECT, related_name='cashbank_transaction_lines')
    description = models.CharField(max_length=255, blank=True)
    amount = models.DecimalField(max_digits=18, decimal_places=2)

    class Meta:
        ordering = ['id']

    def clean(self):
        if self.amount <= 0:
            raise ValidationError('Line amount must be greater than zero.')
        if self.account_id:
            if self.account.company_id != self.transaction.company_id:
                raise ValidationError('Line account must belong to the same company.')
            if not self.account.is_postable:
                raise ValidationError('Line account must be postable.')
