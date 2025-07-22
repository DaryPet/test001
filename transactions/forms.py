"""
Django forms for the transactions application.
"""
from django import forms
from .models import Transaction

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
                attrs={'class': 'form-control', 'step': '0.01', 'min': '0.01'}
                ),
            'type': forms.Select(attrs={'class': 'form-select'}),
        }
