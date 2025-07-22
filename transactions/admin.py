"""
Django admin site configuration for the transactions application.
"""
from django.contrib import admin
from .models import Transaction

admin.site.register(Transaction)
