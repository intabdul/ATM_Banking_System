from django.db import models
from django.contrib.auth.hashers import make_password, check_password
from django.core.validators import MinValueValidator
from decimal import Decimal
import uuid

class Customer(models.Model):
    customer_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    cnic = models.CharField(max_length=15, unique=True)
    name = models.CharField(max_length=200)
    phone = models.CharField(max_length=15)
    email = models.EmailField(blank=True)
    address = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.name} ({self.cnic})"
    
    class Meta:
        ordering = ['name']

class Account(models.Model):
    ACCOUNT_TYPES = [
        ('SAVINGS', 'Savings Account'),
        ('CURRENT', 'Current Account'),
        ('SALARY', 'Salary Account'),
    ]
    
    STATUS_CHOICES = [
        ('ACTIVE', 'Active'),
        ('INACTIVE', 'Inactive'),
        ('BLOCKED', 'Blocked'),
        ('CLOSED', 'Closed'),
    ]
    
    account_number = models.CharField(max_length=20, unique=True)
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='accounts')
    account_type = models.CharField(max_length=20, choices=ACCOUNT_TYPES)
    current_balance = models.DecimalField(
        max_digits=15, 
        decimal_places=2, 
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    daily_withdrawal_limit = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('50000.00'))
    daily_transfer_limit = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('100000.00'))
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='ACTIVE')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.account_number} - {self.customer.name}"
    
    class Meta:
        ordering = ['-created_at']

class ATMCard(models.Model):
    CARD_STATUS = [
        ('ACTIVE', 'Active'),
        ('INACTIVE', 'Inactive'),
        ('BLOCKED', 'Blocked'),
        ('EXPIRED', 'Expired'),
        ('LOST', 'Lost/Stolen'),
    ]
    
    card_number = models.CharField(max_length=16, unique=True)
    account = models.ForeignKey(Account, on_delete=models.CASCADE, related_name='cards')
    pin_hash = models.CharField(max_length=128)
    status = models.CharField(max_length=10, choices=CARD_STATUS, default='ACTIVE')
    expiry_date = models.DateField()
    issue_date = models.DateField(auto_now_add=True)
    last_used = models.DateTimeField(null=True, blank=True)
    failed_attempts = models.IntegerField(default=0)
    
    def set_pin(self, raw_pin):
        """Securely hash PIN"""
        self.pin_hash = make_password(str(raw_pin))
    
    def check_pin(self, raw_pin):
        """Verify PIN"""
        return check_password(str(raw_pin), self.pin_hash)
    
    def __str__(self):
        return f"Card {self.card_number[-4:]} - {self.account.account_number}"
    
    class Meta:
        ordering = ['-issue_date']

class Transaction(models.Model):
    TRANSACTION_TYPES = [
        ('WITHDRAWAL', 'Cash Withdrawal'),
        ('DEPOSIT', 'Cash Deposit'),
        ('TRANSFER', 'Fund Transfer'),
        ('BALANCE_INQUIRY', 'Balance Inquiry'),
        ('MINI_STATEMENT', 'Mini Statement'),
        ('PIN_CHANGE', 'PIN Change'),
        ('BILL_PAYMENT', 'Bill Payment'),
    ]
    
    STATUS_CHOICES = [
        ('SUCCESS', 'Success'),
        ('FAILED', 'Failed'),
        ('PENDING', 'Pending'),
        ('CANCELLED', 'Cancelled'),
    ]
    
    transaction_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    account = models.ForeignKey(Account, on_delete=models.CASCADE, related_name='transactions')
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPES)
    amount = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    receiver_account = models.ForeignKey(
        Account, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='received_transactions'
    )
    fee = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    description = models.TextField(blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='SUCCESS')
    atm = models.ForeignKey('ATMMachine', on_delete=models.SET_NULL, null=True, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    receipt_printed = models.BooleanField(default=False)
    
    def __str__(self):
        return f"{self.transaction_id} - {self.transaction_type}"
    
    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['account', 'timestamp']),
            models.Index(fields=['transaction_type', 'status']),
        ]

class ATMMachine(models.Model):
    STATUS_CHOICES = [
        ('OPERATIONAL', 'Operational'),
        ('MAINTENANCE', 'Under Maintenance'),
        ('OUT_OF_SERVICE', 'Out of Service'),
        ('LOW_CASH', 'Low Cash'),
        ('OFFLINE', 'Offline'),
    ]
    
    NETWORK_STATUS = [
        ('ONLINE', 'Online'),
        ('OFFLINE', 'Offline'),
        ('DEGRADED', 'Degraded Performance'),
    ]
    
    atm_id = models.CharField(max_length=20, unique=True)
    location = models.CharField(max_length=200)
    cash_balance = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    max_capacity = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('1000000.00'))
    network_status = models.CharField(max_length=10, choices=NETWORK_STATUS, default='ONLINE')
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='OPERATIONAL')
    last_maintenance = models.DateTimeField(null=True, blank=True)
    next_maintenance = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"ATM {self.atm_id} - {self.location}"
    
    def cash_percentage(self):
        return (self.cash_balance / self.max_capacity) * 100
    
    class Meta:
        ordering = ['atm_id']

class SecurityLog(models.Model):
    EVENT_TYPES = [
        ('FAILED_LOGIN', 'Failed Login Attempt'),
        ('PIN_CHANGE', 'PIN Change Attempt'),
        ('SUSPICIOUS_TRANSACTION', 'Suspicious Transaction'),
        ('CARD_BLOCKED', 'Card Blocked'),
        ('ATM_TAMPERING', 'ATM Tampering Detected'),
        ('UNAUTHORIZED_ACCESS', 'Unauthorized Access Attempt'),
        ('SYSTEM_ERROR', 'System Error'),
    ]
    
    SEVERITY_CHOICES = [
        ('LOW', 'Low'),
        ('MEDIUM', 'Medium'),
        ('HIGH', 'High'),
        ('CRITICAL', 'Critical'),
    ]
    
    log_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    event_type = models.CharField(max_length=30, choices=EVENT_TYPES)
    severity = models.CharField(max_length=10, choices=SEVERITY_CHOICES, default='MEDIUM')
    description = models.TextField()
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    atm = models.ForeignKey(ATMMachine, on_delete=models.SET_NULL, null=True, blank=True)
    account = models.ForeignKey(Account, on_delete=models.SET_NULL, null=True, blank=True)
    resolved = models.BooleanField(default=False)
    resolution_notes = models.TextField(blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.event_type} - {self.timestamp}"
    
    class Meta:
        ordering = ['-timestamp']