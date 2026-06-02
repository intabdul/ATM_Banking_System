from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db import transaction as db_transaction
from django.utils import timezone
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_http_methods
from decimal import Decimal
import logging
import uuid
from io import BytesIO

from .models import Account, ATMCard, Transaction, ATMMachine, SecurityLog
from .forms import LoginForm, WithdrawForm, TransferForm, PinChangeForm
from .utils import get_client_ip, log_security_event

logger = logging.getLogger(__name__)

# Default ATM (for demo)
DEFAULT_ATM_ID = 'ATM001'

def get_active_atm():
    """Get active ATM machine"""
    try:
        return ATMMachine.objects.get(atm_id=DEFAULT_ATM_ID)
    except ATMMachine.DoesNotExist:
        # Create default ATM if not exists
        atm = ATMMachine.objects.create(
            atm_id=DEFAULT_ATM_ID,
            location="Main Branch, Karachi",
            cash_balance=Decimal('500000.00'),
            max_capacity=Decimal('1000000.00'),
            status='OPERATIONAL',
            network_status='ONLINE'
        )
        return atm

# Custom decorator for ATM authentication
def atm_login_required(view_func):
    """Custom decorator for ATM authentication"""
    def wrapper(request, *args, **kwargs):
        if 'card_id' not in request.session:
            messages.error(request, 'Please login first')
            return redirect('login')
        
        try:
            card = ATMCard.objects.get(id=request.session['card_id'])
            if card.status != 'ACTIVE':
                messages.error(request, 'Your card is blocked. Contact bank.')
                return redirect('login')
        except ATMCard.DoesNotExist:
            messages.error(request, 'Session expired. Please login again.')
            return redirect('login')
        
        return view_func(request, *args, **kwargs)
    return wrapper

def login_view(request):
    atm = get_active_atm()
    
    if atm.status != 'OPERATIONAL':
        messages.error(request, f'ATM is currently {atm.status}. Please try another ATM.')
        return render(request, 'atm/login.html', {'atm': atm})
    
    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            card_number = form.cleaned_data['card_number']
            pin = form.cleaned_data['pin']
            
            try:
                card = ATMCard.objects.get(card_number=card_number)
                
                # Check card expiry
                if card.expiry_date < timezone.now().date():
                    card.status = 'EXPIRED'
                    card.save()
                    messages.error(request, 'Your card has expired.')
                    return render(request, 'atm/login.html', {'form': form, 'atm': atm})
                
                # Check if card is blocked
                if card.status != 'ACTIVE':
                    messages.error(request, f'Card is {card.status.lower()}. Contact bank.')
                    return render(request, 'atm/login.html', {'form': form, 'atm': atm})
                
                # Check PIN
                if card.check_pin(pin):
                    # Reset failed attempts on successful login
                    card.failed_attempts = 0
                    card.last_used = timezone.now()
                    card.save()
                    
                    # Set session
                    request.session['card_id'] = card.id
                    request.session['account_id'] = card.account.id
                    request.session['account_name'] = card.account.customer.name
                    request.session['card_number'] = card.card_number[-4:]
                    request.session['login_time'] = str(timezone.now())
                    
                    # Log successful login
                    Transaction.objects.create(
                        account=card.account,
                        transaction_type='BALANCE_INQUIRY',
                        amount=Decimal('0.00'),
                        atm=atm,
                        ip_address=get_client_ip(request),
                        description='User login'
                    )
                    
                    messages.success(request, f'Welcome {card.account.customer.name}')
                    return redirect('dashboard')
                
                else:
                    # Increment failed attempts
                    card.failed_attempts += 1
                    if card.failed_attempts >= 3:
                        card.status = 'BLOCKED'
                        card.save()
                        
                        # Log security event
                        log_security_event(
                            event_type='CARD_BLOCKED',
                            severity='HIGH',
                            description=f'Card {card.card_number} blocked after 3 failed attempts',
                            ip_address=get_client_ip(request),
                            atm=atm,
                            account=card.account
                        )
                        
                        messages.error(request, 'Card blocked due to multiple failed attempts. Contact bank.')
                    else:
                        card.save()
                        attempts_left = 3 - card.failed_attempts
                        messages.error(request, f'Invalid PIN. {attempts_left} attempts remaining.')
                    
                    form.add_error('pin', 'Invalid PIN')
                    
            except ATMCard.DoesNotExist:
                form.add_error('card_number', 'Card not found')
                log_security_event(
                    event_type='FAILED_LOGIN',
                    severity='MEDIUM',
                    description=f'Failed login attempt with card: {card_number}',
                    ip_address=get_client_ip(request),
                    atm=atm
                )
    else:
        form = LoginForm()
    
    return render(request, 'atm/login.html', {'form': form, 'atm': atm})

