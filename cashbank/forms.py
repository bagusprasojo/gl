from django import forms

from accounting.models import Account
from cashbank.models import CashBankAccount, CashBankTransaction


class CashBankAccountForm(forms.Form):
    name = forms.CharField(max_length=160)
    account = forms.ModelChoiceField(queryset=Account.objects.none())

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
    from_account = forms.ModelChoiceField(queryset=CashBankAccount.objects.none())
    to_account = forms.ModelChoiceField(queryset=CashBankAccount.objects.none())
    amount = forms.DecimalField(max_digits=18, decimal_places=2)
    admin_fee = forms.DecimalField(max_digits=18, decimal_places=2, required=False)
    admin_fee_account = forms.ModelChoiceField(queryset=Account.objects.none(), required=False)
    memo = forms.CharField(widget=forms.Textarea(attrs={'rows': 3}), required=False)

    def __init__(self, company, *args, **kwargs):
        super().__init__(*args, **kwargs)
        cash_accounts = CashBankAccount.objects.filter(company=company, is_active=True).order_by('name')
        self.fields['from_account'].queryset = cash_accounts
        self.fields['to_account'].queryset = cash_accounts
        self.fields['admin_fee_account'].queryset = Account.objects.filter(
            company=company,
            is_active=True,
            is_postable=True,
        ).order_by('code')


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