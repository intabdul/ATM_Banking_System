from django import forms
from django.utils import timezone  # ✅ IMPORTANT
from decimal import Decimal
from .models import Account, ATMCard

class LoginForm(forms.Form):
    card_number = forms.CharField(
        max_length=16,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter Card Number',
            'autocomplete': 'off'
        })
    )
    pin = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter PIN',
            'maxlength': '4'
        }),
        min_length=4,
        max_length=4
    )

class WithdrawForm(forms.Form):
    amount = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        min_value=Decimal('100.00'),
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'step': '100',
            'placeholder': 'Enter amount in multiples of 100'
        })
    )
    
    def __init__(self, *args, **kwargs):
        self.account = kwargs.pop('account')
        self.atm = kwargs.pop('atm', None)
        super().__init__(*args, **kwargs)
    
    def clean_amount(self):
        amount = self.cleaned_data['amount']
        
        # Check account balance
        if amount > self.account.current_balance:
            raise forms.ValidationError('Insufficient balance in account')
        
        # Check ATM cash availability (if atm is provided)
        if self.atm and amount > self.atm.cash_balance:
            raise forms.ValidationError('ATM has insufficient cash')
        
        # Check daily withdrawal limit
        from .models import Transaction  # ✅ Import inside function if needed
        from django.db.models import Sum
        
        today = timezone.now().date()  # ✅ NOW timezone is defined
        daily_withdrawn = self.account.transactions.filter(
            transaction_type='WITHDRAWAL',
            status='SUCCESS',
            timestamp__date=today
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        
        if daily_withdrawn + amount > self.account.daily_withdrawal_limit:
            remaining = self.account.daily_withdrawal_limit - daily_withdrawn
            raise forms.ValidationError(f'Daily withdrawal limit exceeded. Remaining: ${remaining}')
        
        # Check if amount is multiple of 100
        if amount % 100 != 0:
            raise forms.ValidationError('Amount must be in multiples of 100')
        
        return amount

class TransferForm(forms.Form):
    receiver_account = forms.CharField(
        max_length=20,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter Receiver Account Number'
        })
    )
    amount = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        min_value=Decimal('100.00'),
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'step': '0.01',
            'placeholder': 'Enter amount'
        })
    )
    description = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 2,
            'placeholder': 'Optional description'
        })
    )
    
    def __init__(self, *args, **kwargs):
        self.sender = kwargs.pop('account')
        super().__init__(*args, **kwargs)
    
    def clean_receiver_account(self):
        acc_no = self.cleaned_data['receiver_account']
        
        try:
            receiver = Account.objects.get(
                account_number=acc_no, 
                status='ACTIVE'
            )
            
            if receiver.id == self.sender.id:
                raise forms.ValidationError('Cannot transfer to your own account')
            
            return receiver
            
        except Account.DoesNotExist:
            raise forms.ValidationError('Receiver account not found or inactive')
    
    def clean_amount(self):
        amount = self.cleaned_data['amount']
        
        if amount > self.sender.current_balance:
            raise forms.ValidationError('Insufficient balance')
        
        # Check daily transfer limit
        from .models import Transaction  # ✅ Import inside function
        from django.db.models import Sum
        
        today = timezone.now().date()  # ✅ NOW timezone is defined
        daily_transferred = self.sender.transactions.filter(
            transaction_type='TRANSFER',
            status='SUCCESS',
            timestamp__date=today
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        
        if daily_transferred + amount > self.sender.daily_transfer_limit:
            remaining = self.sender.daily_transfer_limit - daily_transferred
            raise forms.ValidationError(f'Daily transfer limit exceeded. Remaining: ${remaining}')
        
        return amount

class PinChangeForm(forms.Form):
    current_pin = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Current PIN',
            'maxlength': '4'
        }),
        min_length=4,
        max_length=4
    )
    new_pin = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'New PIN (4 digits)',
            'maxlength': '4'
        }),
        min_length=4,
        max_length=4
    )
    confirm_pin = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Confirm New PIN',
            'maxlength': '4'
        }),
        min_length=4,
        max_length=4
    )
    
    def __init__(self, *args, **kwargs):
        self.card = kwargs.pop('card')
        super().__init__(*args, **kwargs)
    
    def clean(self):
        cleaned_data = super().clean()
        new_pin = cleaned_data.get('new_pin')
        confirm_pin = cleaned_data.get('confirm_pin')
        
        if new_pin and confirm_pin and new_pin != confirm_pin:
            self.add_error('confirm_pin', 'PINs do not match')
        
        # Check if new PIN is same as current
        if new_pin and self.card.check_pin(new_pin):
            self.add_error('new_pin', 'New PIN cannot be same as current PIN')
        
        return cleaned_data
    
    def clean_current_pin(self):
        current_pin = self.cleaned_data['current_pin']
        if not self.card.check_pin(current_pin):
            raise forms.ValidationError('Current PIN is incorrect')
        return current_pin