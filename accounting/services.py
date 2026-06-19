import calendar
import ast
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from audit.models import AuditLog
from audit.services import write_audit
from accounting.models import (
    Account,
    AccountCashFlowMapping,
    AccountingPeriod,
    AccountPeriodBalance,
    CashFlowCategory,
    FinancialReportLine,
    FinancialReportTemplate,
    JournalEntry,
    JournalLine,
)


DEFAULT_COA = [
    ('1000', 'ASET', Account.ASSET, Account.DEBIT, False),
    ('1100', 'Kas', Account.ASSET, Account.DEBIT, True),
    ('1110', 'Kas Kecil', Account.ASSET, Account.DEBIT, True),
    ('1120', 'Bank', Account.ASSET, Account.DEBIT, True),
    ('1200', 'Piutang Usaha', Account.ASSET, Account.DEBIT, False),
    ('1300', 'Persediaan', Account.ASSET, Account.DEBIT, False),
    ('1500', 'Aset Tetap', Account.ASSET, Account.DEBIT, False),
    ('1590', 'Akumulasi Penyusutan', Account.ASSET, Account.CREDIT, False),
    ('2000', 'LIABILITAS', Account.LIABILITY, Account.CREDIT, False),
    ('2100', 'Utang Usaha', Account.LIABILITY, Account.CREDIT, False),
    ('2200', 'Utang Pajak', Account.LIABILITY, Account.CREDIT, False),
    ('2300', 'Pinjaman', Account.LIABILITY, Account.CREDIT, False),
    ('3000', 'EKUITAS', Account.EQUITY, Account.CREDIT, False),
    ('3100', 'Modal Pemilik', Account.EQUITY, Account.CREDIT, False),
    ('3200', 'Prive', Account.EQUITY, Account.DEBIT, False),
    ('3300', 'Laba Ditahan', Account.EQUITY, Account.CREDIT, False),
    ('4000', 'PENDAPATAN', Account.REVENUE, Account.CREDIT, False),
    ('4100', 'Penjualan', Account.REVENUE, Account.CREDIT, False),
    ('4200', 'Pendapatan Lain-lain', Account.REVENUE, Account.CREDIT, False),
    ('5000', 'HARGA POKOK PENJUALAN', Account.EXPENSE, Account.DEBIT, False),
    ('5100', 'Harga Pokok Penjualan', Account.EXPENSE, Account.DEBIT, False),
    ('6000', 'BEBAN OPERASIONAL', Account.EXPENSE, Account.DEBIT, False),
    ('6100', 'Beban Gaji', Account.EXPENSE, Account.DEBIT, False),
    ('6200', 'Beban Sewa', Account.EXPENSE, Account.DEBIT, False),
    ('6300', 'Beban Listrik dan Air', Account.EXPENSE, Account.DEBIT, False),
    ('6400', 'Beban Transportasi', Account.EXPENSE, Account.DEBIT, False),
    ('6500', 'Beban Penyusutan', Account.EXPENSE, Account.DEBIT, False),
    ('6900', 'Beban Lain-lain', Account.EXPENSE, Account.DEBIT, False),
]


def create_default_accounts(company):
    for code, name, account_type, normal_balance, is_cash in DEFAULT_COA:
        Account.objects.get_or_create(
            company=company,
            code=code,
            defaults={
                'name': name,
                'account_type': account_type,
                'normal_balance': normal_balance,
                'is_cash_equivalent': is_cash,
            },
        )


