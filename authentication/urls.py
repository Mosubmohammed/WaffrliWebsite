
from django.urls import path
from . import views
from .views import *
urlpatterns = [
    path('register/', register, name='register'),
    path('login/', login_view, name='login'),
    path('logout/',logout_user, name='logout'),
    path('forgot-password/', forgot_password, name='forgot_password'),
    path('password_reset_callback/', password_reset_callback, name='password_reset_callback'),
    path('check-email-verification/', check_email_verification, name='check_email_verification'),
    path('resend-verification/', resend_verification_email, name='resend_verification'),
    path('verify/', verify_email_callback, name='verify_email_callback'),
]