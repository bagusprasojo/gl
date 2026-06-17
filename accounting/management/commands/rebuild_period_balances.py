from django.core.management.base import BaseCommand, CommandError

from accounting.models import AccountingPeriod
from accounting.services import rebuild_account_period_balances
from companies.models import Company


class Command(BaseCommand):
    help = 'Rebuild account period balance snapshots for closed periods.'

    def add_arguments(self, parser):
        parser.add_argument('--company', help='Company name. Defaults to all active companies.')

    def handle(self, *args, **options):
        company_name = options.get('company')
        if company_name:
            companies = Company.objects.filter(name=company_name)
            if not companies.exists():
                raise CommandError(f'Company "{company_name}" not found.')
        else:
            companies = Company.objects.filter(is_active=True)

        count = 0
        for company in companies:
            periods = AccountingPeriod.objects.filter(
                company=company,
                status=AccountingPeriod.CLOSED,
            ).order_by('start_date')
            for period in periods:
                rebuild_account_period_balances(period)
                count += 1
        self.stdout.write(self.style.SUCCESS(f'Rebuilt account period balances for {count} closed period(s).'))