DEFAULT_INCOME_STATEMENT_TEMPLATE = [
    {'code': 'PENDAPATAN_HEADING', 'label': 'Pendapatan', 'line_type': FinancialReportLine.HEADING, 'indent': 0, 'bold': True},
    {'code': 'PENJUALAN', 'label': 'Penjualan', 'line_type': FinancialReportLine.ACCOUNT_GROUP, 'accounts': ['4100'], 'indent': 1},
    {'code': 'PENDAPATAN_LAIN', 'label': 'Pendapatan Lain-lain', 'line_type': FinancialReportLine.ACCOUNT_GROUP, 'accounts': ['4200'], 'indent': 1},
    {'code': 'TOTAL_PENDAPATAN', 'label': 'Total Pendapatan', 'line_type': FinancialReportLine.FORMULA, 'formula': 'PENJUALAN + PENDAPATAN_LAIN', 'indent': 0, 'bold': True},
    {'code': 'BLANK_1', 'line_type': FinancialReportLine.BLANK, 'indent': 0},
    {'code': 'BEBAN_HEADING', 'label': 'Beban Operasional', 'line_type': FinancialReportLine.HEADING, 'indent': 0, 'bold': True},
    {'code': 'BEBAN_GAJI', 'label': 'Beban Gaji', 'line_type': FinancialReportLine.ACCOUNT_GROUP, 'accounts': ['6100'], 'indent': 1},
    {'code': 'BEBAN_SEWA', 'label': 'Beban Sewa', 'line_type': FinancialReportLine.ACCOUNT_GROUP, 'accounts': ['6200'], 'indent': 1},
    {'code': 'BEBAN_LISTRIK_AIR', 'label': 'Beban Listrik dan Air', 'line_type': FinancialReportLine.ACCOUNT_GROUP, 'accounts': ['6300'], 'indent': 1},
    {'code': 'BEBAN_TRANSPORTASI', 'label': 'Beban Transportasi', 'line_type': FinancialReportLine.ACCOUNT_GROUP, 'accounts': ['6400'], 'indent': 1},
    {'code': 'BEBAN_PENYUSUTAN', 'label': 'Beban Penyusutan', 'line_type': FinancialReportLine.ACCOUNT_GROUP, 'accounts': ['6500'], 'indent': 1},
    {'code': 'BEBAN_LAIN', 'label': 'Beban Lain-lain', 'line_type': FinancialReportLine.ACCOUNT_GROUP, 'accounts': ['6900'], 'indent': 1},
    {'code': 'TOTAL_BEBAN', 'label': 'Total Beban', 'line_type': FinancialReportLine.FORMULA, 'formula': 'BEBAN_GAJI + BEBAN_SEWA + BEBAN_LISTRIK_AIR + BEBAN_TRANSPORTASI + BEBAN_PENYUSUTAN + BEBAN_LAIN', 'indent': 0, 'bold': True},
    {'code': 'BLANK_2', 'line_type': FinancialReportLine.BLANK, 'indent': 0},
    {'code': 'LABA_RUGI_BERSIH', 'label': 'Laba/Rugi Bersih', 'line_type': FinancialReportLine.FORMULA, 'formula': 'TOTAL_PENDAPATAN - TOTAL_BEBAN', 'indent': 0, 'bold': True},
]


DEFAULT_BALANCE_SHEET_TEMPLATE = [
    {'code': 'ASET_HEADING', 'label': 'Aset', 'line_type': FinancialReportLine.HEADING, 'indent': 0, 'bold': True},
    {'code': 'KAS_BANK', 'label': 'Kas dan Bank', 'line_type': FinancialReportLine.ACCOUNT_GROUP, 'accounts': ['1110', '1120'], 'indent': 1},
    {'code': 'PIUTANG_USAHA', 'label': 'Piutang Usaha', 'line_type': FinancialReportLine.ACCOUNT_GROUP, 'accounts': ['1200'], 'indent': 1},
    {'code': 'PERSEDIAAN', 'label': 'Persediaan', 'line_type': FinancialReportLine.ACCOUNT_GROUP, 'accounts': ['1300'], 'indent': 1},
    {'code': 'ASET_TETAP', 'label': 'Aset Tetap', 'line_type': FinancialReportLine.ACCOUNT_GROUP, 'accounts': ['1500'], 'indent': 1},
    {'code': 'AKUMULASI_PENYUSUTAN', 'label': 'Akumulasi Penyusutan', 'line_type': FinancialReportLine.ACCOUNT_GROUP, 'accounts': ['1590'], 'indent': 1},
    {'code': 'TOTAL_ASET', 'label': 'Total Aset', 'line_type': FinancialReportLine.FORMULA, 'formula': 'KAS_BANK + PIUTANG_USAHA + PERSEDIAAN + ASET_TETAP - AKUMULASI_PENYUSUTAN', 'indent': 0, 'bold': True},
    {'code': 'BLANK_1', 'line_type': FinancialReportLine.BLANK, 'indent': 0},
    {'code': 'LIABILITAS_HEADING', 'label': 'Liabilitas', 'line_type': FinancialReportLine.HEADING, 'indent': 0, 'bold': True},
    {'code': 'UTANG_USAHA', 'label': 'Utang Usaha', 'line_type': FinancialReportLine.ACCOUNT_GROUP, 'accounts': ['2100'], 'indent': 1},
    {'code': 'UTANG_PAJAK', 'label': 'Utang Pajak', 'line_type': FinancialReportLine.ACCOUNT_GROUP, 'accounts': ['2200'], 'indent': 1},
    {'code': 'PINJAMAN', 'label': 'Pinjaman', 'line_type': FinancialReportLine.ACCOUNT_GROUP, 'accounts': ['2300'], 'indent': 1},
    {'code': 'TOTAL_LIABILITAS', 'label': 'Total Liabilitas', 'line_type': FinancialReportLine.FORMULA, 'formula': 'UTANG_USAHA + UTANG_PAJAK + PINJAMAN', 'indent': 0, 'bold': True},
    {'code': 'BLANK_2', 'line_type': FinancialReportLine.BLANK, 'indent': 0},
    {'code': 'EKUITAS_HEADING', 'label': 'Ekuitas', 'line_type': FinancialReportLine.HEADING, 'indent': 0, 'bold': True},
    {'code': 'MODAL_PEMILIK', 'label': 'Modal Pemilik', 'line_type': FinancialReportLine.ACCOUNT_GROUP, 'accounts': ['3100'], 'indent': 1},
    {'code': 'PRIVE', 'label': 'Prive', 'line_type': FinancialReportLine.ACCOUNT_GROUP, 'accounts': ['3200'], 'indent': 1},
    {'code': 'LABA_DITAHAN', 'label': 'Laba Ditahan', 'line_type': FinancialReportLine.ACCOUNT_GROUP, 'accounts': ['3300'], 'indent': 1},
    {'code': 'LABA_RUGI_BERJALAN', 'label': 'Laba/Rugi Berjalan', 'line_type': FinancialReportLine.FORMULA, 'formula': 'income_statement', 'indent': 1},
    {'code': 'TOTAL_EKUITAS', 'label': 'Total Ekuitas', 'line_type': FinancialReportLine.FORMULA, 'formula': 'MODAL_PEMILIK - PRIVE + LABA_DITAHAN + LABA_RUGI_BERJALAN', 'indent': 0, 'bold': True},
    {'code': 'TOTAL_LIABILITAS_EKUITAS', 'label': 'Total Liabilitas dan Ekuitas', 'line_type': FinancialReportLine.FORMULA, 'formula': 'TOTAL_LIABILITAS + TOTAL_EKUITAS', 'indent': 0, 'bold': True},
]


