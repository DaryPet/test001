
import os
import json
import logging
# import uuid
from decimal import Decimal
from datetime import datetime, time
import requests
from django.shortcuts import render
from django.http import JsonResponse
# from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.utils import timezone
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from .models import Transaction
from .forms import TransactionForm


LOGGER = logging.getLogger(__name__)

API_URL = os.environ.get('MOCK_API_URL')
if not API_URL:
    raise RuntimeError('MOCK_API_URL not declared!')

TRANSACTION_LIMIT_PER_DAY = 200


def transaction_list(request):
    """
    Displays a paginated list of transactions, with optional filtering by type.
    Supports AJAX requests for infinite scrolling/dynamic updates.
    """
    all_transactions_for_total_balance = Transaction.objects.all().order_by(
        '-created_at', '-id'
    )

    total_balance_across_all_transactions = Decimal('0.00')
    if all_transactions_for_total_balance.exists():
        total_balance_across_all_transactions = \
            all_transactions_for_total_balance.first().running_balance

    transactions_for_pagination = Transaction.objects.all().order_by(
        '-created_at', '-id'
    )

    filter_type = request.GET.get('type')
    if filter_type in ['deposit', 'expense']:
        transactions_for_pagination = \
            transactions_for_pagination.filter(type=filter_type)

    paginator = Paginator(transactions_for_pagination, 10)
    page_number = request.GET.get('page', 1)

    try:
        page_obj = paginator.page(page_number)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({
                'transactions': [],
                'has_next': False,
                'total_balance': float(total_balance_across_all_transactions)
            })
        page_obj = paginator.page(paginator.num_pages)

    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        transactions_data = []
        for transaction in page_obj.object_list:
            transactions_data.append({
                'code': transaction.code or "N/A",
                'created_at': transaction.created_at.strftime("%d/%m/%Y %H:%M"),
                'type': transaction.type,
                'type_display': transaction.get_type_display(),
                'amount': float(transaction.amount),
                'amount_display': f"{'+' if transaction.amount > 0 else ''}"
                                  f"{transaction.amount:,.2f}",
                'running_balance': float(transaction.running_balance),
            })

        return JsonResponse({
            'transactions': transactions_data,
            'has_next': page_obj.has_next(),
            'total_balance': float(total_balance_across_all_transactions),
            'next_page_number': page_obj.next_page_number()
            if page_obj.has_next() else None,
        })

    context = {
        'transactions': page_obj.object_list,
        'total_balance': total_balance_across_all_transactions,
        'page_obj': page_obj,
        'form': TransactionForm(),
    }
    return render(request, 'transactions/index.html', context)


@require_POST
def add_transaction(request):
    """
    Adds a new transaction sent via AJAX, with additional validations.
    """
    try:
        data = json.loads(request.body)
        form = TransactionForm(data)

        if not form.is_valid():
            errors = {field: form.errors[field] for field in form.errors}
            return JsonResponse({'error': errors, 'success': False}, status=400)

        transaction = form.save()
        last_transaction_for_balance_check = Transaction.objects.exclude(pk=transaction.pk).order_by(
            '-created_at', '-id'
        ).first()
        current_total_balance = last_transaction_for_balance_check.running_balance \
            if last_transaction_for_balance_check else Decimal('0.00')
        
        if transaction.type == 'expense':
            if current_total_balance < abs(transaction.amount):
                transaction.delete()
                return JsonResponse(
                    {'error': {'amount': ['Not enough balance']},
                     'success': False},
                     status =400
                )
            today = timezone.now().date()
            start_of_day = timezone.make_aware(
                datetime.combine(today, time.min),
                timezone.get_default_timezone()
            )
            end_of_day=timezone.make_aware(
                datetime.combine(today, time.max),
                timezone.get_current_timezone()
            )

            expenses_today_count= Transaction.objects.filter(
                type='expense',
                created_at__gte = start_of_day,
                created_at__lte = end_of_day
            ).count()

            if expenses_today_count > TRANSACTION_LIMIT_PER_DAY:
                transaction.delete()
                return JsonResponse({
                    'error': {'type': ['You have already used all transactions limit for today']},
                    "success": False,
                   
                }, status=400)


        final_balance_obj = Transaction.objects.order_by(
            '-created_at', '-id'
        ).first()
        final_total_balance = float(final_balance_obj.running_balance) \
            if final_balance_obj else 0.00

        return JsonResponse({
            'message': 'Transaction successfully executed.',
            'success': True,
            'total_balance': final_total_balance,
            'new_transaction': {
                'code': transaction.code,
                'created_at': transaction.created_at.strftime("%d/%m/%Y %H:%M"),
                'type': transaction.type,
                'type_display': transaction.get_type_display(),
                'amount': float(transaction.amount),
                'amount_display': f"{'+' if transaction.amount > 0 else ''}"
                                  f"{transaction.amount:,.2f}",
                'running_balance': float(transaction.running_balance),
            }
        })
    except json.JSONDecodeError:
        return JsonResponse(
            {'error': 'Incorrect JSON request.', 'success': False},
            status=400
        )
    except Exception as exc: # pylint: disable=broad-except
        LOGGER.exception("Error while adding transaction via AJAX")
        return JsonResponse(
            {'error': f'Unknown error: {str(exc)}', 'success': False},
            status=500
        )


@require_POST
def import_transactions(request):
    """
    Imports transactions from an external MockAPI.
    """
    api_url = API_URL

    if not api_url:
        return JsonResponse(
            {'error': 'API URL cannot be empty', 'success': False},
            status=400
        )

    try:
        response = requests.get(api_url, timeout=10) # Added timeout
        response.raise_for_status()
        api_data = response.json()

        imported_count = 0
        skipped_count = 0

        for item in api_data:
            item_id = item.get('id')
            if not item_id:
                LOGGER.warning("Skipping API transaction without 'id': %s", item)
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
                        created_at = timezone.datetime.fromisoformat(
                            created_at_str.replace('Z', '+00:00')
                        )
                    except ValueError:
                        LOGGER.warning("Error parsing date: %s. Using current time.",
                                       created_at_str)
                        created_at = timezone.now()
                
                transaction_obj= Transaction(
                    code= item_id,
                    type=transaction_type,
                    amount = amount,
                    created_at = created_at,
                )
                transaction_obj.save()
                imported_count +=1

                
            except (ValueError, KeyError) as exc:
                LOGGER.error("Error processing transaction from API: %s. Error: %s",
                             item, exc)
                skipped_count += 1

        last_transaction_after_import = Transaction.objects.order_by(
            '-created_at', '-id'
        ).first()
        total_balance_after_import = float(last_transaction_after_import.running_balance) \
            if last_transaction_after_import else 0.00

        return JsonResponse({
            'message': (f'Imported {imported_count} transactions. '
                        f'Skipped {skipped_count}.'),
            'success': True,
            'total_balance': total_balance_after_import
        })

    except requests.exceptions.RequestException as exc:
        LOGGER.error("Error fetching API: %s", exc)
        return JsonResponse(
            {'error': (f'Error connecting to API: {exc}. '
                       'Check the URL or your internet connection.'),
             'success': False},
            status=500
        )
    except json.JSONDecodeError as exc:
        LOGGER.error("Error parsing JSON response from API: %s", exc)
        return JsonResponse(
            {'error': (f'Error parsing JSON response: {exc}. '
                       'The API might have returned invalid data.'),
             'success': False},
            status=500
        )
    except Exception as exc:
        LOGGER.exception("Unexpected error in import_transactions")
        return JsonResponse(
            {'error': f'An unexpected error occurred: {str(exc)}', 'success': False},
            status=500
        )
