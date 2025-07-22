"""
Django views for managing transactions.
Handles listing, adding, and importing transactions.
"""
import os
import json
import logging
import uuid
from decimal import Decimal
from datetime import datetime, time
import requests
from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.utils import timezone
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from .models import Transaction, recalculate_running_balance
from .forms import TransactionForm


logger = logging.getLogger(__name__)

API_URL = os.environ.get('MOCK_API_URL')
if not API_URL:
    raise RuntimeError('MOCK_API_URL not declared!')

def transaction_list(request):
    """
    Displays a paginated list of transactions, with optional filtering by type.
    Supports AJAX requests for infinite scrolling/dynamic updates.
    """
    transactions_list = Transaction.objects.all().order_by('-created_at', '-id')

    filter_type = request.GET.get('type')
    if filter_type in ['deposit', 'expense']:
        transactions_list = transactions_list.filter(type=filter_type)

    paginator = Paginator(transactions_list, 10)
    page_number = request.GET.get('page', 1)

    try:
        page_obj = paginator.page(page_number)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            last_transaction_for_empty_page = transactions_list.first()
            current_total_balance = float(last_transaction_for_empty_page.running_balance) if last_transaction_for_empty_page else 0.00
            return JsonResponse({
                'transactions': [],
                'has_next': False, 
                'total_balance': current_total_balance
                })

        page_obj = paginator.page(paginator.num_pages)
    
    last_transaction_for_html_context = transactions_list.first() 
    if last_transaction_for_html_context:
        total_balance_for_context = last_transaction_for_html_context.running_balance
    else:
        total_balance_for_context = Decimal('0.00')

    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        transactions_data = []
        for t in page_obj.object_list:
            transactions_data.append({
                'code': t.code or "N/A",
                'created_at': t.created_at.strftime("%d/%m/%Y %H:%M"),
                'type': t.type,
                'type_display': t.get_type_display(),
                'amount': float(t.amount),
                'amount_display': f"{'+' if t.amount > 0 else ''}{t.amount:,.2f}",
                'running_balance': float(t.running_balance),
            })
       
        current_total_balance_for_ajax = float(total_balance_for_context)
        return JsonResponse({
            'transactions': transactions_data,
            'has_next': page_obj.has_next(),
            'total_balance': current_total_balance_for_ajax,
            'next_page_number': page_obj.next_page_number() if page_obj.has_next() else None,
        })

    context = {
        'transactions': page_obj.object_list,
        'total_balance': total_balance_for_context,
        'page_obj': page_obj,
    }
    return render(request, 'transactions/index.html', context)