def seed_default_report_templates(company):
    seed_report_template(
        company,
        FinancialReportTemplate.INCOME_STATEMENT,
        'Laba Rugi Default UMKM',
        DEFAULT_INCOME_STATEMENT_TEMPLATE,
    )
    seed_report_template(
        company,
        FinancialReportTemplate.BALANCE_SHEET,
        'Neraca Default UMKM',
        DEFAULT_BALANCE_SHEET_TEMPLATE,
    )


DEFAULT_CASH_FLOW_CATEGORIES = [
    ('OPERATING_RECEIPTS', 'Penerimaan dari pelanggan dan pendapatan', CashFlowCategory.OPERATING, 10, ['1200', '4100', '4200']),
    ('OPERATING_PAYMENTS', 'Pembayaran aktivitas operasi', CashFlowCategory.OPERATING, 20, ['1300', '2100', '2200', '5100', '6100', '6200', '6300', '6400', '6900']),
    ('OPERATING_UNCLASSIFIED', 'Arus kas operasi belum diklasifikasi', CashFlowCategory.OPERATING, 90, []),
    ('INVESTING_FIXED_ASSETS', 'Pembelian/penjualan aset tetap', CashFlowCategory.INVESTING, 10, ['1500']),
    ('FINANCING_LOANS', 'Pinjaman diterima/dibayar', CashFlowCategory.FINANCING, 10, ['2300']),
    ('FINANCING_CAPITAL', 'Setoran/pengembalian modal', CashFlowCategory.FINANCING, 20, ['3100']),
    ('FINANCING_OWNER_DRAW', 'Prive pemilik', CashFlowCategory.FINANCING, 30, ['3200']),
]


def seed_default_cash_flow_categories(company):
    accounts_by_code = {
        account.code: account
        for account in Account.objects.filter(company=company)
    }
    for code, name, activity_type, sort_order, account_codes in DEFAULT_CASH_FLOW_CATEGORIES:
        category, _ = CashFlowCategory.objects.get_or_create(
            company=company,
            code=code,
            defaults={
                'name': name,
                'activity_type': activity_type,
                'sort_order': sort_order,
            },
        )
        for account_code in account_codes:
            account = accounts_by_code.get(account_code)
            if account:
                AccountCashFlowMapping.objects.get_or_create(
                    company=company,
                    account=account,
                    defaults={'category': category},
                )


@transaction.atomic
def seed_report_template(company, report_type, name, line_specs):
    template, created = FinancialReportTemplate.objects.get_or_create(
        company=company,
        report_type=report_type,
        name=name,
        defaults={'is_default': True, 'is_active': True},
    )
    if not created and template.lines.exists():
        return template

    if template.lines.exists():
        template.lines.all().delete()

    accounts_by_code = {
        account.code: account
        for account in Account.objects.filter(company=company)
    }
    for index, spec in enumerate(line_specs, start=1):
        line = FinancialReportLine.objects.create(
            template=template,
            sort_order=index * 10,
            code=spec['code'],
            label=spec.get('label', ''),
            line_type=spec['line_type'],
            indent_level=spec.get('indent', 0),
            is_bold=spec.get('bold', False),
            show_when_zero=spec.get('show_when_zero', True),
            formula=spec.get('formula', ''),
        )
        account_codes = spec.get('accounts', [])
        if account_codes:
            line.accounts.set(accounts_by_code[code] for code in account_codes if code in accounts_by_code)
    return template


