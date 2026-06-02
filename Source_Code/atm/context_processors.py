from django.conf import settings
from .models import ATMMachine

def atm_settings(request):
    """Add ATM settings to template context"""
    return {
        'ATM_SETTINGS': settings.ATM_SETTINGS,
    }

def atm_status_context(request):
    """Add current ATM status to all templates"""
    try:
        atm = ATMMachine.objects.filter(status='OPERATIONAL').first()
        if not atm:
            atm = ATMMachine.objects.first()
        
        if atm:
            return {
                'current_atm': atm,
                'atm_cash_percentage': (atm.cash_balance / atm.max_capacity) * 100 if atm.max_capacity > 0 else 0,
            }
    except (ATMMachine.DoesNotExist, AttributeError):
        pass
    
    return {
        'current_atm': None,
        'atm_cash_percentage': 0,
    }

def user_session_info(request):
    """Add user session information to context"""
    context = {}
    
    if 'card_id' in request.session:
        context['user_logged_in'] = True
        context['session_start'] = request.session.get('login_time', '')
    else:
        context['user_logged_in'] = False
    
    return context