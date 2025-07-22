"""
URL configuration for the transactions application.
Defines URL patterns for transaction-related views.
"""
from django.urls import path
from . import views

urlpatterns = [
    path('', views.transaction_list, name='transaction_list'),
    path('add/', views.add_transaction, name='add_transaction'),
    path('import/', views.import_transactions, name='import_transactions'),
]
