from django import forms

from accounting.models import Account, JournalEntry


class JournalEntryForm(forms.Form):
    date = forms.DateField(
        input_formats=['%Y-%m-%d'],
        widget=forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
    )
    memo = forms.CharField(widget=forms.Textarea(attrs={'rows': 3}), required=False)


def account_choices(company):
    return Account.objects.filter(company=company, is_active=True).order_by('code')


def parse_journal_lines(company, post_data):
    account_ids = post_data.getlist('account')
    descriptions = post_data.getlist('description')
    debits = post_data.getlist('debit')
    credits = post_data.getlist('credit')
    lines = []
    for index, account_id in enumerate(account_ids):
        if not account_id:
            continue
        lines.append(
            {
                'account': Account.objects.get(company=company, pk=account_id),
                'description': descriptions[index] if index < len(descriptions) else '',
                'debit': debits[index] if index < len(debits) and debits[index] else '0',
                'credit': credits[index] if index < len(credits) and credits[index] else '0',
            }
        )
    return lines
