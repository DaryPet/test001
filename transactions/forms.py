"""
Django forms for the transactions application.
"""
from django import forms
from .models import Transaction
from decimal import Decimal

class TransactionForm(forms.ModelForm):
    """
    Form for creating and updating Transaction objects.
    """
    class Meta:
        """
        Meta class for TransactionForm to define model and fields.
        """
        model = Transaction
        fields = ['type', 'amount']
        widgets = {
            'amount': forms.NumberInput(
                attrs={'class': 'form-control', 'step': '0.01', 'min': '0.01', 'id': 'amountInput'}
                ),
            'type': forms.Select(attrs={'class': 'form-select', 'id': 'typeSelect'}),
        }

    def clean_amount(self):
        amount = self.cleaned_data.get('amount')
        if amount is None:
            raise forms.ValidationError("Please, eneter amount")
        if amount <= Decimal('0.00'):
            raise forms.ValidationError('Amount should be more then 0')  
        return amount

