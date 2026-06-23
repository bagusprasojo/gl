from datetime import date

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render

from accounting.forms import account_choices
from cashbank.forms import CashBankAccountForm, CashBankTransactionForm, CashBankTransferForm, parse_transaction_lines
from cashbank.models import CashBankAccount, CashBankTransaction
from cashbank.services import (
    cashbank_book,
    cashbank_account_choices,
    counter_account_choices,
    create_cashbank_account,
    create_cashbank_transaction,
    create_transfer_transaction,
    delete_cashbank_transaction,
    ensure_module_active,
    is_module_active,
    post_cashbank_transaction,
    reverse_cashbank_transaction,
    update_cashbank_transaction,
    update_transfer_transaction,
)


def _company(request):
    return request.user.company


def _date_filters(request):
    start = request.GET.get('start_date')
    end = request.GET.get('end_date')
    return (
        date.fromisoformat(start) if start else None,
        date.fromisoformat(end) if end else None,
    )


def _guard_module(request):
    ensure_module_active(_company(request))


def _handle_module_error(request, exc):
    messages.error(request, exc.messages[0] if hasattr(exc, 'messages') else str(exc))
    return redirect('accounting:module_list')


@login_required
def account_list(request):
    try:
        _guard_module(request)
    except ValidationError as exc:
        return _handle_module_error(request, exc)
    accounts = CashBankAccount.objects.filter(company=_company(request)).select_related('account').order_by('name')
    return render(request, 'cashbank/account_list.html', {'accounts': accounts})


@login_required
def account_create(request):
    company = _company(request)
    try:
        _guard_module(request)
    except ValidationError as exc:
        return _handle_module_error(request, exc)
    if request.method == 'POST':
        form = CashBankAccountForm(company, request.POST)
        if form.is_valid():
            try:
                account = create_cashbank_account(company, form.cleaned_data['name'], form.cleaned_data['account'], user=request.user)
                messages.success(request, f'Rekening {account.name} dibuat.')
                return redirect('cashbank:account_list')
            except ValidationError as exc:
                messages.error(request, exc.messages[0])
    else:
        form = CashBankAccountForm(company)
    return render(request, 'cashbank/account_form.html', {'form': form})


@login_required
def transaction_list(request):
    try:
        _guard_module(request)
    except ValidationError as exc:
        return _handle_module_error(request, exc)
    start, end = _date_filters(request)
    status = request.GET.get('status', '')
    transactions = CashBankTransaction.objects.filter(company=_company(request)).select_related('cash_account', 'from_account', 'to_account', 'journal_entry').order_by('-date', '-id')
    if start:
        transactions = transactions.filter(date__gte=start)
    if end:
        transactions = transactions.filter(date__lte=end)
    if status in [CashBankTransaction.DRAFT, CashBankTransaction.POSTED, CashBankTransaction.REVERSED]:
        transactions = transactions.filter(status=status)
    paginator = Paginator(transactions, 20)
    page_obj = paginator.get_page(request.GET.get('page'))
    query_params = request.GET.copy()
    query_params.pop('page', None)
    return render(
        request,
        'cashbank/transaction_list.html',
        {
            'transactions': page_obj.object_list,
            'page_obj': page_obj,
            'query_string': query_params.urlencode(),
            'status_choices': CashBankTransaction.STATUS_CHOICES,
        },
    )


def _transaction_initial_lines(transaction_obj=None):
    if not transaction_obj:
        return [{'id': 0, 'account': '', 'description': '', 'amount': ''}]
    return [
        {'id': line.pk, 'account': str(line.account_id), 'description': line.description, 'amount': str(line.amount)}
        for line in transaction_obj.lines.select_related('account')
    ]