@atm_login_required
def dashboard(request):
    card = ATMCard.objects.get(id=request.session['card_id'])
    account = card.account
    atm = get_active_atm()
    
    # Get recent transactions
    recent_transactions = Transaction.objects.filter(
        account=account
    ).order_by('-timestamp')[:5]
    
    # Check ATM status
    if atm.cash_balance < Decimal('50000.00'):
        messages.warning(request, 'ATM cash is low. Withdrawal amount may be limited.')
    
    context = {
        'account': account,
        'card': card,
        'atm': atm,
        'recent_transactions': recent_transactions,
    }
    return render(request, 'atm/dashboard.html', context)

@atm_login_required
@db_transaction.atomic
def withdraw(request):
    card = ATMCard.objects.get(id=request.session['card_id'])
    account = card.account
    atm = get_active_atm()
    
    # Check ATM status
    if atm.status != 'OPERATIONAL':
        messages.error(request, f'ATM is {atm.status}. Withdrawal not available.')
        return redirect('dashboard')
    
    if request.method == 'POST':
        form = WithdrawForm(request.POST, account=account, atm=atm)
        if form.is_valid():
            amount = form.cleaned_data['amount']
            
            try:
                # Update account balance
                account.current_balance -= amount
                account.save()
                
                # Update ATM cash
                atm.cash_balance -= amount
                atm.save()
                
                # Create transaction record
                transaction = Transaction.objects.create(
                    account=account,
                    transaction_type='WITHDRAWAL',
                    amount=amount,
                    atm=atm,
                    ip_address=get_client_ip(request),
                    description=f'Cash withdrawal from ATM {atm.atm_id}'
                )
                
                # Log security event for large withdrawal
                if amount > Decimal('50000.00'):
                    log_security_event(
                        event_type='SUSPICIOUS_TRANSACTION',
                        severity='MEDIUM',
                        description=f'Large withdrawal: ${amount} from account {account.account_number}',
                        ip_address=get_client_ip(request),
                        atm=atm,
                        account=account
                    )
                
                # Generate receipt data for session
                receipt_data = {
                    'transaction_id': str(transaction.transaction_id),
                    'date': timezone.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'account_number': account.account_number,
                    'transaction_type': 'WITHDRAWAL',
                    'amount': f'${amount:.2f}',
                    'balance': f'${account.current_balance:.2f}',
                    'atm_id': atm.atm_id,
                    'location': atm.location,
                }
                
                request.session['last_receipt'] = receipt_data
                request.session['last_transaction'] = str(transaction.transaction_id)
                
                messages.success(request, f'Successfully withdrawn ${amount:.2f}')
                logger.info(f"Withdrawal: ${amount} from account {account.account_number}")
                
                return redirect('dashboard')
                
            except Exception as e:
                messages.error(request, 'Transaction failed. Please try again.')
                logger.error(f"Withdrawal error: {str(e)}")
                db_transaction.set_rollback(True)
    else:
        form = WithdrawForm(account=account, atm=atm)
    
    context = {
        'form': form,
        'account': account,
        'atm': atm,
    }
    return render(request, 'atm/withdraw.html', context)

