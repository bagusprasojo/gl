from datetime import date
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from accounts.models import User
from accounting.models import Account, JournalEntry
from accounting.services import create_draft_journal, ensure_year_periods, post_journal
from companies.models import Company


class Command(BaseCommand):
    help = 'Seed 5 posted sample journals each for cash/bank, receivables, revenue, expenses, and asset depreciation.'

    def add_arguments(self, parser):
        parser.add_argument('--company', help='Company name. Defaults to the first active company.')
        parser.add_argument('--username', help='Username recorded as creator/poster. Defaults to the first user in the company.')
        parser.add_argument('--year', type=int, default=date.today().year)
        parser.add_argument('--month', type=int, default=date.today().month)

    @transaction.atomic
    def handle(self, *args, **options):
        company = self._get_company(options.get('company'))
        user = self._get_user(company, options.get('username'))
        year = options['year']
        month = options['month']
        ensure_year_periods(company, year)

        accounts = {
            account.code: account
            for account in Account.objects.filter(company=company)
        }
        required_codes = ['1110', '1120', '1200', '1590', '2300', '3100', '3200', '4100', '4200', '6100', '6200', '6300', '6400', '6500', '6900']
        missing = [code for code in required_codes if code not in accounts]
        if missing:
            raise CommandError(f'Missing account codes for seed data: {", ".join(missing)}')

        specs = self._transaction_specs(accounts, year, month)
        created = 0
        skipped = 0
        for spec in specs:
            if JournalEntry.objects.filter(company=company, source_module='sample_seed', source_id=spec['source_id']).exists():
                skipped += 1
                continue
            entry = create_draft_journal(
                company=company,
                entry_date=spec['date'],
                memo=spec['memo'],
                lines=spec['lines'],
                user=user,
                source_module='sample_seed',
                source_type=spec['category'],
                source_id=spec['source_id'],
            )
            post_journal(entry, user=user)
            created += 1

        self.stdout.write(
            self.style.SUCCESS(
                f'Seeded sample transactions for "{company.name}": {created} created, {skipped} skipped.'
            )
        )

    def _get_company(self, company_name):
        if company_name:
            try:
                return Company.objects.get(name=company_name)
            except Company.DoesNotExist as exc:
                raise CommandError(f'Company "{company_name}" not found.') from exc
        company = Company.objects.filter(is_active=True).order_by('id').first()
        if not company:
            raise CommandError('No active company found. Run bootstrap_company first.')
        return company

    def _get_user(self, company, username):
        if username:
            try:
                return User.objects.get(username=username, company=company)
            except User.DoesNotExist as exc:
                raise CommandError(f'User "{username}" not found in company "{company.name}".') from exc
        return User.objects.filter(company=company).order_by('id').first()

    def _transaction_specs(self, accounts, year, month):
        def money(value):
            return Decimal(value)

        def tx(day, category, number, memo, debit_account, credit_account, amount):
            return {
                'date': date(year, month, day),
                'category': category,
                'source_id': f'{category.upper()}-{year}{month:02d}-{number:02d}',
                'memo': memo,
                'lines': [
                    {'account': debit_account, 'description': memo, 'debit': money(amount), 'credit': Decimal('0')},
                    {'account': credit_account, 'description': memo, 'debit': Decimal('0'), 'credit': money(amount)},
                ],
            }

        cash_bank = [
            tx(1, 'cash_bank', 1, 'Setoran modal pemilik ke Bank', accounts['1120'], accounts['3100'], '5000000'),
            tx(2, 'cash_bank', 2, 'Pengisian kas kecil dari Bank', accounts['1110'], accounts['1120'], '750000'),
            tx(3, 'cash_bank', 3, 'Setoran kas kecil kembali ke Bank', accounts['1120'], accounts['1110'], '250000'),
            tx(4, 'cash_bank', 4, 'Penerimaan pinjaman usaha ke Bank', accounts['1120'], accounts['2300'], '3000000'),
            tx(5, 'cash_bank', 5, 'Prive pemilik dari Bank', accounts['3200'], accounts['1120'], '500000'),
        ]
        receivables = [
            tx(6, 'receivable', 1, 'Penjualan kredit pelanggan A', accounts['1200'], accounts['4100'], '1250000'),
            tx(7, 'receivable', 2, 'Penjualan kredit pelanggan B', accounts['1200'], accounts['4100'], '980000'),
            tx(8, 'receivable', 3, 'Penjualan kredit pelanggan C', accounts['1200'], accounts['4100'], '1575000'),
            tx(9, 'receivable', 4, 'Penjualan kredit pelanggan D', accounts['1200'], accounts['4100'], '2100000'),
            tx(10, 'receivable', 5, 'Penjualan kredit pelanggan E', accounts['1200'], accounts['4100'], '875000'),
        ]
        revenue = [
            tx(11, 'revenue', 1, 'Penjualan tunai harian 1', accounts['1120'], accounts['4100'], '650000'),
            tx(12, 'revenue', 2, 'Penjualan tunai harian 2', accounts['1120'], accounts['4100'], '720000'),
            tx(13, 'revenue', 3, 'Pendapatan jasa konsultasi', accounts['1120'], accounts['4200'], '1500000'),
            tx(14, 'revenue', 4, 'Penjualan tunai harian 3', accounts['1110'], accounts['4100'], '430000'),
            tx(15, 'revenue', 5, 'Pendapatan lain-lain', accounts['1120'], accounts['4200'], '350000'),
        ]
        expenses = [
            tx(16, 'expense', 1, 'Pembayaran gaji karyawan', accounts['6100'], accounts['1120'], '1800000'),
            tx(17, 'expense', 2, 'Pembayaran sewa toko', accounts['6200'], accounts['1120'], '1200000'),
            tx(18, 'expense', 3, 'Pembayaran listrik dan air', accounts['6300'], accounts['1120'], '475000'),
            tx(19, 'expense', 4, 'Biaya transportasi operasional', accounts['6400'], accounts['1110'], '225000'),
            tx(20, 'expense', 5, 'Beban operasional lain-lain', accounts['6900'], accounts['1120'], '310000'),
        ]
        depreciation = [
            tx(21, 'depreciation', 1, 'Depresiasi laptop operasional', accounts['6500'], accounts['1590'], '250000'),
            tx(22, 'depreciation', 2, 'Depresiasi kendaraan operasional', accounts['6500'], accounts['1590'], '600000'),
            tx(23, 'depreciation', 3, 'Depresiasi etalase toko', accounts['6500'], accounts['1590'], '175000'),
            tx(24, 'depreciation', 4, 'Depresiasi printer dan scanner', accounts['6500'], accounts['1590'], '125000'),
            tx(25, 'depreciation', 5, 'Depresiasi peralatan kantor', accounts['6500'], accounts['1590'], '200000'),
        ]
        return cash_bank + receivables + revenue + expenses + depreciation
