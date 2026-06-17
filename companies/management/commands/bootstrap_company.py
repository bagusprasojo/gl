from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from accounts.models import Role, User
from companies.services import create_company


class Command(BaseCommand):
    help = 'Create a company with default roles, UMKM chart of accounts, periods, modules, and owner user.'

    def add_arguments(self, parser):
        parser.add_argument('--company', required=True)
        parser.add_argument('--username', required=True)
        parser.add_argument('--password', required=True)
        parser.add_argument('--email', default='')

    @transaction.atomic
    def handle(self, *args, **options):
        if User.objects.filter(username=options['username']).exists():
            raise CommandError('Username already exists.')
        company = create_company(options['company'])
        owner_role = Role.objects.get(company=company, key=Role.OWNER)
        user = User.objects.create_user(
            username=options['username'],
            email=options['email'],
            password=options['password'],
            company=company,
            role=owner_role,
            is_staff=True,
            is_superuser=True,
        )
        self.stdout.write(self.style.SUCCESS(f'Created company "{company.name}" and owner "{user.username}".'))