def ensure_year_periods(company, year):
    periods = []
    for month in range(1, 13):
        last_day = calendar.monthrange(year, month)[1]
        period, _ = AccountingPeriod.objects.get_or_create(
            company=company,
            year=year,
            month=month,
            defaults={
                'start_date': date(year, month, 1),
                'end_date': date(year, month, last_day),
            },
        )
        periods.append(period)
    return periods


def get_period_for_date(company, entry_date):
    ensure_year_periods(company, entry_date.year)
    return AccountingPeriod.objects.get(company=company, year=entry_date.year, month=entry_date.month)


def next_journal_number(company, entry_date):
    prefix = f'JU-{entry_date:%Y-%m}-'
    last = (
        JournalEntry.objects.filter(company=company, number__startswith=prefix)
        .order_by('-number')
        .first()
    )
    sequence = int(last.number[-4:]) + 1 if last else 1
    return f'{prefix}{sequence:04d}'


@transaction.atomic
def create_draft_journal(company, entry_date, memo, lines, user=None, source_module='core', source_type='journal', source_id=''):
    period = get_period_for_date(company, entry_date)
    if period.status == AccountingPeriod.CLOSED:
        raise ValidationError('Cannot create journal in a closed period.')
    entry = JournalEntry.objects.create(
        company=company,
        period=period,
        number=next_journal_number(company, entry_date),
        date=entry_date,
        memo=memo,
        created_by=user if getattr(user, 'is_authenticated', False) else None,
        source_module=source_module,
        source_type=source_type,
        source_id=source_id,
    )
    for line in lines:
        JournalLine.objects.create(
            entry=entry,
            account=line['account'],
            description=line.get('description', ''),
            debit=Decimal(line.get('debit') or 0),
            credit=Decimal(line.get('credit') or 0),
        ).full_clean()
    validate_journal(entry)
    write_audit(company, user, AuditLog.CREATE, entry, entry.number)
    return entry


def validate_journal(entry):
    lines = list(entry.lines.select_related('account'))
    if len(lines) < 2:
        raise ValidationError('Journal must have at least two lines.')
    total_debit = sum((line.debit for line in lines), Decimal('0'))
    total_credit = sum((line.credit for line in lines), Decimal('0'))
    if total_debit != total_credit:
        raise ValidationError('Journal debit and credit must balance.')
    if total_debit <= 0:
        raise ValidationError('Journal total must be greater than zero.')
    for line in lines:
        line.full_clean()
    return True


@transaction.atomic
def update_draft_journal(entry, entry_date, memo, lines, user=None):
    entry = JournalEntry.objects.select_for_update().get(pk=entry.pk)
    if entry.status != JournalEntry.DRAFT:
        raise ValidationError('Only draft journals can be edited.')

    period = get_period_for_date(entry.company, entry_date)
    if period.status == AccountingPeriod.CLOSED:
        raise ValidationError('Cannot move journal to a closed period.')

    entry.date = entry_date
    entry.period = period
    entry.memo = memo
    entry.save(update_fields=['date', 'period', 'memo', 'updated_at'])

    entry.lines.all().delete()
    for line in lines:
        JournalLine.objects.create(
            entry=entry,
            account=line['account'],
            description=line.get('description', ''),
            debit=Decimal(line.get('debit') or 0),
            credit=Decimal(line.get('credit') or 0),
        ).full_clean()
    validate_journal(entry)
    write_audit(entry.company, user, AuditLog.UPDATE, entry, entry.number)
    return entry


@transaction.atomic
def delete_draft_journal(entry, user=None):
    entry = JournalEntry.objects.select_for_update().get(pk=entry.pk)
    if entry.status != JournalEntry.DRAFT:
        raise ValidationError('Only draft journals can be deleted.')
    if entry.period.status == AccountingPeriod.CLOSED:
        raise ValidationError('Cannot delete journal in a closed period.')

    company = entry.company
    number = entry.number
    write_audit(company, user, AuditLog.DELETE, entry, number)
    entry.delete()
    return number


