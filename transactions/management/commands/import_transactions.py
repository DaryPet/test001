"""
Django management command to import transactions from an external API.
"""
import os
import requests
from django.core.management.base import BaseCommand
from django.utils.dateparse import parse_datetime
from transactions.models import Transaction

API_URL = os.environ.get('MOCK_API_URL')
if not API_URL:
    raise RuntimeError('MOCK_API_URL environment variable is not set!')

class Command(BaseCommand):
    """
    Management command to import transactions from a mock API.

    This command fetches transaction data from a configurable API endpoint.
    It checks for existing transactions by 'code' to prevent duplicates
    and efficiently saves new transactions using bulk_create.
    """
    help = 'Imports transactions from an external API'

    def handle(self, *args, **options):
        """
        Handles the execution of the import command.

        Fetches data from the API, processes it, and saves new transactions.
        Logs success, warnings, and errors to the console.
        """
        self.stdout.write('Loading transactions from API...')
        try:
            response = requests.get(API_URL, timeout=10)
            response.raise_for_status()
        except requests.exceptions.Timeout:
            self.stderr.write(self.style.ERROR(
                'Error requesting API: Request timed out.'
            ))
            return
        except requests.RequestException as e:
            self.stderr.write(self.style.ERROR(f'Error requesting API: {e}'))
            return

        try:
            data = response.json()
        except ValueError as e:
            self.stderr.write(self.style.ERROR(
                f'Error decoding JSON from API response: {e}'
            ))
            return

        transactions_to_create = []
        # Fetch existing codes once for efficiency
        existing_codes = set(Transaction.objects.values_list('code', flat=True))

        for item in data:
            required_keys = ['id', 'amount', 'type', 'createdAt']
            if not all(key in item for key in required_keys):
                self.stderr.write(self.style.WARNING(
                    f'Skipping item due to missing data: {item}'
                ))
                continue

            transaction_code = item['id']
            if transaction_code in existing_codes:
                self.stdout.write(
                    f'Skipping existing transaction: {transaction_code}'
                )
                continue

            try:
                transaction = Transaction(
                    code=transaction_code,
                    amount=item['amount'],
                    type=item['type'],
                    created_at=parse_datetime(item['createdAt']),
                    is_api=True,
                )
                transactions_to_create.append(transaction)
            except (ValueError, TypeError) as e:
                self.stderr.write(self.style.ERROR(
                    f'Error processing data for {transaction_code}: {e} - '
                    f'Data: {item}'
                ))
                continue

        if transactions_to_create:
            Transaction.objects.bulk_create(transactions_to_create, ignore_conflicts=True)
            imported_count = len(transactions_to_create)
            self.stdout.write(self.style.SUCCESS(
                f'Imported {imported_count} new transactions.'
            ))
        else:
            self.stdout.write(
                self.style.WARNING('No new transactions to import.')
            )