@atm_login_required
@db_transaction.atomic
def transfer(request):
    card = ATMCard.objects.get(id=request.session['card_id'])
    sender = card.account
    
    if request.method == 'POST':
        form = TransferForm(request.POST, account=sender)
        if form.is_valid():
            receiver = form.cleaned_data['receiver_account']
            amount = form.cleaned_data['amount']
            description = form.cleaned_data.get('description', '')
            
            try:
                # Update sender balance
                sender.current_balance -= amount
                sender.save()
                
                # Update receiver balance
                receiver.current_balance += amount
                receiver.save()
                
                atm = get_active_atm()
                
                # Create transaction for sender
                transaction = Transaction.objects.create(
                    account=sender,
                    transaction_type='TRANSFER',
                    amount=amount,
                    receiver_account=receiver,
                    atm=atm,
                    ip_address=get_client_ip(request),
                    description=f'Transfer to {receiver.account_number}' + (f': {description}' if description else '')
                )
                
                # Create transaction for receiver
                Transaction.objects.create(
                    account=receiver,
                    transaction_type='TRANSFER',
                    amount=amount,
                    receiver_account=sender,
                    atm=atm,
                    ip_address=get_client_ip(request),
                    description=f'Transfer from {sender.account_number}' + (f': {description}' if description else '')
                )
                
                # Generate receipt data
                receipt_data = {
                    'transaction_id': str(transaction.transaction_id),
                    'date': timezone.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'from_account': sender.account_number,
                    'to_account': receiver.account_number,
                    'transaction_type': 'TRANSFER',
                    'amount': f'${amount:.2f}',
                    'balance': f'${sender.current_balance:.2f}',
                    'description': description,
                }
                
                request.session['last_receipt'] = receipt_data
                request.session['last_transaction'] = str(transaction.transaction_id)
                
                messages.success(request, f'Successfully transferred ${amount:.2f} to {receiver.account_number}')
                logger.info(f"Transfer: ${amount} from {sender.account_number} to {receiver.account_number}")
                
                return redirect('dashboard')
                
            except Exception as e:
                messages.error(request, 'Transfer failed. Please try again.')
                logger.error(f"Transfer error: {str(e)}")
                db_transaction.set_rollback(True)
    else:
        form = TransferForm(account=sender)
    
    context = {
        'form': form,
        'account': sender,
    }
    return render(request, 'atm/transfer.html', context)

@atm_login_required
def balance(request):
    card = ATMCard.objects.get(id=request.session['card_id'])
    account = card.account
    atm = get_active_atm()
    
    # Log balance inquiry
    Transaction.objects.create(
        account=account,
        transaction_type='BALANCE_INQUIRY',
        amount=Decimal('0.00'),
        atm=atm,
        ip_address=get_client_ip(request),
        description='Balance inquiry'
    )
    
    context = {
        'account': account,
        'atm': atm,
    }
    return render(request, 'atm/balance.html', context)

@atm_login_required
def mini_statement(request):
    card = ATMCard.objects.get(id=request.session['card_id'])
    account = card.account
    atm = get_active_atm()
    
    # Get last 10 transactions
    transactions = Transaction.objects.filter(
        account=account
    ).order_by('-timestamp')[:10]
    
    # Log statement request
    Transaction.objects.create(
        account=account,
        transaction_type='MINI_STATEMENT',
        amount=Decimal('0.00'),
        atm=atm,
        ip_address=get_client_ip(request),
        description='Mini statement requested'
    )
    
    context = {
        'account': account,
        'transactions': transactions,
    }
    return render(request, 'atm/mini_statement.html', context)

