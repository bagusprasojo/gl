from datetime import date

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from accounting.exports import export_financial_statement, export_rows_pdf, export_rows_xlsx
from accounting.forms import JournalEntryForm, account_choices, parse_journal_lines
from accounting.models import Account, AccountingPeriod, JournalEntry
from accounting.services import (
    balance_sheet,
    cash_flow,
    close_period,
    general_ledger,
    income_statement,
    post_journal,
    reverse_journal,
    create_draft_journal,
    trial_balance,
    update_draft_journal,
    delete_draft_journal,
    render_financial_report,
    render_cash_flow_statement,
    get_latest_closed_period,
    get_next_closeable_period,
    reopen_period,
)
from accounting.models import FinancialReportTemplate
from modules.models import ModuleRegistry


def _company(request):
    return request.user.company


def _date_filters(request):
    start = request.GET.get('start_date')
    end = request.GET.get('end_date')
    return (
        date.fromisoformat(start) if start else None,
        date.fromisoformat(end) if end else None,
    )


def _as_of_date_filter(request):
    value = request.GET.get('as_of_date') or request.GET.get('end_date')
    return date.fromisoformat(value) if value else None


def _period_label(start_date=None, end_date=None, as_of=False):
    if as_of:
        return f'Per {end_date:%d-%m-%Y}' if end_date else 'Per seluruh tanggal'
    if start_date and end_date:
        return f'Periode {start_date:%d-%m-%Y} s/d {end_date:%d-%m-%Y}'
    if start_date:
        return f'Periode mulai {start_date:%d-%m-%Y}'
    if end_date:
        return f'Periode sampai {end_date:%d-%m-%Y}'
    return 'Seluruh periode'


def _financial_report_export_rows(rendered_rows):
    return [
        {
            'label': row['line'].label,
            'value': row['value'],
            'has_value': row['has_value'],
            'indent_level': row['line'].indent_level,
            'is_bold': row['line'].is_bold,
            'is_blank': row['line'].line_type == 'blank',
        }
        for row in rendered_rows
    ]


def _cash_flow_export_rows(data):
    rows = []
    for group in data['groups']:
        rows.append({
            'label': group['label'],
            'value': None,
            'has_value': False,
            'indent_level': 0,
            'is_bold': True,
            'is_blank': False,
        })
        for row in group['rows']:
            rows.append({
                'label': row['category'].name,
                'value': row['amount'],
                'has_value': True,
                'indent_level': 1,
                'is_bold': False,
                'is_blank': False,
            })
        rows.append({
            'label': f"Jumlah {group['label'].lower()}",
            'value': group['total'],
            'has_value': True,
            'indent_level': 0,
            'is_bold': True,
            'is_blank': False,
        })
        rows.append({'label': '', 'value': None, 'has_value': False, 'indent_level': 0, 'is_bold': False, 'is_blank': True})
    rows.extend([
        {'label': 'Kenaikan/Penurunan Bersih Kas', 'value': data['net_cash_flow'], 'has_value': True, 'indent_level': 0, 'is_bold': True, 'is_blank': False},
        {'label': 'Kas Awal Periode', 'value': data['cash_beginning'], 'has_value': True, 'indent_level': 0, 'is_bold': True, 'is_blank': False},
        {'label': 'Kas Akhir Periode', 'value': data['cash_ending'], 'has_value': True, 'indent_level': 0, 'is_bold': True, 'is_blank': False},
    ])
    return rows


@login_required
def home(request):
    return render(request, 'accounting/home.html')


@login_required
def account_list(request):
    accounts = Account.objects.filter(company=_company(request)).order_by('code')
    return render(request, 'accounting/account_list.html', {'accounts': accounts})


