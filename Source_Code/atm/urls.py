from django.urls import path
from . import views

urlpatterns = [
    # Authentication
    path('', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    
    # Dashboard
    path('dashboard/', views.dashboard, name='dashboard'),
    
    # Transactions
    path('withdraw/', views.withdraw, name='withdraw'),
    path('transfer/', views.transfer, name='transfer'),
    path('balance/', views.balance, name='balance'),
    
    # Services
    path('mini-statement/', views.mini_statement, name='mini_statement'),
    path('pin-change/', views.pin_change, name='pin_change'),
    path('print-receipt/', views.print_receipt, name='print_receipt'),
    
    # API
    path('api/atm-status/', views.atm_status, name='atm_status'),
]