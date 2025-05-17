import re
from django.shortcuts import render, redirect
from django.contrib.auth.models import User
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
import requests
from .models import SupabaseUser 
from waffrli.models import Customer
from django.conf import settings

def register(request):
    if request.method == 'POST':
        # Get form data
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        email = request.POST.get('email', '').strip()
        phone = request.POST.get('phone', '').strip()
        password = request.POST.get('password')
        confirm_password = request.POST.get('confirm_password')
        gender = request.POST.get('gender')
        image = request.FILES.get('image')
        
        latitude = request.POST.get('latitude')
        longitude = request.POST.get('longitude')
        formatted_address = request.POST.get('formatted_address')
        
        # Validate required fields
        if not all([first_name, last_name, email, phone, password, confirm_password, gender]):
            messages.error(request, "All fields marked with * are required")
            return render(request, 'register.html')
        
        # Validate name length
        if len(first_name) < 2 or len(last_name) < 2:
            messages.error(request, "Names must be at least 2 characters long")
            return render(request, 'register.html')
        
        # Validate email format
        email_regex = r'^[^\s@]+@[^\s@]+\.[^\s@]+$'
        if not re.match(email_regex, email):
            messages.error(request, "Please enter a valid email address")
            return render(request, 'register.html')
        
        # Validate phone number
        phone_digits = re.sub(r'\D', '', phone)
        if len(phone_digits) != 10:
            messages.error(request, "Phone number must be 10 digits")
            return render(request, 'register.html')
        
        # Validate password match
        if password != confirm_password:
            messages.error(request, "Passwords don't match")
            return render(request, 'register.html')
        
        # Validate password strength
        password_errors = []
        if len(password) < 8:
            password_errors.append("Password must be at least 8 characters long")
        if not re.search(r'[A-Z]', password):
            password_errors.append("Password must contain at least one uppercase letter")
        if not re.search(r'[a-z]', password):
            password_errors.append("Password must contain at least one lowercase letter")
        if not re.search(r'[0-9]', password):
            password_errors.append("Password must contain at least one number")
        if not re.search(r'[!@#$%^&*()_+\-=\[\]{};:"\\|,.<>\/?]', password):
            password_errors.append("Password must contain at least one special character")
        
        if password_errors:
            for error in password_errors:
                messages.error(request, error)
            return render(request, 'register.html')
        
        # Validate location
        if not latitude or not longitude:
            messages.error(request, "Please select your location on the map")
            return render(request, 'register.html')
        
        # Check if email already exists
        if User.objects.filter(email=email).exists():
            messages.error(request, "Email already exists")
            return render(request, 'register.html')
        
        try:
            # Create Supabase user
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
            
            # Generate unique username
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
            

            Customer.objects.create(
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
        
        
        try:
            try:
                django_user = User.objects.get(email=email)
                print(f"Found Django user: {django_user.username}")
            except User.DoesNotExist:
                messages.error(request, "Invalid email or password.")
                return render(request, 'login.html', {'email': email})
            

            try:
                customer = Customer.objects.get(email=email)
                if customer.password == password:
                    if not django_user.check_password(password):
                        django_user.set_password(password)
                        django_user.save()

                    user = authenticate(request, username=django_user.username, password=password)
                    if user is not None:

                        login(request, user)
                        messages.success(request, "Login successful!")
                        return redirect('home')
                    else:
                        messages.error(request, "Authentication error. Please try again.")
                        return render(request, 'login.html', {'email': email})
                else:

                    user = authenticate(request, username=django_user.username, password=password)
                    if user is not None:

                        customer.password = password
                        customer.save()
                        

                        login(request, user)
                        messages.success(request, "Login successful!")
                        return redirect('home')
                    else:
                        messages.error(request, "Invalid email or password.")
                        return render(request, 'login.html', {'email': email})
            except Customer.DoesNotExist:
                
                user = authenticate(request, username=django_user.username, password=password)
                if user is not None:
                    Customer.objects.create(
                        user=django_user,
                        email=email,
                        password=password,
                        first_name=django_user.first_name,
                        last_name=django_user.last_name,
                    )

                    login(request, user)
                    messages.success(request, "Login successful!")
                    return redirect('home')
                else:
                    messages.error(request, "Invalid email or password.")
                    return render(request, 'login.html', {'email': email})
        
        except Exception as e:
            messages.error(request, f"Login error: {str(e)}")
            return render(request, 'login.html', {'email': email})
    show_reset = request.GET.get('reset', False)
    
    return render(request, 'login.html', {'email': reset_email, 'show_reset': show_reset})

def logout_view(request):
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

        request.session['signup_token'] = token or token_hash
        request.session['signup_type'] = type_param
        
        # Redirect to a page where the user can enter their email
        return redirect('complete_email_verification')
        
    elif type_param == 'recovery' and (token or token_hash):
        try:

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
            params = {
                'email': email,
                'token': token,
                'type': type_param
            }
            
            print(f"Attempting verification with params: {params}")
            supabase_response = settings.SUPABASE.auth.verify_otp(params)
            print(f"Supabase response: {supabase_response}")
            
            if supabase_response:
                try:

                    django_user = User.objects.get(email=email)
                    django_user.set_password(new_password)
                    django_user.save()
                    print(f"Updated Django User password for {email}")
                    

                    try:
                        customer = Customer.objects.get(email=email)
                        customer.password = new_password
                        customer.save()
                        print(f"Updated Customer model password for {email}")
                    except Customer.DoesNotExist:

                        Customer.objects.create(
                            user=django_user,
                            email=email,
                            password=new_password,
                            first_name=django_user.first_name,
                            last_name=django_user.last_name,
                        )
                        print(f"Created new Customer record for {email}")
                    
                    if 'reset_token' in request.session: 
                        del request.session['reset_token']
                    if 'reset_type' in request.session:
                        del request.session['reset_type']
                    

                    request.session['reset_email'] = email
                    
                    messages.success(request, "Your password has been updated. Please log in with your new password.")
                    return redirect('login')
                except User.DoesNotExist:
                    messages.error(request, "User not found in our system.")
            else:
                messages.error(request, "Invalid verification. Please try resetting your password again.")
                return redirect('forgot_password')
                
        except Exception as e:
            messages.error(request, f"Error during password recovery: {str(e)}")
            import traceback
            traceback.print_exc()
            
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


def reset_password_view(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        new_password = request.POST.get('new_password')
        confirm_password = request.POST.get('confirm_password')
        
        if not email or not new_password or not confirm_password:
            messages.error(request, "All fields are required.")
            return render(request, 'restPassword.html')
            
        if new_password != confirm_password:
            messages.error(request, "Passwords don't match.")
            return render(request, 'restPassword.html')
        
        try:
            # Check if user exists
            try:
                django_user = User.objects.get(email=email)
            except User.DoesNotExist:
                messages.error(request, "No account found with this email.")
                return render(request, 'restPassword.html')
            
            # Update Django User password
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
                # Create Customer if it doesn't exist
                Customer.objects.create(
                    user=django_user,
                    email=email,
                    password=new_password,
                    first_name=django_user.first_name,
                    last_name=django_user.last_name,
                )
                print(f"Created new Customer record for {email}")
            
            messages.success(request, "Your password has been updated successfully! Please log in with your new password.")
            return redirect('login')
            
        except Exception as e:
            messages.error(request, f"Error updating password: {str(e)}")
            import traceback
            traceback.print_exc()
    
    return render(request, 'restPassword.html')


def close_account(request):
    if request.method == 'POST':
        user = request.user
        confirmation = request.POST.get('confirm', '')
        
        if confirmation != 'DELETE':
            messages.error(request, "Please type 'DELETE' to confirm account deletion.")
            return render(request, 'confirm_account_deletion.html')
        
        if user.is_authenticated:
            try:
                # Get Supabase user ID for the user
                supabase_deleted = False
                try:
                    supabase_user = SupabaseUser.objects.get(user=user)
                    supabase_id = supabase_user.supabase_id
                    
                    try:
                        # First attempt with the Supabase client
                        settings.SUPABASE.auth.admin.delete_user(supabase_id)
                        print(f"Successfully deleted Supabase user with ID: {supabase_id}")
                        supabase_deleted = True
                    except Exception as supabase_e:
                        print(f"Could not delete Supabase user with client: {str(supabase_e)}")
                        
                        supabase_url = settings.SUPABASE_URL
                        supabase_service_key = settings.SUPABASE_SERVICE_KEY  # Use service role key for admin operations

                        headers = {
                            'Content-Type': 'application/json',
                            'apikey': supabase_service_key,
                            'Authorization': f'Bearer {supabase_service_key}'
                        }
                        
                        url = f"{supabase_url}/auth/v1/admin/users/{supabase_id}"
                        
                        # Print debug info
                        print(f"Attempting to delete user via API at: {url}")
                        
                        try:
                            response = requests.delete(url, headers=headers)
                            print(f"Response status: {response.status_code}")
                            print(f"Response body: {response.text}")
                            
                            if response.status_code in [200, 204]:  # Both are valid success codes
                                print(f"Successfully deleted Supabase user with ID: {supabase_id} via API")
                                supabase_deleted = True
                            else:
                                print(f"Failed to delete Supabase user via API: {response.status_code}, {response.text}")
                        except Exception as api_e:
                            print(f"API call error: {str(api_e)}")
                            
                except SupabaseUser.DoesNotExist:
                    print("No Supabase user record found for this user")
                
                # Log the user out - import auth_logout at the top of your file
                from django.contrib.auth import logout as auth_logout
                auth_logout(request)
                
                # Delete Django user
                user.delete()
                
                if supabase_deleted:
                    messages.success(request, "Your account has been successfully deleted from all systems.")
                else:
                    messages.success(request, "Your account has been deleted from our system, but there might have been an issue with external services.")
                    # You could log this for admin follow-up
                
                return redirect('home')
                
            except Exception as e:
                messages.error(request, f"Error deleting account: {str(e)}")
                return redirect('settings')
        else:
            messages.error(request, "You must be logged in to delete your account.")
            return redirect('login')  # Use the URL name 'login', not the function name
    else:
        # Display confirmation page for GET requests
        return render(request, 'confirm_account_deletion.html')