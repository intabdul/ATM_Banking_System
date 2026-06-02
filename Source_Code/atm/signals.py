from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone
from .models import Transaction, ATMMachine, ATMCard, SecurityLog

@receiver(post_save, sender=Transaction)
def update_atm_cash_on_withdrawal(sender, instance, created, **kwargs):
    """Update ATM cash balance when withdrawal is successful"""
    if created and instance.transaction_type == 'WITHDRAWAL' and instance.status == 'SUCCESS':
        if instance.atm and instance.amount:
            try:
                atm = instance.atm
                atm.cash_balance -= instance.amount
                
                # Update ATM status based on cash level
                cash_percentage = (atm.cash_balance / atm.max_capacity) * 100
                
                if cash_percentage < 10:
                    atm.status = 'LOW_CASH'
                elif cash_percentage <= 0:
                    atm.status = 'OUT_OF_SERVICE'
                elif atm.status == 'LOW_CASH' and cash_percentage > 20:
                    atm.status = 'OPERATIONAL'
                
                atm.save()
                
                # Log low cash event
                if cash_percentage < 15:
                    SecurityLog.objects.create(
                        event_type='SYSTEM_ERROR',
                        severity='MEDIUM',
                        description=f'ATM {atm.atm_id} cash low: {cash_percentage:.1f}% remaining',
                        atm=atm
                    )
                    
            except ATMMachine.DoesNotExist:
                pass

@receiver(pre_save, sender=ATMCard)
def check_card_expiry(sender, instance, **kwargs):
    """Check and update card status if expired"""
    if instance.expiry_date and instance.expiry_date < timezone.now().date():
        instance.status = 'EXPIRED'

@receiver(post_save, sender=SecurityLog)
def notify_high_severity_events(sender, instance, created, **kwargs):
    """Log high severity security events"""
    if created and instance.severity in ['HIGH', 'CRITICAL']:
        print(f"⚠️ SECURITY ALERT: {instance.event_type} - {instance.description}")
        
        # Here you would typically:
        # 1. Send email to admin
        # 2. Send SMS alert
        # 3. Log to external monitoring system

@receiver(post_save, sender=ATMMachine)
def log_atm_status_change(sender, instance, created, **kwargs):
    """Log when ATM status changes"""
    if not created:
        try:
            old_instance = ATMMachine.objects.get(pk=instance.pk)
            if old_instance.status != instance.status:
                SecurityLog.objects.create(
                    event_type='SYSTEM_ERROR',
                    severity='MEDIUM',
                    description=f'ATM {instance.atm_id} status changed from {old_instance.status} to {instance.status}',
                    atm=instance
                )
        except ATMMachine.DoesNotExist:
            pass