@require_POST
@csrf_exempt
def add_transaction(request):
    """
    Adds a new transaction sent via AJAX, with additional validations.
    """
    try:
        data = json.loads(request.body)

        form = TransactionForm(data)
        if form.is_valid():
            transaction = form.save(commit=False)

            last_transaction_for_check = Transaction.objects.order_by('-created_at', '-id').first()
            current_total_balance_for_validation = last_transaction_for_check.running_balance if last_transaction_for_check else Decimal('0.00')

            if transaction.type == 'expense':
                if current_total_balance_for_validation < abs(transaction.amount):
                    return JsonResponse({'error': {'amount': ['Not enough balance']}, 'success': False}, status=400)
        
            if transaction.type == 'expense':
                today = timezone.now().date()
                start_of_day = timezone.make_aware(datetime.combine(today, time.min), timezone.get_current_timezone())
                end_of_day = timezone.make_aware(datetime.combine(today, time.max), timezone.get_current_timezone())

                expenses_today_count = Transaction.objects.filter(
                    type='expense',
                    created_at__gte=start_of_day,
                    created_at__lte=end_of_day
                ).count()

                TRANSACTION_LIMIT_PER_DAY = 200
                if (expenses_today_count + 1) > TRANSACTION_LIMIT_PER_DAY:
                    return JsonResponse({
                        'error': 
                        {'type': 
                        [f'Too many expenses today.']}, 
                        'success': False}, status=400)

            transaction.code = f"{uuid.uuid4().hex[:8].upper()}"
            transaction.is_api = False

            transaction.save()
            recalculate_running_balance()
            new_transaction = Transaction.objects.get(id=transaction.id)

            last_transaction_after_add = Transaction.objects.order_by('-created_at', '-id').first()
            total_balance_for_add_response = float(last_transaction_after_add.running_balance) if last_transaction_after_add else 0.00
 
            return JsonResponse({
                'message': 'Transaction successfully executed.',
                'success': True,
                'total_balance': total_balance_for_add_response,
                'new_transaction': {
                    'code': new_transaction.code,
                    'created_at': new_transaction.created_at.strftime("%d/%m/%Y %H:%M"),
                    'type': new_transaction.type,
                    'type_display': new_transaction.get_type_display(),
                    'amount': float(new_transaction.amount),
                    'amount_display': f"{'+' if new_transaction.amount > 0 else ''}{new_transaction.amount:,.2f}",
                    'running_balance': float(new_transaction.running_balance),
                }
            })
        else:
            errors = {field: form.errors[field] for field in form.errors}
            return JsonResponse({'error': errors, 'success': False}, status=400)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Incorrect JSON request.', 'success': False}, status=400)
    except Exception as e:
        logger.exception("Error while adding transaction via AJAX")
        return JsonResponse({'error': f'Unknown error: {str(e)}', 'success': False}, status=500)


@require_POST
@csrf_exempt
def import_transactions(request):
    """
    Imports transactions from an external MockAPI.
    """
    api_url = API_URL

    if not api_url:
        return JsonResponse({'error': 'API URL cannot be empty', 'success': False}, status=400)

    try:
        response = requests.get(api_url)
        response.raise_for_status()
        api_data = response.json()

        imported_count = 0
        skipped_count = 0
        new_transactions_to_create = []

        for item in api_data:
            item_id = item.get('id')
            if not item_id:
                logger.warning(f"Skipping API transaction without 'id': {item}")
                skipped_count += 1
                continue

            if Transaction.objects.filter(code=item_id).exists():
                skipped_count += 1
                continue

            try:
                amount = Decimal(str(item.get('amount', '0')))
                transaction_type = item.get('type')

                created_at_str = item.get('createdAt')
                created_at = None
                if created_at_str:
                    try:
                        created_at = timezone.datetime.fromisoformat(created_at_str.replace('Z', '+00:00'))
                    except ValueError:
                        logger.warning(f"Error parsing date: {created_at_str}. Using current time.")
                        created_at = timezone.now()
                if transaction_type == 'expense' and amount > 0:
                    amount = -amount
                elif transaction_type == 'deposit' and amount < 0:
                    amount = abs(amount)

                new_transactions_to_create.append(
                    Transaction(
                        code=item_id,
                        type=transaction_type,
                        amount=amount,
                        created_at=created_at,
                        is_api=True
                    )
                )
                imported_count += 1
            except (ValueError, KeyError) as e:
                logger.error(f"Error processing transaction from API: {item}. Error: {e}")
                skipped_count += 1

        if new_transactions_to_create:
            Transaction.objects.bulk_create(new_transactions_to_create)
            recalculate_running_balance()

        return JsonResponse({
            'message': f'Imported {imported_count} transactions. Skipped {skipped_count}.',
            'success': True
        })

    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching API: {e}")
        return JsonResponse({'error': f'Error connecting to API: {e}. Check the URL or your internet connection.', 'success': False}, status=500)
    except json.JSONDecodeError as e:
        logger.error(f"Error parsing JSON response from API: {e}")
        return JsonResponse({'error': f'Error parsing JSON response: {e}. The API might have returned invalid data.', 'success': False}, status=500)
    except Exception as e:
        logger.exception("Unexpected error in import_transactions")
        return JsonResponse({'error': f'An unexpected error occurred: {str(e)}', 'success': False}, status=500)
    