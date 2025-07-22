"""
AppConfig for the transactions application.
"""
from django.apps import AppConfig


class TransactionsConfig(AppConfig):
    """
    Configuration class for the transactions Django application.
    """
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'transactions'