@atm_login_required
@db_transaction.atomic
def pin_change(request):
    card = ATMCard.objects.get(id=request.session['card_id'])
    
    if request.method == 'POST':
        form = PinChangeForm(request.POST, card=card)
        if form.is_valid():
            new_pin = form.cleaned_data['new_pin']
            
            # Change PIN
            card.set_pin(new_pin)
            card.save()
            
            # Log transaction
            Transaction.objects.create(
                account=card.account,
                transaction_type='PIN_CHANGE',
                amount=Decimal('0.00'),
                atm=get_active_atm(),
                ip_address=get_client_ip(request),
                description='PIN changed successfully'
            )
            
            # Log security event
            log_security_event(
                event_type='PIN_CHANGE',
                severity='MEDIUM',
                description=f'PIN changed for card {card.card_number}',
                ip_address=get_client_ip(request),
                atm=get_active_atm(),
                account=card.account
            )
            
            messages.success(request, 'PIN changed successfully')
            return redirect('dashboard')
    else:
        form = PinChangeForm(card=card)
    
    context = {
        'form': form,
        'card': card,
    }
    return render(request, 'atm/pin_change.html', context)

@atm_login_required
def print_receipt(request):
    receipt_data = request.session.get('last_receipt')
    
    if not receipt_data:
        messages.error(request, 'No recent transaction to print receipt for')
        return redirect('dashboard')
    
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.pdfgen import canvas
        
        # Generate PDF receipt
        buffer = BytesIO()
        p = canvas.Canvas(buffer, pagesize=letter)
        
        # Add content to PDF
        p.setFont("Helvetica-Bold", 16)
        p.drawString(100, 750, "ATM TRANSACTION RECEIPT")
        p.setFont("Helvetica", 10)
        p.drawString(100, 730, f"Transaction ID: {receipt_data.get('transaction_id', 'N/A')}")
        p.drawString(100, 710, f"Date: {receipt_data.get('date', 'N/A')}")
        p.drawString(100, 690, f"Type: {receipt_data.get('transaction_type', 'N/A')}")
        
        if 'from_account' in receipt_data:
            p.drawString(100, 670, f"From: {receipt_data['from_account']}")
            p.drawString(100, 650, f"To: {receipt_data['to_account']}")
        else:
            p.drawString(100, 670, f"Account: {receipt_data.get('account_number', 'N/A')}")
        
        p.drawString(100, 630, f"Amount: {receipt_data.get('amount', 'N/A')}")
        p.drawString(100, 610, f"Balance: {receipt_data.get('balance', 'N/A')}")
        
        if receipt_data.get('description'):
            p.drawString(100, 590, f"Description: {receipt_data['description']}")
        
        p.drawString(100, 550, "Thank you for banking with us!")
        p.drawString(100, 530, "Keep this receipt for your records.")
        
        p.showPage()
        p.save()
        
        buffer.seek(0)
        
        # Mark receipt as printed
        transaction_id = request.session.get('last_transaction')
        if transaction_id:
            try:
                transaction = Transaction.objects.get(transaction_id=transaction_id)
                transaction.receipt_printed = True
                transaction.save()
            except Transaction.DoesNotExist:
                pass
        
        # Return PDF response
        response = HttpResponse(buffer, content_type='application/pdf')
        response['Content-Disposition'] = 'attachment; filename="atm_receipt.pdf"'
        return response
        
    except ImportError:
        messages.error(request, 'Receipt printing not available. Install reportlab package.')
        return redirect('dashboard')

@atm_login_required
def logout_view(request):
    card_id = request.session.get('card_id')
    
    if card_id:
        try:
            card = ATMCard.objects.get(id=card_id)
            logger.info(f"User logged out: Card {card.card_number}")
        except ATMCard.DoesNotExist:
            pass
    
    request.session.flush()
    messages.success(request, 'Successfully logged out')
    return redirect('login')

def atm_status(request):
    """API endpoint to check ATM status"""
    atm = get_active_atm()
    return JsonResponse({
        'atm_id': atm.atm_id,
        'status': atm.status,
        'cash_balance': float(atm.cash_balance),
        'network_status': atm.network_status,
        'location': atm.location,
        'last_maintenance': atm.last_maintenance,
    })

# Helper function
def get_client_ip(request):
    """Get client IP address"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip