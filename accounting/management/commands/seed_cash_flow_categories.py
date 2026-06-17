from django.core.management.base import BaseCommand, CommandError

from accounting.services import seed_default_cash_flow_categories
from companies.models import Company


class Command(BaseCommand):
    help = 'Seed default core-accounting cash flow categories and account mappings.'

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
            seed_default_cash_flow_categories(company)
            count += 1
        self.stdout.write(self.style.SUCCESS(f'Seeded cash flow categories for {count} company(s).'))