@login_required
def journal_list(request):
    company = _company(request)
    start_date, end_date = _date_filters(request)
    status = request.GET.get('status', '')
    search_query = request.GET.get('q', '').strip()
    journals = JournalEntry.objects.filter(company=company).select_related('period').order_by('-date', '-id')
    if start_date:
        journals = journals.filter(date__gte=start_date)
    if end_date:
        journals = journals.filter(date__lte=end_date)
    if status in [JournalEntry.DRAFT, JournalEntry.POSTED, JournalEntry.REVERSED]:
        journals = journals.filter(status=status)
    if search_query:
        journals = journals.filter(
            Q(number__icontains=search_query)
            | Q(memo__icontains=search_query)
            | Q(source_module__icontains=search_query)
            | Q(source_type__icontains=search_query)
            | Q(source_id__icontains=search_query)
        )
    paginator = Paginator(journals, 20)
    page_obj = paginator.get_page(request.GET.get('page'))
    query_params = request.GET.copy()
    query_params.pop('page', None)
    return render(
        request,
        'accounting/journal_list.html',
        {
            'journals': page_obj.object_list,
            'page_obj': page_obj,
            'query_string': query_params.urlencode(),
            'status_choices': JournalEntry._meta.get_field('status').choices,
        },
    )


@login_required
def journal_create(request):
    company = _company(request)
    if request.method == 'POST':
        form = JournalEntryForm(request.POST)
        if form.is_valid():
            try:
                entry = create_draft_journal(
                    company=company,
                    entry_date=form.cleaned_data['date'],
                    memo=form.cleaned_data['memo'],
                    lines=parse_journal_lines(company, request.POST),
                    user=request.user,
                )
                messages.success(request, f'Jurnal {entry.number} dibuat.')
                return redirect('accounting:journal_detail', uuid=entry.uuid)
            except (ValidationError, Account.DoesNotExist) as exc:
                messages.error(request, exc.messages[0] if hasattr(exc, 'messages') else str(exc))
    else:
        form = JournalEntryForm(initial={'date': date.today()})
    return render(
        request,
        'accounting/journal_form.html',
        {
            'form': form,
            'accounts': account_choices(company),
            'initial_lines': [
                {'id': 0, 'account': '', 'description': '', 'debit': '', 'credit': ''},
                {'id': 1, 'account': '', 'description': '', 'debit': '', 'credit': ''},
            ],
            'page_title': 'Jurnal Baru',
            'submit_label': 'Simpan Draft',
        },
    )


@login_required
def journal_edit(request, uuid):
    company = _company(request)
    entry = get_object_or_404(
        JournalEntry.objects.prefetch_related('lines__account'),
        uuid=uuid,
        company=company,
    )
    if entry.status != JournalEntry.DRAFT:
        messages.error(request, 'Hanya jurnal draft yang bisa diedit.')
        return redirect('accounting:journal_detail', uuid=entry.uuid)

    if request.method == 'POST':
        form = JournalEntryForm(request.POST)
        if form.is_valid():
            try:
                update_draft_journal(
                    entry=entry,
                    entry_date=form.cleaned_data['date'],
                    memo=form.cleaned_data['memo'],
                    lines=parse_journal_lines(company, request.POST),
                    user=request.user,
                )
                messages.success(request, f'Jurnal {entry.number} diperbarui.')
                return redirect('accounting:journal_detail', uuid=entry.uuid)
            except (ValidationError, Account.DoesNotExist) as exc:
                messages.error(request, exc.messages[0] if hasattr(exc, 'messages') else str(exc))
    else:
        form = JournalEntryForm(initial={'date': entry.date, 'memo': entry.memo})

    initial_lines = [
        {
            'id': line.pk,
            'account': str(line.account_id),
            'description': line.description,
            'debit': str(line.debit if line.debit else ''),
            'credit': str(line.credit if line.credit else ''),
        }
        for line in entry.lines.all()
    ]
    return render(
        request,
        'accounting/journal_form.html',
        {
            'form': form,
            'accounts': account_choices(company),
            'entry': entry,
            'initial_lines': initial_lines,
            'page_title': f'Edit {entry.number}',
            'submit_label': 'Simpan Perubahan',
        },
    )


@login_required
def journal_detail(request, uuid):
    entry = get_object_or_404(
        JournalEntry.objects.select_related('period').prefetch_related('lines__account'),
        uuid=uuid,
        company=_company(request),
    )
    return render(request, 'accounting/journal_detail.html', {'entry': entry})