@transaction.atomic
def post_journal(entry, user=None):
    entry = JournalEntry.objects.select_for_update().get(pk=entry.pk)
    if entry.status != JournalEntry.DRAFT:
        raise ValidationError('Only draft journals can be posted.')
    if entry.period.status == AccountingPeriod.CLOSED:
        raise ValidationError('Cannot post journal in a closed period.')
    validate_journal(entry)
    entry.status = JournalEntry.POSTED
    entry.posted_by = user if getattr(user, 'is_authenticated', False) else None
    entry.posted_at = timezone.now()
    entry.save(update_fields=['status', 'posted_by', 'posted_at', 'updated_at'])
    write_audit(entry.company, user, AuditLog.POST, entry, entry.number)
    return entry


@transaction.atomic
def reverse_journal(entry, user=None, reversal_date=None, memo=''):
    entry = JournalEntry.objects.select_for_update().get(pk=entry.pk)
    if entry.status != JournalEntry.POSTED:
        raise ValidationError('Only posted journals can be reversed.')
    reversal_date = reversal_date or timezone.localdate()
    lines = [
        {
            'account': line.account,
            'description': f'Reversal {entry.number}',
            'debit': line.credit,
            'credit': line.debit,
        }
        for line in entry.lines.select_related('account')
    ]
    reversal = create_draft_journal(
        entry.company,
        reversal_date,
        memo or f'Reversal for {entry.number}',
        lines,
        user=user,
        source_module='core',
        source_type='reversal',
        source_id=entry.number,
    )
    reversal.reversed_entry = entry
    reversal.save(update_fields=['reversed_entry'])
    post_journal(reversal, user=user)
    entry.status = JournalEntry.REVERSED
    entry.save(update_fields=['status', 'updated_at'])
    write_audit(entry.company, user, AuditLog.REVERSE, entry, entry.number)
    return reversal


@transaction.atomic
def close_period(period, user=None):
    period = AccountingPeriod.objects.select_for_update().get(pk=period.pk)
    if period.status != AccountingPeriod.OPEN:
        raise ValidationError('Only open periods can be closed.')
    next_period = get_next_closeable_period(period.company)
    if not next_period or next_period.pk != period.pk:
        if next_period:
            raise ValidationError(f'Close period {next_period.year}-{next_period.month:02d} first.')
        raise ValidationError('No open period is available to close.')
    drafts = JournalEntry.objects.filter(period=period, status=JournalEntry.DRAFT).exists()
    if drafts:
        raise ValidationError('Cannot close period with draft journals.')
    rebuild_account_period_balances(period)
    period.status = AccountingPeriod.CLOSED
    period.closed_by = user if getattr(user, 'is_authenticated', False) else None
    period.closed_at = timezone.now()
    period.save(update_fields=['status', 'closed_by', 'closed_at'])
    ensure_year_periods(period.company, period.year + 1 if period.month == 12 else period.year)
    write_audit(period.company, user, AuditLog.CLOSE_PERIOD, period, str(period))
    return period


@transaction.atomic
def reopen_period(period, user=None):
    period = AccountingPeriod.objects.select_for_update().get(pk=period.pk)
    latest_closed = get_latest_closed_period(period.company)
    if period.status != AccountingPeriod.CLOSED:
        raise ValidationError('Only closed periods can be reopened.')
    if not latest_closed or latest_closed.pk != period.pk:
        raise ValidationError('Only the latest closed period can be reopened.')

    AccountPeriodBalance.objects.filter(period=period).delete()
    period.status = AccountingPeriod.OPEN
    period.closed_by = None
    period.closed_at = None
    period.save(update_fields=['status', 'closed_by', 'closed_at'])
    write_audit(period.company, user, AuditLog.UPDATE, period, f'Reopened {period}')
    return period


def get_latest_closed_period(company):
    return (
        AccountingPeriod.objects.filter(company=company, status=AccountingPeriod.CLOSED)
        .order_by('-end_date')
        .first()
    )


def get_next_closeable_period(company):
    latest_closed = get_latest_closed_period(company)
    periods = AccountingPeriod.objects.filter(company=company, status=AccountingPeriod.OPEN)
    if latest_closed:
        periods = periods.filter(start_date__gt=latest_closed.end_date)
    return periods.order_by('start_date').first()


