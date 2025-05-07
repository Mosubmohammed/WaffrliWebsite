from django.urls import path
from . import views
from .views import *

urlpatterns = [
    path('register/', register, name='register'),
    path('login/', login_view, name='login'),
    path('logout/', logout_view, name='logout'),
    path('forgot-password/', forgot_password, name='forgot_password'),
    path('check-email-verification/', check_email_verification, name='check_email_verification'),
    path('resend-verification/', resend_verification_email, name='resend_verification'),
    path('verify/', verify_email_callback, name='verify_email_callback'),
    path('complete-password-reset/', complete_password_reset, name='complete_password_reset'),
    path('complete-email-verification/', complete_email_verification, name='complete_email_verification'),
    path('reset-password/', reset_password_view, name='reset_password'),
    path('close-account/', close_account, name='close_account'),
]