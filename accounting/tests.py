from datetime import date

from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.test import Client, TestCase

from accounts.models import User
from accounting.models import Account, AccountingPeriod, AccountPeriodBalance, CashFlowCategory, FinancialReportTemplate, JournalEntry
from accounting.services import create_draft_journal, post_journal, close_period, trial_balance, update_draft_journal
from companies.services import create_company


class AccountingCoreTests(TestCase):
    def setUp(self):
        self.company = create_company('Test UMKM')
        self.user = User.objects.create_user(username='owner', password='secret', company=self.company)
        self.bank = Account.objects.get(company=self.company, code='1120')
        self.modal = Account.objects.get(company=self.company, code='3100')

    def test_company_bootstrap_creates_default_core_data(self):
        self.assertEqual(self.company.base_currency, 'IDR')
        self.assertEqual(self.company.roles.count(), 4)
        self.assertGreaterEqual(self.company.accounts.count(), 20)
        self.assertEqual(self.company.periods.filter(year=date.today().year).count(), 12)
        self.assertTrue(self.company.modules.get(key='core_accounting').is_active)
        self.assertFalse(self.company.modules.get(key='cash_bank').is_active)
        self.assertTrue(
            self.company.financial_report_templates.filter(
                report_type=FinancialReportTemplate.INCOME_STATEMENT,
                is_default=True,
            ).exists()
        )
        self.assertTrue(
            self.company.financial_report_templates.filter(
                report_type=FinancialReportTemplate.BALANCE_SHEET,
                is_default=True,
            ).exists()
        )
        self.assertEqual(self.company.cash_flow_categories.count(), 7)
        self.assertTrue(self.company.account_cash_flow_mappings.filter(account__code='4100').exists())

    def test_post_balanced_journal_updates_trial_balance(self):
        entry = create_draft_journal(
            self.company,
            date(2026, 6, 15),
            'Setoran modal',
            [
                {'account': self.bank, 'debit': '1000000', 'credit': '0'},
                {'account': self.modal, 'debit': '0', 'credit': '1000000'},
            ],
            user=self.user,
        )

        posted = post_journal(entry, user=self.user)
        balance = trial_balance(self.company, end_date=date(2026, 6, 30))

        self.assertEqual(posted.status, JournalEntry.POSTED)
        self.assertEqual(balance['total_debit'], balance['total_credit'])

    def test_unbalanced_journal_is_rejected(self):
        with self.assertRaises(ValidationError):
            create_draft_journal(
                self.company,
                date(2026, 6, 15),
                'Tidak balance',
                [
                    {'account': self.bank, 'debit': '1000000', 'credit': '0'},
                    {'account': self.modal, 'debit': '0', 'credit': '900000'},
                ],
                user=self.user,
            )

    def test_close_period_rejects_draft_journals(self):
        entry = create_draft_journal(
            self.company,
            date(2026, 6, 15),
            'Draft',
            [
                {'account': self.bank, 'debit': '1000000', 'credit': '0'},
                {'account': self.modal, 'debit': '0', 'credit': '1000000'},
            ],
            user=self.user,
        )
        period = AccountingPeriod.objects.get(company=self.company, year=2026, month=6)

        with self.assertRaises(ValidationError):
            close_period(period, user=self.user)

        self.assertEqual(entry.status, JournalEntry.DRAFT)

    def test_close_period_creates_account_period_balances(self):
        june_entry = create_draft_journal(
            self.company,
            date(2026, 6, 15),
            'Setoran modal',
            [
                {'account': self.bank, 'debit': '1000000', 'credit': '0'},
                {'account': self.modal, 'debit': '0', 'credit': '1000000'},
            ],
            user=self.user,
        )
        post_journal(june_entry, user=self.user)
        june = AccountingPeriod.objects.get(company=self.company, year=2026, month=6)

        close_period(june, user=self.user)

        bank_balance = AccountPeriodBalance.objects.get(period=june, account=self.bank)
        modal_balance = AccountPeriodBalance.objects.get(period=june, account=self.modal)
        self.assertEqual(bank_balance.opening_debit, 0)
        self.assertEqual(bank_balance.movement_debit, 1000000)
        self.assertEqual(bank_balance.closing_debit, 1000000)
        self.assertEqual(modal_balance.movement_credit, 1000000)
        self.assertEqual(modal_balance.closing_credit, 1000000)

    def test_next_period_balance_uses_previous_closing_as_opening(self):
        june_entry = create_draft_journal(
            self.company,
            date(2026, 6, 15),
            'Setoran modal Juni',
            [
                {'account': self.bank, 'debit': '1000000', 'credit': '0'},
                {'account': self.modal, 'debit': '0', 'credit': '1000000'},
            ],
            user=self.user,
        )
        post_journal(june_entry, user=self.user)
        close_period(AccountingPeriod.objects.get(company=self.company, year=2026, month=6), user=self.user)

        july_entry = create_draft_journal(
            self.company,
            date(2026, 7, 1),
            'Setoran modal Juli',
            [
                {'account': self.bank, 'debit': '500000', 'credit': '0'},
                {'account': self.modal, 'debit': '0', 'credit': '500000'},
            ],
            user=self.user,
        )
        post_journal(july_entry, user=self.user)
        july = AccountingPeriod.objects.get(company=self.company, year=2026, month=7)

        close_period(july, user=self.user)

        bank_balance = AccountPeriodBalance.objects.get(period=july, account=self.bank)
        self.assertEqual(bank_balance.opening_debit, 1000000)
        self.assertEqual(bank_balance.movement_debit, 500000)
        self.assertEqual(bank_balance.closing_debit, 1500000)

    def test_seed_sample_transactions_creates_twenty_five_posted_journals_once(self):
        call_command(
            'seed_sample_transactions',
            company=self.company.name,
            username=self.user.username,
            year=2026,
            month=6,
            verbosity=0,
        )
        call_command(
            'seed_sample_transactions',
            company=self.company.name,
            username=self.user.username,
            year=2026,
            month=6,
            verbosity=0,
        )

        seeded = JournalEntry.objects.filter(company=self.company, source_module='sample_seed')

        self.assertEqual(seeded.count(), 25)
        self.assertEqual(seeded.filter(status=JournalEntry.POSTED).count(), 25)

    def test_balance_sheet_page_renders_account_rows(self):
        entry = create_draft_journal(
            self.company,
            date(2026, 6, 15),
            'Setoran modal',
            [
                {'account': self.bank, 'debit': '1000000', 'credit': '0'},
                {'account': self.modal, 'debit': '0', 'credit': '1000000'},
            ],
            user=self.user,
        )
        post_journal(entry, user=self.user)
        client = Client()
        client.force_login(self.user)

        response = client.get('/accounting/reports/balance-sheet/')

        self.assertContains(response, 'Bank')
        self.assertContains(response, 'Modal Pemilik')

    def test_draft_journal_can_be_edited(self):
        entry = create_draft_journal(
            self.company,
            date(2026, 6, 15),
            'Setoran modal',
            [
                {'account': self.bank, 'debit': '1000000', 'credit': '0'},
                {'account': self.modal, 'debit': '0', 'credit': '1000000'},
            ],
            user=self.user,
        )

        update_draft_journal(
            entry,
            date(2026, 6, 16),
            'Setoran modal revisi',
            [
                {'account': self.bank, 'debit': '1500000', 'credit': '0'},
                {'account': self.modal, 'debit': '0', 'credit': '1500000'},
            ],
            user=self.user,
        )
        entry.refresh_from_db()

        self.assertEqual(entry.date, date(2026, 6, 16))
        self.assertEqual(entry.memo, 'Setoran modal revisi')
        self.assertEqual(entry.total_debit, entry.total_credit)
        self.assertEqual(entry.total_debit, 1500000)

    def test_posted_journal_edit_page_redirects_to_detail(self):
        entry = create_draft_journal(
            self.company,
            date(2026, 6, 15),
            'Setoran modal',
            [
                {'account': self.bank, 'debit': '1000000', 'credit': '0'},
                {'account': self.modal, 'debit': '0', 'credit': '1000000'},
            ],
            user=self.user,
        )
        post_journal(entry, user=self.user)
        client = Client()
        client.force_login(self.user)

        response = client.get(f'/accounting/journals/{entry.uuid}/edit/')

        self.assertRedirects(response, f'/accounting/journals/{entry.uuid}/')

    def test_journal_list_is_paginated_by_twenty_rows(self):
        for index in range(21):
            create_draft_journal(
                self.company,
                date(2026, 6, 15),
                f'Jurnal pagination {index + 1}',
                [
                    {'account': self.bank, 'debit': '1000', 'credit': '0'},
                    {'account': self.modal, 'debit': '0', 'credit': '1000'},
                ],
                user=self.user,
            )
        client = Client()
        client.force_login(self.user)

        page_one = client.get('/accounting/journals/')
        page_two = client.get('/accounting/journals/?page=2')

        self.assertContains(page_one, 'Menampilkan 1-20 dari 21 jurnal')
        self.assertEqual(len(page_one.context['journals']), 20)
        self.assertContains(page_two, 'Menampilkan 21-21 dari 21 jurnal')
        self.assertEqual(len(page_two.context['journals']), 1)

    def test_income_statement_uses_report_template(self):
        entry = create_draft_journal(
            self.company,
            date(2026, 6, 15),
            'Penjualan tunai',
            [
                {'account': self.bank, 'debit': '1000000', 'credit': '0'},
                {'account': Account.objects.get(company=self.company, code='4100'), 'debit': '0', 'credit': '1000000'},
            ],
            user=self.user,
        )
        post_journal(entry, user=self.user)
        client = Client()
        client.force_login(self.user)

        response = client.get('/accounting/reports/income-statement/?start_date=2026-06-01&end_date=2026-06-30')

        self.assertContains(response, 'Total Pendapatan')
        self.assertContains(response, 'Laba/Rugi Bersih')
        self.assertContains(response, '1.000.000')

    def test_balance_sheet_uses_report_template(self):
        entry = create_draft_journal(
            self.company,
            date(2026, 6, 15),
            'Setoran modal',
            [
                {'account': self.bank, 'debit': '1000000', 'credit': '0'},
                {'account': self.modal, 'debit': '0', 'credit': '1000000'},
            ],
            user=self.user,
        )
        post_journal(entry, user=self.user)
        client = Client()
        client.force_login(self.user)

        response = client.get('/accounting/reports/balance-sheet/?as_of_date=2026-06-30')

        self.assertContains(response, 'Total Aset')
        self.assertContains(response, 'Total Liabilitas dan Ekuitas')
        self.assertContains(response, '1.000.000')
        self.assertContains(response, 'name="as_of_date"')
        self.assertNotContains(response, 'name="start_date"')

    def test_cash_flow_statement_groups_core_journals_by_activity(self):
        aset_tetap = Account.objects.get(company=self.company, code='1500')
        pinjaman = Account.objects.get(company=self.company, code='2300')
        penjualan = Account.objects.get(company=self.company, code='4100')
        for memo, debit, credit in [
            ('Penjualan tunai', self.bank, penjualan),
            ('Pembelian aset tetap', aset_tetap, self.bank),
            ('Pinjaman diterima', self.bank, pinjaman),
        ]:
            entry = create_draft_journal(
                self.company,
                date(2026, 6, 15),
                memo,
                [
                    {'account': debit, 'debit': '1000000', 'credit': '0'},
                    {'account': credit, 'debit': '0', 'credit': '1000000'},
                ],
                user=self.user,
            )
            post_journal(entry, user=self.user)
        client = Client()
        client.force_login(self.user)

        response = client.get('/accounting/reports/cash-flow/?start_date=2026-06-01&end_date=2026-06-30')

        self.assertContains(response, 'ARUS KAS DARI AKTIVITAS OPERASI')
        self.assertContains(response, 'ARUS KAS DARI AKTIVITAS INVESTASI')
        self.assertContains(response, 'ARUS KAS DARI AKTIVITAS PENDANAAN')
        self.assertContains(response, 'Penerimaan dari pelanggan dan pendapatan')
        self.assertContains(response, 'Pembelian/penjualan aset tetap')
        self.assertContains(response, 'Pinjaman diterima/dibayar')

    def test_general_ledger_is_paginated_and_core_journal_number_links_to_detail(self):
        first_entry = None
        for index in range(11):
            entry = create_draft_journal(
                self.company,
                date(2026, 6, 15),
                f'Buku besar pagination {index + 1}',
                [
                    {'account': self.bank, 'debit': '1000', 'credit': '0'},
                    {'account': self.modal, 'debit': '0', 'credit': '1000'},
                ],
                user=self.user,
            )
            post_journal(entry, user=self.user)
            first_entry = first_entry or entry
        client = Client()
        client.force_login(self.user)

        page_one = client.get('/accounting/reports/general-ledger/')
        page_two = client.get('/accounting/reports/general-ledger/?page=2')

        self.assertContains(page_one, 'Menampilkan 1-20 dari 22 baris buku besar')
        self.assertEqual(len(page_one.context['lines']), 20)
        self.assertContains(page_two, 'Menampilkan 21-22 dari 22 baris buku besar')
        self.assertEqual(len(page_two.context['lines']), 2)
        self.assertContains(page_one, f'/accounting/journals/{first_entry.uuid}/')

# Create your tests here.
