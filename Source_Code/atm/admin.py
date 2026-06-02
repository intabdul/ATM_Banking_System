from django.contrib import admin
from django import forms
from django.contrib.auth.hashers import make_password
from .models import *

# Custom form for ATMCard
class ATMCardAdminForm(forms.ModelForm):
    pin_input = forms.CharField(
        max_length=4,
        min_length=4,
        label="PIN",
        help_text="Enter 4-digit PIN for login",
        widget=forms.PasswordInput(render_value=True)
    )
    
    class Meta:
        model = ATMCard
        fields = '__all__'
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            # Don't show PIN for existing cards
            self.fields['pin_input'].required = False
            self.fields['pin_input'].help_text = "Leave blank to keep current PIN"
    
    def save(self, commit=True):
        card = super().save(commit=False)
        
        # Hash the PIN if provided
        pin_input = self.cleaned_data.get('pin_input')
        if pin_input:
            card.pin_hash = make_password(pin_input)
        
        if commit:
            card.save()
        return card

@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ['cnic', 'name', 'phone', 'email']
    search_fields = ['cnic', 'name', 'phone']
    list_filter = ['created_at']

@admin.register(Account)
class AccountAdmin(admin.ModelAdmin):
    list_display = ['account_number', 'customer', 'account_type', 'current_balance', 'status']
    list_filter = ['account_type', 'status', 'created_at']
    search_fields = ['account_number', 'customer__name']

@admin.register(ATMCard)
class ATMCardAdmin(admin.ModelAdmin):
    form = ATMCardAdminForm  # ✅ Use custom form
    list_display = ['card_number', 'account', 'status', 'expiry_date']
    list_filter = ['status', 'expiry_date']
    search_fields = ['card_number', 'account__account_number']
    
    # Fields to display in admin form
    fieldsets = (
        ('Card Information', {
            'fields': ('card_number', 'account', 'status', 'expiry_date')
        }),
        ('PIN Configuration', {
            'fields': ('pin_input',),
            'description': 'Enter 4-digit PIN for this card'
        }),
    )

@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ['transaction_id', 'account', 'transaction_type', 'amount', 'status', 'timestamp']
    list_filter = ['transaction_type', 'status', 'timestamp']
    search_fields = ['transaction_id', 'account__account_number']
    readonly_fields = ['transaction_id', 'timestamp']
    date_hierarchy = 'timestamp'

@admin.register(ATMMachine)
class ATMMachineAdmin(admin.ModelAdmin):
    list_display = ['atm_id', 'location', 'cash_balance', 'network_status', 'status']
    list_filter = ['status', 'network_status']
    readonly_fields = ['last_maintenance']

@admin.register(SecurityLog)
class SecurityLogAdmin(admin.ModelAdmin):
    list_display = ['log_id', 'event_type', 'severity', 'timestamp', 'resolved']
    list_filter = ['event_type', 'severity', 'resolved']
    search_fields = ['description']
    readonly_fields = ['log_id', 'timestamp']