@login_required
def journal_post(request, uuid):
    entry = get_object_or_404(JournalEntry, uuid=uuid, company=_company(request))
    if request.method == 'POST':
        try:
            post_journal(entry, user=request.user)
            messages.success(request, f'Jurnal {entry.number} diposting.')
        except ValidationError as exc:
            messages.error(request, exc.messages[0])
    return redirect('accounting:journal_detail', uuid=entry.uuid)


@login_required
def journal_delete(request, uuid):
    entry = get_object_or_404(JournalEntry, uuid=uuid, company=_company(request))
    if request.method == 'POST':
        try:
            number = delete_draft_journal(entry, user=request.user)
            messages.success(request, f'Jurnal {number} dihapus.')
            return redirect('accounting:journal_list')
        except ValidationError as exc:
            messages.error(request, exc.messages[0])
    return redirect('accounting:journal_detail', uuid=entry.uuid)


@login_required
def journal_reverse(request, uuid):
    entry = get_object_or_404(JournalEntry, uuid=uuid, company=_company(request))
    if request.method == 'POST':
        try:
            reversal = reverse_journal(entry, user=request.user)
            messages.success(request, f'Jurnal reversal {reversal.number} dibuat dan diposting.')
            return redirect('accounting:journal_detail', uuid=reversal.uuid)
        except ValidationError as exc:
            messages.error(request, exc.messages[0])
    return redirect('accounting:journal_detail', uuid=entry.uuid)


@login_required
def period_list(request):
    company = _company(request)
    periods = list(AccountingPeriod.objects.filter(company=company).order_by('-year', '-month'))
    next_closeable_period = get_next_closeable_period(company)
    latest_closed_period = get_latest_closed_period(company)
    for period in periods:
        period.can_close = bool(next_closeable_period and period.pk == next_closeable_period.pk)
        period.can_reopen = bool(latest_closed_period and period.pk == latest_closed_period.pk)
    return render(request, 'accounting/period_list.html', {'periods': periods})


@login_required
def period_close(request, uuid):
    period = get_object_or_404(AccountingPeriod, uuid=uuid, company=_company(request))
    if request.method == 'POST':
        try:
            close_period(period, user=request.user)
            messages.success(request, f'Periode {period.year}-{period.month:02d} ditutup.')
        except ValidationError as exc:
            messages.error(request, exc.messages[0])
    return redirect('accounting:period_list')


@login_required
def period_reopen(request, uuid):
    period = get_object_or_404(AccountingPeriod, uuid=uuid, company=_company(request))
    if request.method == 'POST':
        try:
            reopen_period(period, user=request.user)
            messages.success(request, f'Periode {period.year}-{period.month:02d} dibuka ulang.')
        except ValidationError as exc:
            messages.error(request, exc.messages[0])
    return redirect('accounting:period_list')


@login_required
def module_list(request):
    modules = ModuleRegistry.objects.filter(company=_company(request))
    return render(request, 'accounting/module_list.html', {'modules': modules})


def _export(request, filename, title, headers, rows):
    fmt = request.GET.get('export')
    if fmt == 'xlsx':
        return export_rows_xlsx(filename, title, headers, rows)
    if fmt == 'pdf':
        return export_rows_pdf(filename, title, headers, rows)
    return None


