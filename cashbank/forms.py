from decimal import Decimal

from django import forms

from accounting.models import Account
from cashbank.models import CashBankAccount, CashBankTransaction


class CashBankAccountForm(forms.Form):
    name = forms.CharField(max_length=160)
    account_kind = forms.ChoiceField(choices=CashBankAccount.ACCOUNT_KINDS)
    bank_name = forms.CharField(max_length=120, required=False)
    account_number = forms.CharField(max_length=80, required=False)
    account_holder = forms.CharField(max_length=160, required=False)
    account = forms.ModelChoiceField(queryset=Account.objects.none())
    notes = forms.CharField(widget=forms.Textarea(attrs={'rows': 3}), required=False)

    def __init__(self, company, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['account'].queryset = Account.objects.filter(
            company=company,
            is_active=True,
            is_postable=True,
            is_cash_equivalent=True,
        ).order_by('code')


class CashBankTransactionForm(forms.Form):
    date = forms.DateField(input_formats=['%Y-%m-%d'], widget=forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'))
    cash_account = forms.ModelChoiceField(queryset=CashBankAccount.objects.none())
    counterparty = forms.CharField(max_length=180, required=False)
    memo = forms.CharField(widget=forms.Textarea(attrs={'rows': 3}), required=False)

    def __init__(self, company, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['cash_account'].queryset = CashBankAccount.objects.filter(company=company, is_active=True).order_by('name')


class CashBankTransferForm(forms.Form):
    date = forms.DateField(input_formats=['%Y-%m-%d'], widget=forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'))
    from_account = forms.ModelChoiceField(queryset=CashBankAccount.objects.none(), empty_label='Pilih rekening asal')
    to_account = forms.ModelChoiceField(queryset=CashBankAccount.objects.none(), empty_label='Pilih rekening tujuan')
    amount = forms.DecimalField(max_digits=18, decimal_places=2, min_value=Decimal('0.01'))
    admin_fee = forms.DecimalField(max_digits=18, decimal_places=2, min_value=Decimal('0.00'), required=False)
    admin_fee_borne_by = forms.ChoiceField(choices=CashBankTransaction.ADMIN_FEE_BORNE_BY_CHOICES)
    admin_fee_account = forms.ModelChoiceField(queryset=Account.objects.none(), required=False, empty_label='Pilih akun beban')
    memo = forms.CharField(widget=forms.Textarea(attrs={'rows': 3}), required=False)
    def __init__(self, company, *args, **kwargs):
        super().__init__(*args, **kwargs)
        cash_accounts = CashBankAccount.objects.filter(company=company, is_active=True).select_related('account').order_by('name')
        self.fields['from_account'].queryset = cash_accounts
        self.fields['to_account'].queryset = cash_accounts
        self.fields['admin_fee_account'].queryset = Account.objects.filter(
            company=company,
            account_type=Account.EXPENSE,
            is_active=True,
            is_postable=True,
            is_cash_equivalent=False,
        ).order_by('code')
        self.fields['from_account'].label_from_instance = self._cash_account_label
        self.fields['to_account'].label_from_instance = self._cash_account_label

    @staticmethod
    def _cash_account_label(account):
        details = [account.get_account_kind_display()]
        if account.bank_name:
            details.append(account.bank_name)
        if account.account_number:
            details.append(account.account_number)
        return f"{account.name} - {' / '.join(details)} ({account.account.code})"

    def clean(self):
        cleaned_data = super().clean()
        from_account = cleaned_data.get('from_account')
        to_account = cleaned_data.get('to_account')
        amount = cleaned_data.get('amount') or Decimal('0')
        admin_fee = cleaned_data.get('admin_fee') or Decimal('0')
        admin_fee_account = cleaned_data.get('admin_fee_account')
        if not cleaned_data.get('admin_fee_borne_by'):
            cleaned_data['admin_fee_borne_by'] = CashBankTransaction.ADMIN_FEE_DESTINATION

        if from_account and to_account and from_account.pk == to_account.pk:
            raise forms.ValidationError('Rekening asal dan tujuan harus berbeda.')
        if admin_fee and not admin_fee_account:
            self.add_error('admin_fee_account', 'Akun biaya admin wajib dipilih jika biaya admin diisi.')
        if amount and admin_fee >= amount:
            self.add_error('admin_fee', 'Biaya admin harus lebih kecil dari nilai transfer.')
        cleaned_data['admin_fee'] = admin_fee
        return cleaned_data


def parse_transaction_lines(company, post_data):
    account_ids = post_data.getlist('account')
    descriptions = post_data.getlist('description')
    amounts = post_data.getlist('amount')
    lines = []
    for index, account_id in enumerate(account_ids):
        if not account_id:
            continue
        amount = amounts[index] if index < len(amounts) and amounts[index] else '0'
        lines.append({
            'account': Account.objects.get(company=company, pk=account_id, is_postable=True, is_cash_equivalent=False),
            'description': descriptions[index] if index < len(descriptions) else '',
            'amount': amount,
        })
    return lines
