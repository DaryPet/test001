"""
Tests for the transactions application models and views.
"""
import os
import json
import uuid
from datetime import datetime
from decimal import Decimal
from unittest.mock import patch, Mock
import requests
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from .models import Transaction, recalculate_running_balance

MOCK_API_TEST_URL = "http://test-api.example.com/transactions"

class TransactionModelTest(TestCase):
    """
    Tests for models Transaction.
    """
    def setUp(self):
        """Set up for TransactionModelTest."""
        Transaction.objects.all().delete()

    def test_transaction_creation(self):
        """Verifies the creation of a regular transaction."""
        initial_count = Transaction.objects.count()
        transaction = Transaction.objects.create(
            code=str(uuid.uuid4()),
            type='deposit',
            amount=Decimal('100.00'),
            created_at=timezone.now(),
            is_api=False,
            running_balance=Decimal('100.00')
        )
        self.assertEqual(Transaction.objects.count(), initial_count + 1)
        self.assertEqual(transaction.type, 'deposit')
        self.assertEqual(transaction.amount, Decimal('100.00'))
        self.assertFalse(transaction.is_api)
        self.assertIsNotNone(transaction.running_balance)

    def test_get_type_display(self):
        """Verifies the get_type_display method."""
        transaction = Transaction.objects.create(
            code=str(uuid.uuid4()),
            type='expense',
            amount=Decimal('50.00'),
            created_at=timezone.now(),
            is_api=False,
            running_balance=Decimal('0.00')
        )
        self.assertEqual(transaction.get_type_display(), 'Expense')

    def test_recalculate_running_balance(self):
        """Verifies the correctness of running_balance recalculation."""
        Transaction.objects.all().delete()

        t1 = Transaction.objects.create(
            code='TXN001', type='deposit', amount=Decimal('100.00'), created_at=timezone.now() - timezone.timedelta(days=2), is_api=False
        )
        t2 = Transaction.objects.create(
            code='TXN002', type='expense', amount=Decimal('30.00'), created_at=timezone.now() - timezone.timedelta(days=1), is_api=False
        )
        t3 = Transaction.objects.create(
            code='TXN003', type='deposit', amount=Decimal('50.00'), created_at=timezone.now(), is_api=False
        )

        recalculate_running_balance()

        t1.refresh_from_db()
        t2.refresh_from_db()
        t3.refresh_from_db()

        self.assertEqual(t1.running_balance, Decimal('100.00'))
        self.assertEqual(t2.running_balance, Decimal('70.00'))
        self.assertEqual(t3.running_balance, Decimal('120.00'))

        t4 = Transaction.objects.create(
            code='TXN004', type='expense', amount=Decimal('20.00'), created_at=timezone.now() + timezone.timedelta(seconds=1), is_api=False
        )
        recalculate_running_balance()
        t1.refresh_from_db()
        t2.refresh_from_db()
        t3.refresh_from_db()
        t4.refresh_from_db()
        self.assertEqual(t1.running_balance, Decimal('100.00'))
        self.assertEqual(t2.running_balance, Decimal('70.00'))
        self.assertEqual(t3.running_balance, Decimal('120.00'))
        self.assertEqual(t4.running_balance, Decimal('100.00'))


