from django.utils import timezone
from decimal import Decimal
import logging
from .models import SecurityLog, Transaction, Account

logger = logging.getLogger(__name__)

def get_client_ip(request):
    """Get client IP address"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip

def check_daily_limits(account, transaction_type, amount):
    """Check if transaction exceeds daily limits"""
    today = timezone.now().date()
    
    today_transactions = Transaction.objects.filter(
        account=account,
        transaction_type=transaction_type,
        status='SUCCESS',
        timestamp__date=today
    )
    
    total_today = today_transactions.aggregate(total=models.Sum('amount'))['total'] or Decimal('0.00')
    
    if transaction_type == 'WITHDRAWAL':
        limit = account.daily_withdrawal_limit
    elif transaction_type == 'TRANSFER':
        limit = account.daily_transfer_limit
    else:
        return True  # No limit for other transactions
    
    return (total_today + amount) <= limit

def log_security_event(event_type, severity, description, ip_address=None, atm=None, account=None):
    """Log security events"""
    SecurityLog.objects.create(
        event_type=event_type,
        severity=severity,
        description=description,
        ip_address=ip_address,
        atm=atm,
        account=account
    )
    logger.warning(f"Security Event: {event_type} - {description}")

def validate_card_status(card):
    """Validate card status and return error message if invalid"""
    if card.status == 'BLOCKED':
        return 'Card is blocked. Contact bank.'
    elif card.status == 'INACTIVE':
        return 'Card is inactive.'
    elif card.status == 'EXPIRED':
        return 'Card has expired.'
    elif card.status == 'LOST':
        return 'Card reported as lost/stolen.'
    return None

def generate_receipt_pdf(transaction_data):
    """Generate PDF receipt"""
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas
    from io import BytesIO
    
    buffer = BytesIO()
    p = canvas.Canvas(buffer, pagesize=letter)
    
    # Add receipt content
    p.drawString(100, 750, "ATM Transaction Receipt")
    p.drawString(100, 730, f"Transaction ID: {transaction_data.get('transaction_id')}")
    p.drawString(100, 710, f"Date: {transaction_data.get('date')}")
    p.drawString(100, 690, f"Type: {transaction_data.get('transaction_type')}")
    p.drawString(100, 670, f"Amount: ${transaction_data.get('amount'):.2f}")
    p.drawString(100, 650, f"Balance: ${transaction_data.get('balance'):.2f}")
    
    p.save()
    buffer.seek(0)
    return buffer

def calculate_cash_dispensable(atm, amount):
    """Calculate if ATM can dispense requested amount"""
    denominations = [5000, 1000, 500, 100]
    
    remaining = float(amount)
    dispensation = {}
    
    for denom in denominations:
        if remaining >= denom:
            count = int(remaining // denom)
            # Limit to available notes (simplified)
            max_notes = 40  # Assuming ATM can dispense max 40 notes per denomination
            count = min(count, max_notes)
            dispensation[denom] = count
            remaining -= count * denom
    
    return remaining == 0, dispensation