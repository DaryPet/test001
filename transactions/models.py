"""
Defines the Transaction model and related utility functions for the transactions application.
"""
from decimal import Decimal
from django.db import models
from django.utils import timezone

class Transaction(models.Model):
    """
    Represents a financial transaction, either a deposit or an expense.
    Includes a running balance calculated based on chronological order.
    """
    TRANSACTION_TYPES = [
        ('deposit', 'Deposit'),
        ('expense', 'Expense'),
    ]

    code = models.CharField(max_length=100, unique=True, blank=True, null=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    type = models.CharField(max_length=10, choices=TRANSACTION_TYPES)
    created_at = models.DateTimeField(null=True, blank=True)
    running_balance = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    is_api = models.BooleanField(default=False)

    class Meta:
        """
        Meta options for the Transaction model.
        Defines default ordering for correct running balance calculation.
        """
        ordering = ['created_at', 'id']

    def save(self, *args, **kwargs):
        """
        Overrides the default save method to:
        1. Set 'created_at' for new transactions if not provided.
        2. Adjust the sign of 'amount' based on 'type' (deposits positive, expenses negative).
        3. Recalculate the running balance for all transactions after saving.
        """
        if not self.pk and not self.created_at:
            self.created_at = timezone.now()

        if self.type == 'expense' and self.amount > 0:
            self.amount = -self.amount
        elif self.type == 'deposit' and self.amount < 0:
            self.amount = abs(self.amount)

        super().save(*args, **kwargs)

        recalculate_running_balance()

    def __str__(self):
        """
        String representation of the Transaction instance.
        """
        created_at_str = (
            self.created_at.strftime('%Y-%m-%d %H:%M') if self.created_at else 'N/A'
        )
        return f"{self.get_type_display()} - {self.amount} ({created_at_str})"
        # return f"{self.get_type_display()} - {self.amount} ({self.created_at.strftime('%Y-%m-%d %H:%M') if self.created_at else 'N/A'})"

    def get_type_display(self):
        """
        Returns the human-readable display name for the transaction type.
        """
        return dict(self.TRANSACTION_TYPES).get(self.type, self.type)

def recalculate_running_balance():
    """
    Recalculates the 'running_balance' for all transactions in the database
    in chronological order. Called after each transaction save to ensure accuracy.
    """
    transactions = Transaction.objects.order_by('created_at', 'id')
    current_balance = Decimal('0.00')

    transactions_to_update = []

    for transaction in transactions:
        current_balance += transaction.amount
        if transaction.running_balance != current_balance:
            transaction.running_balance = current_balance
            transactions_to_update.append(transaction)

    if transactions_to_update:
        Transaction.objects.bulk_update(transactions_to_update, ['running_balance'])
