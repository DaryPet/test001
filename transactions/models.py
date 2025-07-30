"""
Defines the Transaction model and related utility functions for the transactions application.
"""
import uuid
from decimal import Decimal
from django.db import models
from django.utils import timezone
from model_utils.models import TimeStampedModel

class Transaction(TimeStampedModel):
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
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    running_balance = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    # is_api = models.BooleanField(default=False)

    class Meta(TimeStampedModel.Meta):
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
        3. Recalculate the running balance for new transactions after saving.
        """
        is_new_record = not self.pk
        if is_new_record and not self.code:
            self.code = str(uuid.uuid4())

        if self.type == 'expense' and self.amount > 0:
            self.amount = -self.amount
        elif self.type == 'deposit' and self.amount < 0:
            self.amount = abs(self.amount)

        super().save(*args, **kwargs)

        if is_new_record:
            prev_transaction = Transaction.objects.filter(
                models.Q(created_at__lt=self.created_at) |
                (models.Q(created_at=self.created_at) & models.Q(id__lt=self.id))
            ).order_by('-created_at', "-id").first()

            if prev_transaction:
                self.running_balance = prev_transaction.running_balance + self.amount
            else:
                self. running_balance = self.amount

            Transaction.objects.filter(pk=self.pk).update(running_balance=self.running_balance)




    def __str__(self):
        """
        String representation of the Transaction instance.
        """
        created_at_str=self.created_at.strftime ('%Y-%m-%d %H:%M') if self.created_at else 'N/A'
        return f"{self.get_type_display()} - {self.amount} ({self.running_balance}) ({created_at_str})"
        # return f"{self.get_type_display()} - {self.amount} ({self.created_at.strftime('%Y-%m-%d %H:%M') if self.created_at else 'N/A'})"

    def get_type_display(self):
        """
        Returns the human-readable display name for the transaction type.
        """
        return dict(self.TRANSACTION_TYPES).get(self.type, self.type)
