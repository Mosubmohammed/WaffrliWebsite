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


def login_view(request):
    # Pre-fill email if coming from password reset
    reset_email = request.session.get('reset_email', '')
    if reset_email:
        del request.session['reset_email']
    
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')
        
        print(f"Attempting login for email: {email}")
        
        try:
            try:
                django_user = User.objects.get(email=email)
                print(f"Found Django user: {django_user.username}")
            except User.DoesNotExist:
                messages.error(request, "Invalid email or password.")
                return render(request, 'login.html', {'email': email})
            
            # Try Django authentication first
            user = authenticate(request, username=django_user.username, password=password)
            if user is not None:
                print(f"Django authentication successful for {email}")
                
                # Try Supabase authentication
                try:
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
                        
                    # Both Django and Supabase authentication successful
                    login(request, user)
                    request.session['supabase_access_token'] = supabase_response.session.access_token
                    request.session['supabase_user_id'] = supabase_response.user.id
                    
                    # Ensure Customer model is in sync
                    try:
                        customer = Customer.objects.get(email=email)
                        if customer.password != password:
                            # Update Customer model password if out of sync
                            customer.password = password
                            customer.save()
                            print(f"Updated Customer model password during login for {email}")
                    except Customer.DoesNotExist:
                        print(f"No Customer found with email {email}")
                    
                    messages.success(request, "Login successful!")
                    return redirect('home')
                    
                except Exception as supabase_e:
                    print(f"Supabase authentication failed: {str(supabase_e)}")
                    
                    # Check if this is a new system (e.g. after password reset)
                    # If Django auth is successful but Supabase auth failed,
                    # attempt to repair the Supabase account
                    try:
                        # Try to get the user from Supabase to check if they exist
                        supabase_user = settings.SUPABASE.auth.admin.get_user_by_email(email)
                        if supabase_user:
                            # If account exists in Supabase, offer password reset
                            messages.error(request, "Your account exists but the password may be out of sync. Please reset your password.")
                            context = {
                                'email': email,
                                'show_reset': True
                            }
                            return render(request, 'login.html', context)
                    except:
                        # If we couldn't check Supabase user, just suggest password reset
                        messages.error(request, "Authentication error. Your password may need to be synchronized. Please try resetting your password.")
                        return render(request, 'login.html', {'email': email, 'show_reset': True})
            else:
                print(f"Django authentication failed for {email}")
                
                # Try the Customer model directly
                try:
                    customer = Customer.objects.get(email=email)
                    if customer.password == password:
                        # If Customer password matches but Django authentication failed,
                        # update the Django User password to match
                        django_user.set_password(password)
                        django_user.save()
                        print(f"Updated Django User password to match Customer model for {email}")
                        
                        # Try authentication again
                        user = authenticate(request, username=django_user.username, password=password)
                        if user is not None:
                            # Try Supabase login
                            try:
                                supabase_response = settings.SUPABASE.auth.sign_in_with_password({
                                    "email": email,
                                    "password": password
                                })
                                
                                login(request, user)
                                request.session['supabase_access_token'] = supabase_response.session.access_token
                                request.session['supabase_user_id'] = supabase_response.user.id
                                
                                messages.success(request, "Login successful after synchronization!")
                                return redirect('home')
                            except:
                                # If Supabase still fails, offer password reset
                                messages.error(request, "Your account was partially synchronized. Please reset your password to complete synchronization.")
                                return render(request, 'login.html', {'email': email, 'show_reset': True})
                        else:
                            messages.error(request, "Authentication synchronization failed. Please reset your password.")
                            return render(request, 'login.html', {'email': email, 'show_reset': True})
                except Customer.DoesNotExist:
                    messages.error(request, "Invalid email or password.")
                    return render(request, 'login.html', {'email': email})
                
                messages.error(request, "Invalid email or password.")
                return render(request, 'login.html', {'email': email})
                
        except Exception as e:
            messages.error(request, f"Login error: {str(e)}")
            return render(request, 'login.html', {'email': email})
    
    # Add a flag to show password reset option
    show_reset = request.GET.get('reset', False)
    
    return render(request, 'login.html', {'email': reset_email, 'show_reset': show_reset})

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
    email_prefill = request.GET.get('email', '')
    
    if request.method == 'POST':
        email = request.POST.get('email')
        
        if not email:
            messages.error(request, "Email is required.")
            return render(request, 'forgot_password.html', {'email': email_prefill})
        
        try:
            # Redirect to your verify endpoint
            settings.SUPABASE.auth.reset_password_for_email(
                email,
                {
                    "redirect_to": "http://127.0.0.1:8000/auth/verify/", 
                }
            )
            
            messages.success(request, "If your email exists in our system, you will receive a password reset link.")
            return redirect('login')
            
        except Exception as e:
            messages.error(request, f"Error: {str(e)}")
            return render(request, 'forgot_password.html', {'email': email})
    
    return render(request, 'forgot_password.html', {'email': email_prefill})


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
                        'email_redirect_to': 'http://127.0.0.1:8000/auth/verify/',
                    }
                }
            )
            
            messages.success(request, "Verification email sent! Please check your inbox.")
        except Exception as e:
            messages.error(request, f"Error sending verification email: {str(e)}")
    
    return redirect('login')