def rebuild_account_period_balances(period):
    previous_period = (
        AccountingPeriod.objects.filter(company=period.company, end_date__lt=period.start_date)
        .order_by('-end_date')
        .first()
    )
    previous_balances = {}
    if previous_period:
        previous_balances = {
            balance.account_id: balance
            for balance in AccountPeriodBalance.objects.filter(period=previous_period)
        }

    movements = {
        row['account_id']: {
            'debit': row['debit'] or Decimal('0'),
            'credit': row['credit'] or Decimal('0'),
        }
        for row in JournalLine.objects.filter(
            entry__company=period.company,
            entry__period=period,
            entry__status__in=[JournalEntry.POSTED, JournalEntry.REVERSED],
        )
        .values('account_id')
        .annotate(debit=Sum('debit'), credit=Sum('credit'))
    }

    balances = []
    for account in Account.objects.filter(company=period.company).order_by('code'):
        previous_balance = previous_balances.get(account.id)
        opening_debit = previous_balance.closing_debit if previous_balance else Decimal('0')
        opening_credit = previous_balance.closing_credit if previous_balance else Decimal('0')
        movement_debit = movements.get(account.id, {}).get('debit', Decimal('0'))
        movement_credit = movements.get(account.id, {}).get('credit', Decimal('0'))
        closing_debit, closing_credit = _side_from_signed_balance(
            opening_debit - opening_credit + movement_debit - movement_credit
        )
        balances.append(
            AccountPeriodBalance(
                company=period.company,
                account=account,
                period=period,
                opening_debit=opening_debit,
                opening_credit=opening_credit,
                movement_debit=movement_debit,
                movement_credit=movement_credit,
                closing_debit=closing_debit,
                closing_credit=closing_credit,
            )
        )

    AccountPeriodBalance.objects.filter(period=period).delete()
    AccountPeriodBalance.objects.bulk_create(balances)
    return balances


def _side_from_signed_balance(amount):
    if amount >= 0:
        return amount, Decimal('0')
    return Decimal('0'), abs(amount)


def account_balances(company, start_date=None, end_date=None):
    if start_date is None and end_date is not None:
        snapshot_period = _latest_snapshot_period(company, end_date)
        if snapshot_period:
            return account_balances_from_snapshot(company, snapshot_period, end_date)

    qs = JournalLine.objects.filter(entry__company=company, entry__status__in=[JournalEntry.POSTED, JournalEntry.REVERSED])
    if start_date:
        qs = qs.filter(entry__date__gte=start_date)
    if end_date:
        qs = qs.filter(entry__date__lte=end_date)
    rows = qs.values('account_id').annotate(debit=Sum('debit'), credit=Sum('credit'))
    totals = {row['account_id']: {'debit': row['debit'] or Decimal('0'), 'credit': row['credit'] or Decimal('0')} for row in rows}
    result = []
    for account in Account.objects.filter(company=company, is_active=True).order_by('code'):
        debit = totals.get(account.id, {}).get('debit', Decimal('0'))
        credit = totals.get(account.id, {}).get('credit', Decimal('0'))
        balance = debit - credit if account.normal_balance == Account.DEBIT else credit - debit
        result.append({'account': account, 'debit': debit, 'credit': credit, 'balance': balance})
    return result


def _latest_snapshot_period(company, end_date):
    return (
        AccountingPeriod.objects.filter(
            company=company,
            end_date__lte=end_date,
            account_balances__isnull=False,
        )
        .distinct()
        .order_by('-end_date')
        .first()
    )


def account_balances_from_snapshot(company, snapshot_period, end_date):
    balances_by_account = {
        balance.account_id: balance
        for balance in AccountPeriodBalance.objects.filter(period=snapshot_period)
    }
    movement_start = snapshot_period.end_date + timedelta(days=1)
    movements = {}
    if movement_start <= end_date:
        movements = {
            row['account_id']: {
                'debit': row['debit'] or Decimal('0'),
                'credit': row['credit'] or Decimal('0'),
            }
            for row in JournalLine.objects.filter(
                entry__company=company,
                entry__date__gte=movement_start,
                entry__date__lte=end_date,
                entry__status__in=[JournalEntry.POSTED, JournalEntry.REVERSED],
            )
            .values('account_id')
            .annotate(debit=Sum('debit'), credit=Sum('credit'))
        }

    result = []
    for account in Account.objects.filter(company=company, is_active=True).order_by('code'):
        period_balance = balances_by_account.get(account.id)
        opening_signed = Decimal('0')
        if period_balance:
            opening_signed = period_balance.closing_debit - period_balance.closing_credit
        movement_debit = movements.get(account.id, {}).get('debit', Decimal('0'))
        movement_credit = movements.get(account.id, {}).get('credit', Decimal('0'))
        debit, credit = _side_from_signed_balance(opening_signed + movement_debit - movement_credit)
        balance = debit - credit if account.normal_balance == Account.DEBIT else credit - debit
        result.append({'account': account, 'debit': debit, 'credit': credit, 'balance': balance})
    return result


def trial_balance(company, start_date=None, end_date=None):
    rows = account_balances(company, start_date, end_date)
    return {
        'rows': rows,
        'total_debit': sum((row['debit'] for row in rows), Decimal('0')),
        'total_credit': sum((row['credit'] for row in rows), Decimal('0')),
    }


