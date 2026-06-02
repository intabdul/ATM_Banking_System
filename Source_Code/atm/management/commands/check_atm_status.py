from django.core.management.base import BaseCommand
from atm.models import ATMMachine

class Command(BaseCommand):
    help = 'Check ATM status and cash levels'
    
    def handle(self, *args, **kwargs):
        atms = ATMMachine.objects.all()
        
        for atm in atms:
            status = '✅ OK'
            if atm.status != 'OPERATIONAL':
                status = '⚠️ ' + atm.status
            elif atm.cash_balance < 100000.00:
                status = '⚠️ LOW CASH'
            
            self.stdout.write(f'{atm.atm_id}: {status}')
            self.stdout.write(f'  Location: {atm.location}')
            self.stdout.write(f'  Cash: ${atm.cash_balance:.2f} / ${atm.max_capacity:.2f}')
            self.stdout.write(f'  Network: {atm.network_status}')
            self.stdout.write('')