class TransactionViewTest(TestCase):
    """
    Tests for Views.
    """
    def setUp(self):
        self.client = Client()
        self.transaction_list_url = reverse('transaction_list')
        self.add_transaction_url = reverse('add_transaction')
        self.import_transactions_url = reverse('import_transactions')

        self.t1 = Transaction.objects.create(
            code='TXN001', type='deposit', amount=Decimal('100.00'), created_at=timezone.now() - timezone.timedelta(days=3), is_api=False
        )
        self.t2 = Transaction.objects.create(
            code='TXN002', type='expense', amount=Decimal('20.00'), created_at=timezone.now() - timezone.timedelta(days=2), is_api=False
        )
        self.t3 = Transaction.objects.create(
            code='TXN003', type='deposit', amount=Decimal('50.00'), created_at=timezone.now() - timezone.timedelta(days=1), is_api=False
        )
        recalculate_running_balance()
        self.t1.refresh_from_db()
        self.t2.refresh_from_db()
        self.t3.refresh_from_db()


    # --- Test for transaction_list ---
    def test_transaction_list_html_response(self):
        """Verifies that the transaction list HTML page loads correctly."""
        response = self.client.get(self.transaction_list_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'transactions/index.html')
        self.assertContains(response, 'Transaction Tracker')
        self.assertContains(response, 'TXN003')

    def test_transaction_list_ajax_response_first_page(self):
        """Verifies AJAX response for the first page of transactions."""
        for i in range(4, 17):
            Transaction.objects.create(
                code=f'TXN{i:03d}',
                type='deposit' if i % 2 == 0 else 'expense',
                amount=Decimal(f'{i}.00'),
                created_at=timezone.now() - timezone.timedelta(minutes=i),
                is_api=False
            )
        recalculate_running_balance()

        response = self.client.get(self.transaction_list_url, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertIn('transactions', data)
        self.assertIn('has_next', data)
        self.assertIn('total_balance', data)
        self.assertIn('next_page_number', data)

        self.assertEqual(len(data['transactions']), 10)
        self.assertTrue(data['has_next'])
        self.assertEqual(data['next_page_number'], 2)

    def test_transaction_list_ajax_response_next_page(self):
        """Verifies AJAX response for the next page of transactions."""
        for i in range(4, 17):
            Transaction.objects.create(
                code=f'TXN{i:03d}',
                type='deposit' if i % 2 == 0 else 'expense',
                amount=Decimal(f'{i}.00'),
                created_at=timezone.now() - timezone.timedelta(minutes=i),
                is_api=False
            )
        recalculate_running_balance()

        response = self.client.get(self.transaction_list_url, {'page': 2}, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertIn('transactions', data)
        self.assertEqual(len(data['transactions']), 6)
        self.assertFalse(data['has_next'])
        self.assertIsNone(data['next_page_number'])


    def test_transaction_list_filter_by_type_deposit(self):
        """Verifies transaction filtering by 'deposit' type."""
        Transaction.objects.create(code='D001', type='deposit', amount=Decimal('10.00'), created_at=timezone.now() + timezone.timedelta(seconds=1), is_api=False)
        Transaction.objects.create(code='E001', type='expense', amount=Decimal('5.00'), created_at=timezone.now() + timezone.timedelta(seconds=2), is_api=False)
        Transaction.objects.create(code='D002', type='deposit', amount=Decimal('20.00'), created_at=timezone.now() + timezone.timedelta(seconds=3), is_api=False)
        recalculate_running_balance()

        response = self.client.get(self.transaction_list_url, {'type': 'deposit'}, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertIn('transactions', data)
        self.assertEqual(len(data['transactions']), 4)
        for t in data['transactions']:
            self.assertEqual(t['type'], 'deposit')

    def test_transaction_list_filter_by_type_expense(self):
        """Verifies transaction filtering by 'expense' type."""
        Transaction.objects.create(code='D001', type='deposit', amount=Decimal('10.00'), created_at=timezone.now() + timezone.timedelta(seconds=1), is_api=False)
        Transaction.objects.create(code='E001', type='expense', amount=Decimal('5.00'), created_at=timezone.now() + timezone.timedelta(seconds=2), is_api=False)
        Transaction.objects.create(code='D002', type='deposit', amount=Decimal('20.00'), created_at=timezone.now() + timezone.timedelta(seconds=3), is_api=False)
        recalculate_running_balance()

        response = self.client.get(self.transaction_list_url, {'type': 'expense'}, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertIn('transactions', data)
        self.assertEqual(len(data['transactions']), 2)
        for t in data['transactions']:
            self.assertEqual(t['type'], 'expense')
    
    def test_transaction_list_filter_invalid_type(self):
        """Verifies that the filter is ignored for an invalid type."""
        response = self.client.get(self.transaction_list_url, {'type': 'invalid_type'}, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('transactions', data)
        self.assertEqual(len(data['transactions']), 3) 

    # --- Test for add_transaction ---
    def test_add_transaction_deposit_success(self):
        """Verifies successful addition of a deposit."""
        initial_count = Transaction.objects.count()
        response = self.client.post(
            self.add_transaction_url,
            json.dumps({'type': 'deposit', 'amount': 200.00}),
            content_type='application/json',
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertIn('new_transaction', data)
        self.assertEqual(Transaction.objects.count(), initial_count + 1)
        self.assertEqual(data['new_transaction']['type'], 'deposit')
        self.assertEqual(data['new_transaction']['amount'], 200.0)
        self.assertEqual(data['total_balance'], float(self.t3.running_balance + Decimal('200.00')))

    def test_add_transaction_expense_success(self):
        """Verifies successful addition of an expense with sufficient balance."""
        initial_count = Transaction.objects.count()
        response = self.client.post(
            self.add_transaction_url,
            json.dumps({'type': 'expense', 'amount': 10.00}),
            content_type='application/json',
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertIn('new_transaction', data)
        self.assertEqual(Transaction.objects.count(), initial_count + 1)
        self.assertEqual(data['new_transaction']['type'], 'expense')
        self.assertEqual(data['new_transaction']['amount'], -10.0)
        self.assertEqual(data['total_balance'], float(self.t3.running_balance - Decimal('10.00')))

    def test_add_transaction_expense_insufficient_balance(self):
        """Verifies adding an expense with insufficient balance."""
        response = self.client.post(
            self.add_transaction_url,
            json.dumps({'type': 'expense', 'amount': 200.00}),
            content_type='application/json',
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertFalse(data['success'])
        self.assertIn('Not enough balance', data['error']['amount'])
        self.assertEqual(Transaction.objects.count(), 3)

    @patch('django.utils.timezone.now')
    def test_add_transaction_expense_daily_limit(self, mock_now):
        """Verifies the daily expense limit."""
        test_date = timezone.make_aware(datetime(2025, 7, 22, 10, 0, 0))
        mock_now.return_value = test_date
        Transaction.objects.create(
            code='INITIAL_DEP',
            type='deposit',
            amount=Decimal('10000.00'),
            created_at=test_date - timezone.timedelta(days=1),
            is_api=False
        )
        recalculate_running_balance()
        for i in range(200):
            Transaction.objects.create(
                code=f'DAILYEXP{i:03d}',
                type='expense',
                amount=Decimal('1.00'),
                created_at=test_date - timezone.timedelta(seconds=i),
                is_api=False
            )
        recalculate_running_balance()
        response = self.client.post(
            self.add_transaction_url,
            json.dumps({'type': 'expense', 'amount': 1.00}),
            content_type='application/json',
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertFalse(data['success'])
        self.assertIn('Too many expenses today.', data['error']['type'][0])
        self.assertEqual(Transaction.objects.filter(type='expense', created_at__date=test_date.date()).count(), 200)


    # --- Tests for import_transactions ---
    @patch('requests.get') 
    @patch.dict(os.environ, {'MOCK_API_URL': MOCK_API_TEST_URL})
    def test_import_transactions_success(self, mock_get):
        """Verifies successful import of transactions from the API."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {'id': 'api-1', 'createdAt': '2025-01-01T10:00:00Z', 'amount': 50.00, 'type': 'deposit'},
            {'id': 'api-2', 'createdAt': '2025-01-02T11:00:00Z', 'amount': 25.00, 'type': 'expense'},
            {'id': 'api-3', 'createdAt': '2025-01-03T12:00:00Z', 'amount': 75.00, 'type': 'deposit'},
        ]
        mock_get.return_value = mock_response

        initial_count = Transaction.objects.count()
        response = self.client.post(
            self.import_transactions_url,
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertIn('Imported 3 transactions. Skipped 0.', data['message'])
        self.assertEqual(Transaction.objects.count(), initial_count + 3)

        api_txn = Transaction.objects.get(code='api-1')
        self.assertTrue(api_txn.is_api)
        self.assertEqual(api_txn.type, 'deposit')
        self.assertEqual(api_txn.amount, Decimal('50.00'))

        api_txn_expense = Transaction.objects.get(code='api-2')
        self.assertTrue(api_txn_expense.is_api)
        self.assertEqual(api_txn_expense.type, 'expense')
        self.assertEqual(api_txn_expense.amount, Decimal('-25.00'))
    @patch('requests.get')
    @patch.dict(os.environ, {'MOCK_API_URL': MOCK_API_TEST_URL})
    def test_import_transactions_skips_existing(self, mock_get):
        """Verifies that the import skips existing transactions."""
        Transaction.objects.create(
            code='api-1', type='deposit', amount=Decimal('10.00'), created_at=timezone.now(), is_api=True
        )
        initial_count = Transaction.objects.count()

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {'id': 'api-1', 'createdAt': '2025-01-01T10:00:00Z', 'amount': 50.00, 'type': 'deposit'},
            {'id': 'api-4', 'createdAt': '2025-01-04T13:00:00Z', 'amount': 100.00, 'type': 'deposit'},
        ]
        mock_get.return_value = mock_response

        response = self.client.post(
            self.import_transactions_url,
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertIn('Imported 1 transactions. Skipped 1.', data['message'])
        self.assertEqual(Transaction.objects.count(), initial_count + 1)

    @patch('requests.get')
    @patch.dict(os.environ, {'MOCK_API_URL': MOCK_API_TEST_URL})
    def test_import_transactions_api_error(self, mock_get):
        """Verifies error handling during API connection."""
        mock_get.side_effect = requests.exceptions.RequestException("Connection refused")

        response = self.client.post(
            self.import_transactions_url,
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        self.assertEqual(response.status_code, 500)
        data = response.json()
        self.assertFalse(data['success'])
        self.assertIn('Error connecting to API', data['error'])
        self.assertEqual(Transaction.objects.count(), 3)