@login_required
def transaction_create(request, transaction_type):
    company = _company(request)
    try:
        _guard_module(request)
    except ValidationError as exc:
        return _handle_module_error(request, exc)
    if transaction_type not in [CashBankTransaction.INCOMING, CashBankTransaction.OUTGOING]:
        messages.error(request, 'Tipe transaksi tidak valid.')
        return redirect('cashbank:transaction_list')
    if request.method == 'POST':
        form = CashBankTransactionForm(company, request.POST)
        if form.is_valid():
            try:
                transaction_obj = create_cashbank_transaction(
                    company,
                    transaction_type,
                    form.cleaned_data['date'],
                    memo=form.cleaned_data['memo'],
                    cash_account=form.cleaned_data['cash_account'],
                    line_specs=parse_transaction_lines(company, request.POST),
                    counterparty=form.cleaned_data['counterparty'],
                    user=request.user,
                )
                messages.success(request, f'Transaksi {transaction_obj.number} dibuat.')
                return redirect('cashbank:transaction_detail', uuid=transaction_obj.uuid)
            except (ValidationError, Exception) as exc:
                messages.error(request, exc.messages[0] if hasattr(exc, 'messages') else str(exc))
    else:
        form = CashBankTransactionForm(company, initial={'date': date.today()})
    return render(
        request,
        'cashbank/transaction_form.html',
        {
            'form': form,
            'transaction_type': transaction_type,
            'accounts': counter_account_choices(company),
            'initial_lines': _transaction_initial_lines(),
            'page_title': 'Kas/Bank Masuk' if transaction_type == CashBankTransaction.INCOMING else 'Kas/Bank Keluar',
            'submit_label': 'Simpan Draft',
        },
    )


@login_required
def transfer_create(request):
    company = _company(request)
    try:
        _guard_module(request)
    except ValidationError as exc:
        return _handle_module_error(request, exc)
    if request.method == 'POST':
        form = CashBankTransferForm(company, request.POST)
        if form.is_valid():
            try:
                transaction_obj = create_transfer_transaction(
                    company,
                    form.cleaned_data['date'],
                    form.cleaned_data['from_account'],
                    form.cleaned_data['to_account'],
                    form.cleaned_data['amount'],
                    memo=form.cleaned_data['memo'],
                    admin_fee=form.cleaned_data['admin_fee'] or 0,
                    admin_fee_account=form.cleaned_data['admin_fee_account'],
                    user=request.user,
                )
                messages.success(request, f'Transfer {transaction_obj.number} dibuat.')
                return redirect('cashbank:transaction_detail', uuid=transaction_obj.uuid)
            except ValidationError as exc:
                messages.error(request, exc.messages[0])
    else:
        form = CashBankTransferForm(company, initial={'date': date.today(), 'admin_fee': 0})
    return render(request, 'cashbank/transfer_form.html', {'form': form, 'page_title': 'Transfer Kas/Bank', 'submit_label': 'Simpan Draft'})


@login_required
def transaction_edit(request, uuid):
    company = _company(request)
    try:
        _guard_module(request)
    except ValidationError as exc:
        return _handle_module_error(request, exc)
    transaction_obj = get_object_or_404(CashBankTransaction.objects.prefetch_related('lines__account'), uuid=uuid, company=company)
    if transaction_obj.status != CashBankTransaction.DRAFT:
        messages.error(request, 'Hanya transaksi draft yang bisa diedit.')
        return redirect('cashbank:transaction_detail', uuid=transaction_obj.uuid)
    if transaction_obj.transaction_type == CashBankTransaction.TRANSFER:
        if request.method == 'POST':
            form = CashBankTransferForm(company, request.POST)
            if form.is_valid():
                try:
                    update_transfer_transaction(
                        transaction_obj,
                        form.cleaned_data['date'],
                        form.cleaned_data['from_account'],
                        form.cleaned_data['to_account'],
                        form.cleaned_data['amount'],
                        memo=form.cleaned_data['memo'],
                        admin_fee=form.cleaned_data['admin_fee'] or 0,
                        admin_fee_account=form.cleaned_data['admin_fee_account'],
                        user=request.user,
                    )
                    messages.success(request, f'Transfer {transaction_obj.number} diperbarui.')
                    return redirect('cashbank:transaction_detail', uuid=transaction_obj.uuid)
                except ValidationError as exc:
                    messages.error(request, exc.messages[0])
        else:
            form = CashBankTransferForm(company, initial={
                'date': transaction_obj.date,
                'from_account': transaction_obj.from_account,
                'to_account': transaction_obj.to_account,
                'amount': transaction_obj.amount,
                'admin_fee': transaction_obj.admin_fee,
                'admin_fee_account': transaction_obj.admin_fee_account,
                'memo': transaction_obj.memo,
            })
        return render(request, 'cashbank/transfer_form.html', {'form': form, 'transaction': transaction_obj, 'page_title': f'Edit {transaction_obj.number}', 'submit_label': 'Simpan Perubahan'})

    if request.method == 'POST':
        form = CashBankTransactionForm(company, request.POST)
        if form.is_valid():
            try:
                update_cashbank_transaction(
                    transaction_obj,
                    form.cleaned_data['date'],
                    memo=form.cleaned_data['memo'],
                    cash_account=form.cleaned_data['cash_account'],
                    line_specs=parse_transaction_lines(company, request.POST),
                    counterparty=form.cleaned_data['counterparty'],
                    user=request.user,
                )
                messages.success(request, f'Transaksi {transaction_obj.number} diperbarui.')
                return redirect('cashbank:transaction_detail', uuid=transaction_obj.uuid)
            except (ValidationError, Exception) as exc:
                messages.error(request, exc.messages[0] if hasattr(exc, 'messages') else str(exc))
    else:
        form = CashBankTransactionForm(company, initial={
            'date': transaction_obj.date,
            'cash_account': transaction_obj.cash_account,
            'counterparty': transaction_obj.counterparty,
            'memo': transaction_obj.memo,
        })
    return render(
        request,
        'cashbank/transaction_form.html',
        {
            'form': form,
            'transaction': transaction_obj,
            'transaction_type': transaction_obj.transaction_type,
            'accounts': counter_account_choices(company),
            'initial_lines': _transaction_initial_lines(transaction_obj),
            'page_title': f'Edit {transaction_obj.number}',
            'submit_label': 'Simpan Perubahan',
        },
    )