def general_ledger(company, account=None, start_date=None, end_date=None):
    if account is None:
        return None

    opening_signed = Decimal('0')
    if start_date:
        opening_rows = account_balances(company, end_date=start_date - timedelta(days=1))
        for row in opening_rows:
            if row['account'].pk == account.pk:
                opening_signed = row['debit'] - row['credit']
                break

    qs = JournalLine.objects.filter(
        entry__company=company,
        entry__status__in=[JournalEntry.POSTED, JournalEntry.REVERSED],
        account=account,
    )
    if start_date:
        qs = qs.filter(entry__date__gte=start_date)
    if end_date:
        qs = qs.filter(entry__date__lte=end_date)

    running_signed = opening_signed
    lines = []
    total_debit = Decimal('0')
    total_credit = Decimal('0')
    for line in qs.select_related('entry', 'account').order_by('entry__date', 'entry__number', 'id'):
        total_debit += line.debit
        total_credit += line.credit
        running_signed += line.debit - line.credit
        line.running_balance = running_signed if account.normal_balance == Account.DEBIT else -running_signed
        lines.append(line)

    opening_balance = opening_signed if account.normal_balance == Account.DEBIT else -opening_signed
    closing_balance = running_signed if account.normal_balance == Account.DEBIT else -running_signed
    return {
        'account': account,
        'opening_balance': opening_balance,
        'total_debit': total_debit,
        'total_credit': total_credit,
        'closing_balance': closing_balance,
        'lines': lines,
    }


def income_statement(company, start_date=None, end_date=None):
    rows = [row for row in account_balances(company, start_date, end_date) if row['account'].account_type in [Account.REVENUE, Account.EXPENSE]]
    revenue = sum((row['balance'] for row in rows if row['account'].account_type == Account.REVENUE), Decimal('0'))
    expense = sum((row['balance'] for row in rows if row['account'].account_type == Account.EXPENSE), Decimal('0'))
    return {'rows': rows, 'revenue': revenue, 'expense': expense, 'net_income': revenue - expense}


def balance_sheet(company, as_of_date=None):
    rows = account_balances(company, end_date=as_of_date)
    grouped = defaultdict(list)
    for row in rows:
        if row['account'].account_type in [Account.ASSET, Account.LIABILITY, Account.EQUITY]:
            grouped[row['account'].account_type].append(row)
    totals = {key: sum((row['balance'] for row in value), Decimal('0')) for key, value in grouped.items()}
    net_income = income_statement(company, end_date=as_of_date)['net_income']
    totals[Account.EQUITY] = totals.get(Account.EQUITY, Decimal('0')) + net_income
    return {'groups': dict(grouped), 'totals': totals, 'net_income': net_income}


def get_default_report_template(company, report_type):
    template = (
        FinancialReportTemplate.objects.filter(
            company=company,
            report_type=report_type,
            is_active=True,
            is_default=True,
        )
        .order_by('id')
        .first()
    )
    if template:
        return template
    seed_default_report_templates(company)
    return FinancialReportTemplate.objects.get(
        company=company,
        report_type=report_type,
        is_default=True,
        is_active=True,
    )


def render_financial_report(company, report_type, start_date=None, end_date=None):
    template = get_default_report_template(company, report_type)
    lines = template.lines.prefetch_related('accounts').order_by('sort_order', 'id')
    account_balance_map = {
        row['account'].id: row['balance']
        for row in account_balances(company, start_date=start_date, end_date=end_date)
    }
    values = {}
    rendered_rows = []

    for line in lines:
        value = None
        if line.line_type == FinancialReportLine.ACCOUNT_GROUP:
            value = sum(
                (account_balance_map.get(account.id, Decimal('0')) for account in line.accounts.all()),
                Decimal('0'),
            )
        elif line.line_type == FinancialReportLine.FORMULA:
            if line.formula == 'income_statement':
                value = income_statement(company, start_date=start_date, end_date=end_date)['net_income']
            else:
                value = evaluate_report_formula(line.formula, values)
        elif line.line_type in [FinancialReportLine.HEADING, FinancialReportLine.BLANK]:
            value = None

        if value is not None:
            values[line.code] = value
        if value == 0 and not line.show_when_zero:
            continue
        rendered_rows.append({'line': line, 'value': value, 'has_value': value is not None})

    return {'template': template, 'rows': rendered_rows, 'values': values}


def evaluate_report_formula(expression, values):
    try:
        node = ast.parse(expression, mode='eval')
    except SyntaxError as exc:
        raise ValidationError(f'Invalid report formula: {expression}') from exc
    return _evaluate_formula_node(node.body, values)


