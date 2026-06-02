from django.core.management.base import BaseCommand
from atm.models import Customer, Account, ATMCard
from decimal import Decimal
from datetime import date, timedelta

class Command(BaseCommand):
    help = 'Create sample bank accounts for testing'
    
    def handle(self, *args, **kwargs):
        # Create customer
        customer, created = Customer.objects.get_or_create(
            cnic='12345-6789012-3',
            defaults={
                'name': 'Shahzad Khan',
                'phone': '0310-6654623',
                'email': 'shezook@gmail.com',
                'address': '123 Main Street, Sargodha',
            }
        )
        
        if created:
            self.stdout.write(self.style.SUCCESS(f'Created customer: {customer.name}'))
        
        # Create account
        account, acc_created = Account.objects.get_or_create(
            account_number='001234567890',
            defaults={
                'customer': customer,
                'account_type': 'SAVINGS',
                'current_balance': Decimal('100000.00'),
                'daily_withdrawal_limit': Decimal('50000.00'),
                'daily_transfer_limit': Decimal('100000.00'),
            }
        )
        
        if acc_created:
            self.stdout.write(self.style.SUCCESS(f'Created account: {account.account_number}'))
        
        # Create ATM card
        card, card_created = ATMCard.objects.get_or_create(
            card_number='1234567890123456',
            defaults={
                'account': account,
                'expiry_date': date.today() + timedelta(days=365*3),  # 3 years
            }
        )
        
        if card_created:
            card.set_pin('1234')
            card.save()
            self.stdout.write(self.style.SUCCESS(f'Created ATM card: {card.card_number}'))
        
        # Create ATM machine
        from atm.models import ATMMachine
        atm, atm_created = ATMMachine.objects.get_or_create(
            atm_id='ATM001',
            defaults={
                'location': 'Main Branch, Karachi',
                'cash_balance': Decimal('500000.00'),
                'max_capacity': Decimal('1000000.00'),
                'status': 'OPERATIONAL',
                'network_status': 'ONLINE',
            }
        )
        
        if atm_created:
            self.stdout.write(self.style.SUCCESS(f'Created ATM: {atm.atm_id}'))
        
        self.stdout.write(self.style.SUCCESS('Setup completed successfully!'))
        self.stdout.write('Login with:')
        self.stdout.write(f'  Card Number: 1234567890123456')
        self.stdout.write(f'  PIN: 1234')