@login_required
def report_general_ledger(request):
    company = _company(request)
    start, end = _date_filters(request)
    account_uuid = request.GET.get('account')
    account = Account.objects.filter(company=company, uuid=account_uuid).first() if account_uuid else None
    ledger = general_ledger(company, account=account, start_date=start, end_date=end)
    lines = ledger['lines'] if ledger else []
    rows = []
    if ledger:
        rows.append(['', '', account.code, account.name, 'Saldo Awal', '', '', ledger['opening_balance']])
        rows.extend([
            [
                line.entry.date,
                line.entry.number,
                line.account.code,
                line.account.name,
                line.description,
                line.debit,
                line.credit,
                line.running_balance,
            ]
            for line in lines
        ])
        rows.append(['', '', account.code, account.name, 'Total Mutasi', ledger['total_debit'], ledger['total_credit'], ''])
        rows.append(['', '', account.code, account.name, 'Saldo Akhir', '', '', ledger['closing_balance']])
    exported = _export(
        request,
        'buku-besar',
        'Buku Besar',
        ['Tanggal', 'No Jurnal', 'Kode', 'Akun', 'Keterangan', 'Debit', 'Kredit', 'Saldo'],
        rows,
    )
    if exported:
        return exported
    paginator = Paginator(lines, 20)
    page_obj = paginator.get_page(request.GET.get('page'))
    query_params = request.GET.copy()
    query_params.pop('page', None)
    return render(
        request,
        'accounting/report_general_ledger.html',
        {
            'ledger': ledger,
            'lines': page_obj.object_list,
            'accounts': account_choices(company),
            'selected_account': account,
            'page_obj': page_obj,
            'query_string': query_params.urlencode(),
        },
    )


@login_required
def report_trial_balance(request):
    start, end = _date_filters(request)
    data = trial_balance(_company(request), start, end)
    rows = [[row['account'].code, row['account'].name, row['debit'], row['credit']] for row in data['rows']]
    exported = _export(request, 'neraca-percobaan', 'Neraca Percobaan', ['Kode', 'Akun', 'Debit', 'Kredit'], rows)
    if exported:
        return exported
    return render(request, 'accounting/report_trial_balance.html', data)


@login_required
def report_income_statement(request):
    start, end = _date_filters(request)
    company = _company(request)
    data = render_financial_report(company, FinancialReportTemplate.INCOME_STATEMENT, start, end)
    export_rows = _financial_report_export_rows(data['rows'])
    exported = export_financial_statement(
        request,
        'laba-rugi',
        company,
        'Laba Rugi',
        _period_label(start, end),
        export_rows,
    )
    if exported:
        return exported
    rows = [
        [row['line'].code, row['line'].label, row['value'] if row['value'] is not None else '']
        for row in data['rows']
        if row['line'].line_type != 'blank'
    ]
    return render(request, 'accounting/report_income_statement.html', data)


@login_required
def report_balance_sheet(request):
    as_of_date = _as_of_date_filter(request)
    company = _company(request)
    data = render_financial_report(company, FinancialReportTemplate.BALANCE_SHEET, None, as_of_date)
    export_rows = _financial_report_export_rows(data['rows'])
    exported = export_financial_statement(
        request,
        'neraca',
        company,
        'Neraca',
        _period_label(end_date=as_of_date, as_of=True),
        export_rows,
    )
    if exported:
        return exported
    rows = [
        [row['line'].code, row['line'].label, row['value'] if row['value'] is not None else '']
        for row in data['rows']
        if row['line'].line_type != 'blank'
    ]
    return render(request, 'accounting/report_balance_sheet.html', {**data, 'as_of_date': as_of_date})


@login_required
def report_cash_flow(request):
    start, end = _date_filters(request)
    company = _company(request)
    data = render_cash_flow_statement(company, start, end)
    export_rows = _cash_flow_export_rows(data)
    exported = export_financial_statement(
        request,
        'arus-kas',
        company,
        'Arus Kas',
        _period_label(start, end),
        export_rows,
    )
    if exported:
        return exported
    rows = []
    for group in data['groups']:
        rows.append(['', group['label'], ''])
        for row in group['rows']:
            rows.append([row['category'].code, row['category'].name, row['amount']])
        rows.append(['', f"Jumlah {group['label'].lower()}", group['total']])
    rows.extend([
        ['', 'Kenaikan/Penurunan Bersih Kas', data['net_cash_flow']],
        ['', 'Kas Awal Periode', data['cash_beginning']],
        ['', 'Kas Akhir Periode', data['cash_ending']],
    ])
    return render(request, 'accounting/report_cash_flow.html', data)

# Create your views here.