def verify_email_callback(request):
    token = request.GET.get('token')
    token_hash = request.GET.get('token_hash')
    type_param = request.GET.get('type')
    redirect_to = request.GET.get('redirect_to')
    
    print(f"Verification callback accessed with: token={token}, type={type_param}, redirect_to={redirect_to}")
    
    if type_param == 'signup' and (token or token_hash):
        # The issue is here - we need to get the email from the token first
        # Since we don't have the email directly in the URL parameters,
        # we need to redirect to a page where the user can enter their email
        request.session['signup_token'] = token or token_hash
        request.session['signup_type'] = type_param
        
        # Redirect to a page where the user can enter their email
        return redirect('complete_email_verification')
        
    elif type_param == 'recovery' and (token or token_hash):
        try:
            # For password recovery, redirect to the complete_password_reset page
            # Store the token in session
            request.session['reset_token'] = token or token_hash
            request.session['reset_type'] = type_param
            
            # Redirect to a form where the user can enter their email and new password
            return redirect('complete_password_reset')
                
        except Exception as e:
            messages.error(request, f"Error during password recovery: {str(e)}")
    else:
        messages.error(request, "Invalid verification request.")
    
    return redirect('login')


def complete_password_reset(request):
    if 'reset_token' not in request.session or 'reset_type' not in request.session:
        messages.error(request, "Password reset session expired. Please try again.")
        return redirect('forgot_password')
        
    if request.method == 'POST':
        email = request.POST.get('email')
        new_password = request.POST.get('new_password')
        confirm_password = request.POST.get('confirm_password')
        
        if not email or not new_password or not confirm_password:
            messages.error(request, "All fields are required.")
            return render(request, 'complete_password_reset.html')
            
        if new_password != confirm_password:
            messages.error(request, "Passwords don't match.")
            return render(request, 'complete_password_reset.html')
            
        token = request.session.get('reset_token')
        type_param = request.session.get('reset_type')
        
        try:
            # Verify with both email and token
            params = {
                'email': email,
                'token': token,
                'type': type_param
            }
            
            print(f"Attempting verification with params: {params}")
            supabase_response = settings.SUPABASE.auth.verify_otp(params)
            
            # If verification successful, update password
            if supabase_response and hasattr(supabase_response, 'session') and supabase_response.session:
                try:
                    # Update Supabase password if possible
                    try:
                        # Try to update the Supabase password using the session token
                        supabase_session = supabase_response.session.access_token
                        settings.SUPABASE.auth.sign_in_with_password({
                            "email": email,
                            "password": new_password
                        })
                        print("Successfully updated Supabase password")
                    except Exception as supabase_e:
                        print(f"Could not update Supabase password: {str(supabase_e)}")
                    
                    # Update Django user password
                    django_user = User.objects.get(email=email)
                    django_user.set_password(new_password)
                    django_user.save()
                    print(f"Updated Django User password for {email}")
                    
                    # Update Customer model password
                    try:
                        customer = Customer.objects.get(email=email)
                        customer.password = new_password
                        customer.save()
                        print(f"Updated Customer model password for {email}")
                    except Customer.DoesNotExist:
                        print(f"No Customer found with email {email}")
                    
                    # Clean up session
                    del request.session['reset_token']
                    del request.session['reset_type']
                    
                    # Store the email in session to pre-fill login form
                    request.session['reset_email'] = email
                    
                    messages.success(request, "Your password has been reset successfully! Please log in with your new password.")
                    return redirect('login')
                except User.DoesNotExist:
                    messages.error(request, "User not found.")
            else:
                messages.error(request, "Invalid email or token combination.")
                
        except Exception as e:
            messages.error(request, f"Error during password recovery: {str(e)}")
            
    return render(request, 'complete_password_reset.html')

def complete_email_verification(request):
    """Handle the final step of email verification with both email and token."""
    if 'signup_token' not in request.session or 'signup_type' not in request.session:
        messages.error(request, "Email verification session expired. Please try again.")
        return redirect('login')
        
    if request.method == 'POST':
        email = request.POST.get('email')
        
        if not email:
            messages.error(request, "Email is required.")
            return render(request, 'complete_email_verification.html')
            
        token = request.session.get('signup_token')
        type_param = request.session.get('signup_type')
        
        try:
            # Verify with both email and token
            params = {
                'email': email,
                'token': token,
                'type': type_param
            }
            
            print(f"Attempting email verification with params: {params}")
            supabase_response = settings.SUPABASE.auth.verify_otp(params)
            
            # If verification successful, update email verification status
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
                    
                    # Clean up session
                    del request.session['signup_token']
                    del request.session['signup_type']
                    
                    messages.success(request, "Email verified successfully! You can now log in.")
                    return redirect('login')
                except User.DoesNotExist:
                    messages.error(request, "User not found.")
            else:
                messages.error(request, "Invalid email or token combination.")
                
        except Exception as e:
            messages.error(request, f"Error verifying email: {str(e)}")
            
    return render(request, 'complete_email_verification.html')