def _evaluate_formula_node(node, values):
    if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Sub)):
        left = _evaluate_formula_node(node.left, values)
        right = _evaluate_formula_node(node.right, values)
        return left + right if isinstance(node.op, ast.Add) else left - right
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        return -_evaluate_formula_node(node.operand, values)
    if isinstance(node, ast.Name):
        return values.get(node.id, Decimal('0'))
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return Decimal(str(node.value))
    raise ValidationError('Report formula only supports line codes with + and - operators.')


def cash_flow(company, start_date=None, end_date=None):
    rows = [row for row in account_balances(company, start_date, end_date) if row['account'].is_cash_equivalent]
    cash_in = sum((row['debit'] for row in rows), Decimal('0'))
    cash_out = sum((row['credit'] for row in rows), Decimal('0'))
    return {'rows': rows, 'cash_in': cash_in, 'cash_out': cash_out, 'net_cash_flow': cash_in - cash_out}


def render_cash_flow_statement(company, start_date=None, end_date=None):
    seed_default_cash_flow_categories(company)
    categories = list(
        CashFlowCategory.objects.filter(company=company, is_active=True).order_by('activity_type', 'sort_order', 'name')
    )
    uncategorized = CashFlowCategory.objects.get(company=company, code='OPERATING_UNCLASSIFIED')
    mapping_by_account = {
        mapping.account_id: mapping.category
        for mapping in AccountCashFlowMapping.objects.filter(company=company).select_related('category')
    }
    category_totals = {category.id: Decimal('0') for category in categories}

    entries = JournalEntry.objects.filter(company=company, status__in=[JournalEntry.POSTED, JournalEntry.REVERSED])
    if start_date:
        entries = entries.filter(date__gte=start_date)
    if end_date:
        entries = entries.filter(date__lte=end_date)
    entries = entries.prefetch_related('lines__account').order_by('date', 'number')

    for entry in entries:
        lines = list(entry.lines.all())
        cash_delta = sum(
            (line.debit - line.credit for line in lines if line.account.is_cash_equivalent),
            Decimal('0'),
        )
        if cash_delta == 0:
            continue

        counter_lines = [line for line in lines if not line.account.is_cash_equivalent]
        mapped_counter_lines = [
            line
            for line in counter_lines
            if mapping_by_account.get(line.account_id)
        ]
        if not mapped_counter_lines:
            category_totals[uncategorized.id] += cash_delta
            continue

        total_weight = sum(
            (abs(line.debit - line.credit) for line in mapped_counter_lines),
            Decimal('0'),
        )
        if total_weight == 0:
            category_totals[uncategorized.id] += cash_delta
            continue

        allocated = Decimal('0')
        last_index = len(mapped_counter_lines) - 1
        for index, line in enumerate(mapped_counter_lines):
            category = mapping_by_account[line.account_id]
            if index == last_index:
                amount = cash_delta - allocated
            else:
                amount = cash_delta * abs(line.debit - line.credit) / total_weight
                allocated += amount
            category_totals[category.id] += amount

    grouped = []
    activity_labels = {
        CashFlowCategory.OPERATING: 'ARUS KAS DARI AKTIVITAS OPERASI',
        CashFlowCategory.INVESTING: 'ARUS KAS DARI AKTIVITAS INVESTASI',
        CashFlowCategory.FINANCING: 'ARUS KAS DARI AKTIVITAS PENDANAAN',
    }
    for activity_type in [CashFlowCategory.OPERATING, CashFlowCategory.INVESTING, CashFlowCategory.FINANCING]:
        activity_categories = [
            category
            for category in categories
            if category.activity_type == activity_type
        ]
        rows = [
            {'category': category, 'amount': category_totals.get(category.id, Decimal('0'))}
            for category in activity_categories
        ]
        total = sum((row['amount'] for row in rows), Decimal('0'))
        grouped.append({'activity_type': activity_type, 'label': activity_labels[activity_type], 'rows': rows, 'total': total})

    cash_beginning = cash_balance_as_of(company, start_date - timedelta(days=1)) if start_date else Decimal('0')
    cash_ending = cash_balance_as_of(company, end_date) if end_date else cash_beginning + sum((group['total'] for group in grouped), Decimal('0'))
    net_cash_flow = sum((group['total'] for group in grouped), Decimal('0'))
    if end_date is None:
        cash_ending = cash_beginning + net_cash_flow

    return {
        'groups': grouped,
        'cash_beginning': cash_beginning,
        'net_cash_flow': net_cash_flow,
        'cash_ending': cash_ending,
    }


def cash_balance_as_of(company, as_of_date):
    if as_of_date is None:
        return Decimal('0')
    rows = account_balances(company, end_date=as_of_date)
    return sum(
        (row['balance'] for row in rows if row['account'].is_cash_equivalent),
        Decimal('0'),
    )
