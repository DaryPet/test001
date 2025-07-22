"""
URL configuration for the ledgerly project.

This module defines the URL patterns for the entire project.
It includes Django admin URLs and integrates URLs from the 'transactions' app.
"""

from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('transactions.urls')),
]