@login_required
def transaction_detail(request, uuid):
    try:
        _guard_module(request)
    except ValidationError as exc:
        return _handle_module_error(request, exc)
    transaction_obj = get_object_or_404(
        CashBankTransaction.objects.select_related('cash_account', 'from_account', 'to_account', 'admin_fee_account', 'journal_entry').prefetch_related('lines__account'),
        uuid=uuid,
        company=_company(request),
    )
    return render(request, 'cashbank/transaction_detail.html', {'transaction': transaction_obj})


@login_required
def transaction_post(request, uuid):
    transaction_obj = get_object_or_404(CashBankTransaction, uuid=uuid, company=_company(request))
    if request.method == 'POST':
        try:
            post_cashbank_transaction(transaction_obj, user=request.user)
            messages.success(request, f'Transaksi {transaction_obj.number} diposting.')
        except ValidationError as exc:
            messages.error(request, exc.messages[0])
    return redirect('cashbank:transaction_detail', uuid=transaction_obj.uuid)


@login_required
def transaction_reverse(request, uuid):
    transaction_obj = get_object_or_404(CashBankTransaction, uuid=uuid, company=_company(request))
    if request.method == 'POST':
        try:
            reversal = reverse_cashbank_transaction(transaction_obj, user=request.user)
            messages.success(request, f'Transaksi {transaction_obj.number} direversal dengan jurnal {reversal.number}.')
        except ValidationError as exc:
            messages.error(request, exc.messages[0])
    return redirect('cashbank:transaction_detail', uuid=transaction_obj.uuid)


@login_required
def transaction_delete(request, uuid):
    transaction_obj = get_object_or_404(CashBankTransaction, uuid=uuid, company=_company(request))
    if request.method == 'POST':
        try:
            number = delete_cashbank_transaction(transaction_obj, user=request.user)
            messages.success(request, f'Transaksi {number} dihapus.')
            return redirect('cashbank:transaction_list')
        except ValidationError as exc:
            messages.error(request, exc.messages[0])
    return redirect('cashbank:transaction_detail', uuid=transaction_obj.uuid)


@login_required
def report_cashbank_book(request):
    company = _company(request)
    try:
        _guard_module(request)
    except ValidationError as exc:
        return _handle_module_error(request, exc)
    start, end = _date_filters(request)
    account_uuid = request.GET.get('account')
    cash_account = CashBankAccount.objects.filter(company=company, uuid=account_uuid).select_related('account').first() if account_uuid else None
    book = cashbank_book(company, cash_account, start, end) if cash_account else None
    return render(
        request,
        'cashbank/report_cashbank_book.html',
        {
            'accounts': cashbank_account_choices(company),
            'selected_account': cash_account,
            'book': book,
            'lines': book['lines'] if book else [],
        },
    )