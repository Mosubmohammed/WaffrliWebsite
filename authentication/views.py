
from django.shortcuts import render, redirect
from django.contrib.auth.models import User
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from .models import SupabaseUser 
from waffrli.models import Customer
from django.conf import settings

def register(request):
    if request.method == 'POST':
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        email = request.POST.get('email')
        phone = request.POST.get('phone')
        password = request.POST.get('password')
        confirm_password = request.POST.get('confirm_password')
        gender = request.POST.get('gender')
        image = request.FILES.get('image')

        latitude = request.POST.get('latitude')
        longitude = request.POST.get('longitude')
        formatted_address = request.POST.get('formatted_address')
        

        if password != confirm_password:
            messages.error(request, "Passwords don't match")
            return render(request, 'register.html')
        
        if User.objects.filter(email=email).exists():
            messages.error(request, "Email already exists")
            return render(request, 'register.html')
        
        try:
            supabase_response = settings.SUPABASE.auth.sign_up({
                "email": email,
                "password": password,
                "options": {
                    "data": {
                        "first_name": first_name,
                        "last_name": last_name,
                        "phone": phone,
                        "gender": gender
                    },
                    "email_redirect_to": "http://127.0.0.1:8000/auth/verify/",
                }
            })
            
            request.session['verification_email'] = email
            
            supabase_user_id = supabase_response.user.id
            
            username = first_name
            if User.objects.filter(username=username).exists():
                counter = 1
                base_username = username
                while User.objects.filter(username=username).exists():
                    username = f"{base_username}{counter}"
                    counter += 1
            
            django_user = User.objects.create_user(
                username=username,
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name,
                is_active=True
            )
            

            SupabaseUser.objects.create(
                user=django_user,
                supabase_id=supabase_user_id,
                email_verified=False
            )
            

            customer = Customer.objects.create(
                user=django_user,
                first_name=first_name,
                last_name=last_name,
                phone=phone,
                email=email,
                password=password,
                gender=gender,
                latitude=float(latitude) if latitude else None,
                longitude=float(longitude) if longitude else None,
                formatted_address=formatted_address,
                image=image if image else None
            )
            
            messages.success(request, "Registration successful! Please check your email to verify your account before logging in.")

            return redirect('login')
            
        except Exception as e:
            messages.error(request, f"Registration failed: {str(e)}")
            return render(request, 'register.html')
    
    return render(request, 'register.html')




