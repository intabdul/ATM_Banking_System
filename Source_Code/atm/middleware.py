from django.utils import timezone
from django.shortcuts import redirect
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

class ATMSessionMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Skip for login and static files
        if request.path in ['/', '/login', '/static/', '/api/'] or request.path.startswith('/admin'):
            return self.get_response(request)
        
        # Check session timeout
        if 'card_id' in request.session:
            login_time_str = request.session.get('login_time')
            if login_time_str:
                try:
                    login_time = timezone.datetime.fromisoformat(login_time_str)
                    session_timeout = settings.ATM_SETTINGS['SESSION_TIMEOUT_MINUTES']
                    
                    if (timezone.now() - login_time).seconds > session_timeout * 60:
                        # Session expired
                        request.session.flush()
                        logger.info("Session expired due to timeout")
                        return redirect('login')
                    
                    # Update last activity
                    request.session['login_time'] = str(timezone.now())
                    
                except (ValueError, TypeError):
                    pass
        
        response = self.get_response(request)
        return response

class TransactionLimitMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        response = self.get_response(request)
        
        # Check for suspicious activity
        if 'card_id' in request.session and request.method == 'POST':
            # Log transaction attempts (simplified)
            if any(x in request.path for x in ['withdraw', 'transfer', 'pin-change']):
                logger.info(f"Transaction attempt: {request.path} by session {request.session.get('card_id')}")
        
        return response