# authentication/views.py
def login_view(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')
        
        try:

            try:
                django_user = User.objects.get(email=email)
            except User.DoesNotExist:
                messages.error(request, "Invalid email or password.")
                return render(request, 'login.html')
            

            supabase_response = settings.SUPABASE.auth.sign_in_with_password({
                "email": email,
                "password": password
            })
            

            if not supabase_response.user.email_confirmed_at:
                messages.error(request, "Please verify your email address before logging in.")

                context = {
                    'email': email,
                    'show_resend': True
                }
                return render(request, 'login.html', context)
            
            user = authenticate(request, username=django_user.username, password=password)
            if user is not None:
                login(request, user)
                
                request.session['supabase_access_token'] = supabase_response.session.access_token
                request.session['supabase_user_id'] = supabase_response.user.id
                
                messages.success(request, "Login successful!")
                return redirect('home')
            else:
                messages.error(request, "Invalid email or password.")
                return render(request, 'login.html')
                
        except Exception as e:
            messages.error(request, f"Login error: {str(e)}")
            return render(request, 'login.html')
    
    return render(request, 'login.html')



def logout_user(request):
    try:
        settings.SUPABASE.auth.sign_out()
    except:
        pass
    
    # Clear Django session
    if 'supabase_access_token' in request.session:
        del request.session['supabase_access_token']
    if 'supabase_user_id' in request.session:
        del request.session['supabase_user_id']
    
    logout(request)
    messages.success(request, 'Logged out successfully!')
    return redirect('home')



def forgot_password(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        
        if not email:
            messages.error(request, "Email is required.")
            return render(request, 'forgot_password.html')
        
        try:
            # Updated redirect URL to match your URL configuration
            settings.SUPABASE.auth.reset_password_for_email(
                email,
                {
                    "redirect_to": "http://127.0.0.1:8000/auth/password_reset_callback/", # Notice: no auth/ prefix
                }
            )
            
            messages.success(request, "If your email exists in our system, you will receive a password reset link.")
            return redirect('login')
            
        except Exception as e:
            messages.error(request, f"Error: {str(e)}")
            return render(request, 'forgot_password.html')
    
    return render(request, 'forgot_password.html')



def password_reset_callback(request):
    print("RESET CALLBACK ACCESSED")  # Debug
    print("All GET params:", dict(request.GET))  # Debug
    
    # Get common verification parameters
    token_hash = request.GET.get('token_hash')
    code = request.GET.get('code')
    type_param = request.GET.get('type')
    
    if type_param == 'recovery':
        try:
            # Handle password reset verification
            if token_hash:
                # Use token_hash for verification (new version)
                supabase_response = settings.SUPABASE.auth.verify_otp({
                    'token_hash': token_hash,
                    'type': 'recovery'
                })
            elif code:
                # Fallback to code for older versions
                supabase_response = settings.SUPABASE.auth.verify_otp({
                    'token': code,
                    'type': 'recovery'
                })
            else:
                raise Exception("No verification token found")
            
            if supabase_response and supabase_response.user:
                # Successful password reset
                email = supabase_response.user.email
                
                # Optionally update Django user model with verification status
                try:
                    django_user = User.objects.get(email=email)
                    supabase_user = SupabaseUser.objects.get(user=django_user)
                    supabase_user.email_verified = True
                    supabase_user.save()
                except (User.DoesNotExist, SupabaseUser.DoesNotExist):
                    pass  # User might not exist in Django yet
                
                messages.success(request, "Password reset successful! You can now log in with your new password.")
            else:
                messages.error(request, "Invalid password reset token.")
                
        except Exception as e:
            messages.error(request, f"Error resetting password: {str(e)}")
    else:
        messages.error(request, "Invalid password reset request.")
    
    return redirect('login')



def check_email_verification(request):
    if request.user.is_authenticated:
        try:
            access_token = request.session.get('supabase_access_token')
            
            if access_token:
                user_data = settings.SUPABASE.auth.get_user(access_token)
                
                # Update SupabaseUser model if verification status changed
                supabase_user = SupabaseUser.objects.get(user=request.user)
                email_verified = bool(user_data.user.email_confirmed_at)
                
                if supabase_user.email_verified != email_verified:
                    supabase_user.email_verified = email_verified
                    supabase_user.save()
                
                context = {
                    'email_verified': email_verified,
                    'user': request.user
                }
                
                return render(request, 'verification_success.html', context)
            
        except Exception as e:
            messages.error(request, f"Error checking verification status: {str(e)}")
    
    return redirect('login')



def resend_verification_email(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        
        if not email:
            messages.error(request, "Email is required.")
            return redirect('login')
        
        try:
            settings.SUPABASE.auth.resend(
                'signup',
                {
                    'email': email,
                    'options': {
                        'email_redirect_to': 'http://127.0.0.1:8000/auth/verify',
                    }
                }
            )
            
            messages.success(request, "Verification email sent! Please check your inbox.")
        except Exception as e:
            messages.error(request, f"Error sending verification email: {str(e)}")
    
    return redirect('login')




def verify_email_callback(request):
    token_hash = request.GET.get('token_hash')
    type_param = request.GET.get('type')
    
    if type_param == 'signup' and token_hash:
        try:
            # Use token_hash for verification
            supabase_response = settings.SUPABASE.auth.verify_otp({
                'token_hash': token_hash,
                'type': 'signup'
            })
            
            if supabase_response and supabase_response.user:
                email = supabase_response.user.email
                
                try:
                    django_user = User.objects.get(email=email)
                    
                    supabase_user, created = SupabaseUser.objects.get_or_create(
                        user=django_user,
                        defaults={
                            'supabase_id': supabase_response.user.id,
                            'email_verified': True
                        }
                    )
                    
                    if not created:
                        supabase_user.email_verified = True
                        supabase_user.save()
                    
                    messages.success(request, "Email verified successfully! You can now log in.")
                except User.DoesNotExist:
                    messages.error(request, "User not found.")
            else:
                messages.error(request, "Invalid verification token.")
                
        except Exception as e:
            messages.error(request, f"Error verifying email: {str(e)}")
    else:
        messages.error(request, "Invalid verification request.")
    
    return redirect('login')








