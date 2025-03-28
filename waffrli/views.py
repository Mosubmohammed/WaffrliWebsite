
from decimal import Decimal, InvalidOperation
from django.shortcuts import get_object_or_404, redirect, render
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.http import JsonResponse
from django.db.models import Q
import firebase_admin
from .models import *
from django.contrib.auth.decorators import login_required
from django.db.models import Count, F, ExpressionWrapper, FloatField,Sum
from django.contrib.auth.models import User
from firebase_admin import auth as firebase_auth
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from .utils import *
import os
from waffrliApp.settings import db
from firebase_admin import firestore

def home(request):
    products = Product.objects.all()

    return render(request, 'home.html',{'products':products})



def category(request, foo):
    foo = foo.replace('-', ' ').strip()
    try:
        category = Category.objects.get(name__iexact=foo)
        products = Product.objects.filter(category=category)
        
        # Get unique store names from products in this category
        stores = Product.objects.filter(category=category).values_list('store', flat=True).distinct()
        
        # Get unique city names (instead of location)
        cities = Product.objects.filter(category=category).values_list('city', flat=True).distinct()
        
        # Get unique brand names
        brands = Product.objects.filter(category=category).values_list('brand', flat=True).distinct()

        return render(request, 'category.html', {
            'products': products, 
            'category': category, 
            'stores': stores,
            'locations': cities,  # Pass cities as locations for the template
            'brands': brands
        })
    except Category.DoesNotExist:
        messages.error(request, 'That category does not exist')
    except Exception as e:
        print(f"Unexpected error: {e}")
        messages.error(request, 'An unexpected error occurred')

    return redirect('home')





def filter_products(request, foo):
    foo = foo.replace('-', ' ').strip()
    
    try:
        category = get_object_or_404(Category, name__iexact=foo)
        
        # Get filter parameters
        store_names = request.GET.get("stores", "").split(",") if request.GET.get("stores") else []
        location_names = request.GET.get("locations", "").split(",") if request.GET.get("locations") else []
        brand_names = request.GET.get("brands", "").split(",") if request.GET.get("brands") else []
        min_price = request.GET.get("min_price", 0)
        max_price = request.GET.get("max_price", 999999)
        rating_filter = request.GET.get("ratings", "0")
        
        # Convert to numbers to prevent errors
        try:
            min_price = float(min_price)
            max_price = float(max_price)
        except ValueError:
            return JsonResponse({"error": "Invalid price filters"}, status=400)
        
        # Start filtering by category and sale_price
        products = Product.objects.filter(category=category, sale_price__gte=min_price, sale_price__lte=max_price)
        
        # Apply store filtering only if stores are selected
        if store_names and store_names[0] != "":
            products = products.filter(store__in=store_names)
        
        # Apply city filtering (instead of location) only if cities are selected
        if location_names and location_names[0] != "":
            products = products.filter(city__in=location_names)
        
        # Apply brand filtering only if brands are selected
        if brand_names and brand_names[0] != "":
            products = products.filter(brand__in=brand_names)
        
        # Apply rating (likes) filtering
        if rating_filter and rating_filter != "0":
            try:
                min_rating = int(rating_filter)
                # Using annotation to count likes for proper filtering
                from django.db.models import Count
                products = products.annotate(likes_count=Count('likes')).filter(likes_count__gte=min_rating)
            except ValueError:
                pass
        
        # Ensure distinct products
        products = products.distinct()
        
        data = {
            "products": [
                {
                    "id": p.id,
                    "name": p.Name,
                    "store": p.store,
                    "city": p.city,  # Change location to city in response
                    "brand": p.brand,
                    "price": str(p.Price),
                    "sale_price": str(p.sale_price) if p.sale_price else None,
                    "description": p.Description,
                    "create_at": p.create_at.strftime("%d-%m"),
                    "username": p.user.username if p.user else "Unknown",
                    "customer_pic_url": p.customer_pic_id.image.url if p.customer_pic_id and p.customer_pic_id.image else None,
                    "image_url": p.image.url if p.image else "/static/images/default-product.png",
                    "likes_count": p.likes.count(),
                    "liked_by_user": request.user in p.likes.all(),
                    "comment_count": 0,  # Replace with actual count if needed
                }
                for p in products
            ]
        }
        return JsonResponse(data)
    
    except Category.DoesNotExist:
        return JsonResponse({"error": "Category not found"}, status=404)


    
    
    
def AllCategory(request):
    categories = Category.objects.all()
    return render(request, 'AllCategory.html', {})




def product(request, pk):
    try:
        # Get the product
        product = get_object_or_404(Product, id=pk)
        
        # Increment views
        product.increment_views()
        
        # Handle POST request for comment submission
        if request.method == 'POST':
            comment_text = request.POST.get('comment')
            if comment_text and request.user.is_authenticated:
                # Get the current logged-in user's customer
                customer = Customer.objects.get(user=request.user)
                
                # Create and save the comment
                Comment.objects.create(
                    product=product,
                    customer=customer,
                    text=comment_text
                )
                messages.success(request, 'Your comment has been posted successfully!')
            else:
                messages.warning(request, 'Please write a comment or log in to comment.')
        
        # Retrieve all comments for this product
        comments = product.comments.all()
        
        # Get related products (products in the same category, excluding current product)
        related_products = Product.objects.filter(
            category=product.category
        ).exclude(
            id=product.id
        ).order_by(
            '-create_at'  # Sort by newest first
        )[:6]  # Limit to 6 products
        
        # Calculate discount percentage for product and related products
        if product.Price and product.sale_price:
            product.discount_percentage = round(((product.Price - product.sale_price) / product.Price) * 100)
        else:
            product.discount_percentage = 0
            
        # Calculate discount for related products
        for related_product in related_products:
            if related_product.Price and related_product.sale_price:
                discount = ((related_product.Price - related_product.sale_price) / related_product.Price) * 100
                related_product.discount_percentage = round(discount)
            else:
                related_product.discount_percentage = 0
                
            # Add a flag for popular products (e.g., products with high views or likes)
            related_product.is_popular = related_product.views > 100 or related_product.likes.count() > 10
            
            # Add time ago for display
            related_product.time_ago = related_product.create_at
        
        # Create context with all necessary data
        context = {
            'product': product,
            'comments': comments,
            'related_products': related_products,
            'user': request.user,  # Ensure user is in context
        }
        
        return render(request, 'product.html', context)
    
    except Product.DoesNotExist:
        messages.error(request, 'That product does not exist.')
        return redirect('home')



# def register(request):
#     if request.method == 'POST':
#         first_name = request.POST.get('first_name')
#         last_name = request.POST.get('last_name')
#         email = request.POST.get('email')
#         phone = request.POST.get('phone')
#         password = request.POST.get('password')
#         confirm_password = request.POST.get('confirm_password')
#         gender = request.POST.get('gender')
#         address = request.POST.get('address')
#         city = request.POST.get('city')
#         image = request.FILES.get('image')
        
#         # Generate username from email
#         username = email.split('@')[0]
        
#         # Basic validation
#         if password != confirm_password:
#             messages.error(request, "Passwords don't match")
#             return render(request, 'register.html')
        
#         try:
#             # Step 1: Create user in Firebase Auth
#             firebase_user = firebase_auth.create_user(
#                 email=email,
#                 password=password,
#                 display_name=f"{first_name} {last_name}",
#                 email_verified=False
#             )
#             firebase_uid = firebase_user.uid
            
#             # Step 2: Try to store in Firestore, but handle potential failure
#             try:
#                 # Store user data in Firestore
#                 user_data = {
#                     'uid': firebase_uid,
#                     'username': username,
#                     'email': email,
#                     'first_name': first_name,
#                     'last_name': last_name,
#                     'phone': phone,
#                     'gender': gender,
#                     'address': address,
#                     'city': city,
#                     'email_verified': False,
#                     'created_at': firestore.SERVER_TIMESTAMP
#                 }
                
#                 # Add user document to Firestore
#                 db.collection('users').document(firebase_uid).set(user_data)
#                 firestore_success = True
#             except Exception as firestore_error:
#                 print(f"Firestore error: {str(firestore_error)}")
#                 messages.warning(request, "Account created in authentication but profile data couldn't be saved to the database. You can still login, but please contact support.")
#                 firestore_success = False
            
#             # Step 3: Try to send verification email
#             try:
#                 verification_link = firebase_auth.generate_email_verification_link(
#                     email, 
#                     action_code_settings=firebase_auth.ActionCodeSettings(
#                         url="http://localhost:8000/verified/",
#                         handle_code_in_app=False
#                     )
#                 )
#                 print(f"Verification link generated: {verification_link}")
#                 email_success = True
#             except Exception as email_error:
#                 print(f"Email verification error: {str(email_error)}")
#                 messages.warning(request, "Account created but verification email could not be sent. Please contact support.")
#                 email_success = False
            
#             # Step 4: Create Django User for authentication
#             django_user = User.objects.create_user(
#                 username=username,
#                 email=email,
#                 password=password,
#                 first_name=first_name,
#                 last_name=last_name,
#                 is_active=True
#             )
            
#             # Login the user
#             login(request, django_user)
            
#             # Provide appropriate success message based on what worked
#             if firestore_success and email_success:
#                 messages.success(request, "Registration successful! Please check your email to verify your account.")
#             elif firestore_success:
#                 messages.success(request, "Registration successful! However, verification email could not be sent.")
#             else:
#                 messages.success(request, "Basic registration successful, but profile data couldn't be saved.")
                
#             return redirect('home')  
            
#         except Exception as e:
#             messages.error(request, f"Registration failed: {str(e)}")
#             return render(request, 'register.html')
    
#     # For GET requests
#     return render(request, 'register.html')



def register(request):
    if request.method == 'POST':
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        email = request.POST.get('email')
        phone = request.POST.get('phone')
        password = request.POST.get('password')
        confirm_password = request.POST.get('confirm_password')
        gender = request.POST.get('gender')
        address = request.POST.get('address')
        city = request.POST.get('city')
        image = request.FILES.get('image')
        
        # Generate username from email (or use a field in your form for username)
        username = email.split('@')[0]
        
        # Basic validation
        if password != confirm_password:
            messages.error(request, "Passwords don't match")
            return render(request, 'register.html')
        
        if User.objects.filter(username=username).exists():
            # Make username unique if it already exists
            base_username = username
            counter = 1
            while User.objects.filter(username=username).exists():
                username = f"{base_username}{counter}"
                counter += 1
        
        if User.objects.filter(email=email).exists():
            messages.error(request, "Email already exists")
            return render(request, 'register.html')
        
        try:
            # Create user in Firebase
            firebase_user = firebase_auth.create_user(
                email=email,
                password=password,
                display_name=f"{first_name} {last_name}",
                email_verified=False  # Explicitly set as not verified
            )
            firebase_uid = firebase_user.uid
            
            # Generate and send verification email - store the link for debugging
            try:
                verification_link = firebase_auth.generate_email_verification_link(
                    email, 
                    action_code_settings=firebase_admin.auth.ActionCodeSettings(
                        url="http://localhost:8000/verified/",
                        handle_code_in_app=False
                    )
                )
                # Print link to console for debugging
                print(f"Verification link generated: {verification_link}")
            
            except Exception as email_error:
                # Log the specific email sending error
                print(f"Email verification error: {str(email_error)}")
                messages.warning(request, "Account created but verification email could not be sent. Please contact support.")
            
            # Create Django User
            django_user = User.objects.create_user(
                username=username,
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name,
                is_active=True  # User can still log in to your site, but you can check verification status
            )
            
            # Link Django User to Firebase
            FirebaseUser.objects.create(
                user=django_user,
                firebase_uid=firebase_uid,
                email_verified=False  # Track verification status in your database
            )
            
            # Create Customer profile
            customer = Customer.objects.create(
                user=django_user,
                first_name=first_name,
                last_name=last_name,
                phone=phone,
                email=email,
                password=password,  # Note: This is redundant since Django User already stores password
                gender=gender,
                address=address,
                City=city,
            )
            
            # Add image if provided
            if image:
                customer.image = image
                customer.save()
            
            login(request, django_user)
            
            messages.success(request, "Registration successful! Please check your email to verify your account.")
            return redirect('home')  
            
        except Exception as e:
            messages.error(request, f"Registration failed: {str(e)}")
            return render(request, 'register.html')
    
    # For GET requests
    return render(request, 'register.html')


def check_email_verification(request):
    return render(request, 'verification_success.html')


def verify_email_status(request):
    # Function to check if a user's email is verified
    if request.user.is_authenticated:
        try:
            firebase_user = FirebaseUser.objects.get(user=request.user)
            # Get fresh user data from Firebase
            firebase_user_info = firebase_auth.get_user(firebase_user.firebase_uid)
            
            # Update local record if verification status changed
            if firebase_user_info.email_verified != firebase_user.email_verified:
                firebase_user.email_verified = firebase_user_info.email_verified
                firebase_user.save()
            
            return firebase_user.email_verified
        except FirebaseUser.DoesNotExist:
            return False
    return False



# def login_view(request):
#     if request.method == 'POST':
#         email = request.POST.get('email')
#         password = request.POST.get('password')
        
#         try:
#             # First, check if the user exists in Firebase
#             try:
#                 firebase_user = firebase_auth.get_user_by_email(email)
#                 firebase_uid = firebase_user.uid
                
#                 # Check if user exists in Firestore
#                 user_doc = db.collection('users').document(firebase_uid).get()
                
#                 # Try Django authentication with email as username
#                 django_username = email.split('@')[0]
#                 django_user = authenticate(request, username=django_username, password=password)
                
#                 # If that fails, try with the actual username from Firestore if available
#                 if django_user is None and user_doc.exists:
#                     user_data = user_doc.to_dict()
#                     if 'username' in user_data:
#                         django_user = authenticate(request, username=user_data['username'], password=password)
                
#                 # If still not authenticated, try finding the Django user by email
#                 if django_user is None:
#                     try:
#                         django_account = User.objects.get(email=email)
#                         django_user = authenticate(request, username=django_account.username, password=password)
#                     except User.DoesNotExist:
#                         pass
                
#                 if django_user is not None:
#                     # User authenticated with Django, log them in
#                     login(request, django_user)
                    
#                     # Store Firebase UID in session for middleware use
#                     request.session['firebase_uid'] = firebase_uid
                    
#                     # Store user profile data in session if needed
#                     if user_doc.exists:
#                         user_data = user_doc.to_dict()
#                         request.session['user_profile'] = {
#                             'name': f"{user_data.get('first_name', '')} {user_data.get('last_name', '')}",
#                             'email': user_data.get('email', ''),
#                             'phone': user_data.get('phone', '')
#                         }
                    
#                     messages.success(request, "Login successful!")
#                     return redirect('home')
#                 else:
#                     messages.error(request, "Invalid email or password.")
#             except firebase_auth.UserNotFoundError:
#                 messages.error(request, "Account not found. Please register first.")
            
#         except Exception as e:
#             messages.error(request, f"Login error: {str(e)}")
        
#         return render(request, 'login.html')
    
#     # For GET requests
#     return render(request, 'login.html')

def login_view(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')
        
        try:
            # Try Django authentication first - trying email as username
            user = authenticate(request, username=email, password=password)
            
            # If that fails, try finding the user by email and then authenticate with their username
            if user is None:
                try:
                    django_user = User.objects.get(email=email)
                    user = authenticate(request, username=django_user.username, password=password)
                except User.DoesNotExist:
                    user = None
                    
            if user is not None:
                # User authenticated successfully with Django
                login(request, user)
                
                # Check if user has a Firebase profile
                firebase_profile = FirebaseUser.objects.filter(user=user).first()
                if firebase_profile:
                    try:
                        # Verify the user exists in Firebase
                        firebase_auth.get_user(firebase_profile.firebase_uid)
                    except Exception as firebase_error:
                        # Firebase verification failed, but still allow Django login
                        print(f"Firebase verification error: {str(firebase_error)}")
                        messages.warning(request, "Logged in successfully, but there may be an issue with your account. Some features may be limited.")
                        return redirect('home')
                
                # All good
                messages.success(request, "Login successful!")
                return redirect('home')
            else:
                # Authentication failed
                messages.error(request, "Invalid email or password.")
                return render(request, 'login.html')
                
        except Exception as e:
            messages.error(request, f"Login error: {str(e)}")
            return render(request, 'login.html')
            
    # For GET requests
    return render(request, 'login.html')

def logout_user(request):
    logout(request)
    messages.success(request, 'Logged out successfully!')
    return redirect('home')



def restPassword(request):

    if request.method == 'POST':
        email = request.POST.get('email')
        new_password = request.POST.get('new_password')
        
        if not email or not new_password:
            messages.error(request, "Email and new password are required.")
            return render(request, 'restPassword.html')
            
        try:
            # Update Django user password
            user = User.objects.get(email=email)
            user.set_password(new_password)
            user.save()
            
            # Update Firebase user password
            try:
                firebase_user = FirebaseUser.objects.get(user=user)
                firebase_auth.update_user(
                    firebase_user.firebase_uid,
                    password=new_password
                )
                messages.success(request, "Password reset successfully! You can now log in with your new password.")
            except FirebaseUser.DoesNotExist:
                messages.warning(request, "Password reset successful in our system, but not synchronized with authentication provider.")
            except Exception as firebase_e:
                messages.warning(request, "Password reset successful in our system, but not synchronized with authentication provider.")
                print(f"Firebase password update error: {str(firebase_e)}")
                
            return redirect('login')
            
        except User.DoesNotExist:
            messages.error(request, "User not found.")
            return render(request, 'restPassword.html')
        except Exception as e:
            messages.error(request, f"Password reset error: {str(e)}")
            return render(request, 'restPassword.html')
            
    # For GET requests
    return render(request, 'restPassword.html')


def forgot_password(request):
    """Handle forgot password requests"""
    if request.method == 'POST':
        email = request.POST.get('email')
        
        if not email:
            messages.error(request, "Email is required.")
            return render(request, 'forgot_password.html')
            
        try:
            # Check if user exists in Django
            user_exists = User.objects.filter(email=email).exists()
            
            if not user_exists:
                # Don't reveal if user exists or not for security
                messages.success(request, "If your email exists in our system, you will receive a password reset link.")
                return render(request, 'forgot_password.html')
                
            # Send password reset email via Firebase
            try:
                reset_link = firebase_auth.generate_password_reset_link(
                    email, 
                    action_code_settings=firebase_admin.auth.ActionCodeSettings(
                        url="http://localhost:8000/password_reset_callback/",
                        handle_code_in_app=False
                    )
                )
                # Here you would actually send the email with the reset_link
                # For debugging, just print it
                print(f"Password reset link: {reset_link}")
                messages.success(request, "Password reset link has been sent to your email.")
            except Exception as firebase_e:
                # Fallback to Django's password reset if Firebase fails
                print(f"Firebase password reset error: {str(firebase_e)}")
                # Implement Django's built-in password reset here
                # Or redirect to Django's password reset view
                messages.warning(request, "Please use our standard password reset process.")
                return redirect('password_reset')  # Django's built-in view
                
            return redirect('login')
            
        except Exception as e:
            messages.error(request, f"Error: {str(e)}")
            return render(request, 'forgot_password.html')
            
    # For GET requests
    return render(request, 'forgot_password.html')


def password_reset_callback(request):
    """Callback endpoint after Firebase password reset"""
    # Extract the new Firebase password and user info from the callback
    # This is where you'd sync the Django user's password with Firebase
    
    # For now, just inform the user
    messages.success(request, "Your password has been reset successfully. You can now log in with your new password.")
    return redirect('login')


def search(request):
    if request.method == "POST":
        searched = request.POST['searched']
        results = Product.objects.filter(
            Q(Name__icontains=searched) |
            Q(Description__icontains=searched) |
            Q(category__name__icontains=searched)
        )

        if not results:
            messages.error(request, "No matching products found.")
            return render(request, "home.html")

        return render(request, "search.html", {'searched': results})

    return render(request, "home.html")


# @login_required
# def post_deal(request):
#     if not request.user.is_authenticated:
#         messages.error(request, "You must be logged in to post a deal.")
#         return redirect('login')
    
#     if request.method == "POST":
#         # Get Firebase UID from session
#         firebase_uid = request.session.get('firebase_uid')
#         if not firebase_uid:
#             messages.error(request, "Authentication issue. Please log out and log in again.")
#             return redirect('home')
        
#         # Fetch form data
#         name = request.POST.get('deal-title')
#         url = request.POST.get('deal-url')
#         sale_price = request.POST.get('sale-price')
#         price = request.POST.get('list-price')
#         description = request.POST.get('description')
#         store = request.POST.get('store')
#         brand = request.POST.get('brand')
#         category_id = request.POST.get('category')
#         location = request.POST.get('location')
#         pic = request.FILES.get('image')
        
#         # Validate required fields
#         if not name or not store or not category_id or not location:
#             messages.error(request, "Please fill in all required fields.")
#             return redirect('post_deal')
        
#         # Fetch category name from Django model (you can move categories to Firestore later)
#         try:
#             category = Category.objects.get(id=int(category_id))
#             category_name = category.name
#         except (Category.DoesNotExist, ValueError):
#             messages.error(request, "Invalid category selected.")
#             return redirect('post_deal')
        
#         # Check if URL already exists in Firestore
#         if url:
#             existing_deals = db.collection('products').where('url', '==', url).get()
#             if len(existing_deals) > 0:
#                 messages.error(request, "A product with this URL already exists.")
#                 return redirect('post_deal')
        
#         # Convert price fields to float safely
#         try:
#             sale_price_float = float(sale_price) if sale_price else 0.0
#             price_float = float(price) if price else 0.0
#         except ValueError:
#             messages.error(request, "Invalid price format.")
#             return redirect('post_deal')
        
#         # Handle image upload - store in Django media first
#         image_url = None
#         if pic:
#             import os
#             from django.conf import settings
            
#             # Create a unique filename with user ID and timestamp
#             import time
#             timestamp = int(time.time())
#             filename = f"{firebase_uid}_{timestamp}_{pic.name}"
            
#             # Ensure the upload directory exists
#             upload_path = os.path.join(settings.MEDIA_ROOT, 'product_images')
#             os.makedirs(upload_path, exist_ok=True)
            
#             # Save the image file
#             with open(os.path.join(upload_path, filename), 'wb+') as destination:
#                 for chunk in pic.chunks():
#                     destination.write(chunk)
            
#             # Set the image URL for storage in Firestore
#             image_url = f"/media/product_images/{filename}"
        
#         # Create product data for Firestore
#         product_data = {
#             'user_id': firebase_uid,
#             'name': name,
#             'url': url,
#             'sale_price': sale_price_float,
#             'price': price_float,
#             'description': description,
#             'store': store,
#             'brand': brand,
#             'image_url': image_url,
#             'category': category_name,
#             'category_id': category_id,
#             'city': location,
#             'views': 0,
#             'likes_count': 0,
#             'created_at': firestore.SERVER_TIMESTAMP,
#             'username': request.user.username,  # Store the username for easy reference
#         }
        
#         # Add to Firestore
#         new_product_ref = db.collection('products').add(product_data)
#         product_id = new_product_ref[1].id
        
#         # Check for wishlist matches in Firestore
#         wishlist_items = db.collection('wishlist').get()
        
#         for item in wishlist_items:
#             wishlist_data = item.to_dict()
#             wishlist_user_id = wishlist_data.get('user_id')
            
#             # Skip the current user's wishlist items
#             if wishlist_user_id == firebase_uid:
#                 continue
                
#             keyword = wishlist_data.get('keyword', '').lower()
#             wishlist_category = wishlist_data.get('category', '')
#             min_price = float(wishlist_data.get('min_price', 0))
#             max_price = float(wishlist_data.get('max_price', 999999))
            
#             # Check if this product matches the wishlist criteria
#             if ((keyword in name.lower() or keyword in description.lower()) and
#                 (not wishlist_category or wishlist_category == category_name) and
#                 (sale_price_float >= min_price and sale_price_float <= max_price)):
                
#                 # Create a notification for the wishlist owner
#                 notification_data = {
#                     'user_id': wishlist_user_id,
#                     'title': 'Wishlist Match Found!',
#                     'message': f'A new deal for "{name}" matches your wishlist alert for "{keyword}".',
#                     'notification_type': 'wishlist_match',
#                     'related_product_id': product_id,
#                     'is_read': False,
#                     'created_at': firestore.SERVER_TIMESTAMP
#                 }
                
#                 db.collection('notifications').add(notification_data)
        
#         messages.success(request, "Deal posted successfully!")
        
#         # Return to the product page - you'll need to update your URL patterns and product view
#         return redirect('product', pk=product_id)
    
#     # For GET requests - just display the form
#     categories = Category.objects.all()
#     return render(request, "post_deal.html", {'categories': categories})



def post_deal(request):
    if not request.user.is_authenticated:
        messages.error(request, "You must be logged in to post a deal.")
        return redirect('login')
    
    if request.method == "POST":
        # Fetch image
        pic = request.FILES.get('image')
        if not pic:
            messages.error(request, "Please upload an image.")
            return redirect('post_deal')
        
        # Fetch form data
        name = request.POST.get('deal-title')
        url = request.POST.get('deal-url')
        sale_price = request.POST.get('sale-price')
        price = request.POST.get('list-price')
        description = request.POST.get('description')
        store = request.POST.get('store')
        brand = request.POST.get('brand')
        category_id = request.POST.get('category')
        location = request.POST.get('location')
        
        # Validate required fields
        if not name or not store or not category_id or not location:
            messages.error(request, "Please fill in all required fields.")
            return redirect('post_deal')
        
        # Fetch category
        try:
            category = Category.objects.get(id=int(category_id))
        except (Category.DoesNotExist, ValueError):
            messages.error(request, "Invalid category selected.")
            return redirect('post_deal')
        
        # Check if URL already exists
        if url and Product.objects.filter(Dealurl=url).exists():
            messages.error(request, "A product with this URL already exists.")
            return redirect('post_deal')
        
        # Convert price fields to Decimal safely
        try:
            sale_price_decimal = Decimal(sale_price) if sale_price else Decimal("0.00")
            price_decimal = Decimal(price) if price else Decimal("0.00")
        except (ValueError, InvalidOperation):
            messages.error(request, "Invalid price format.")
            return redirect('post_deal')
        
        # Create and save the product
        deal = Product.objects.create(
            user=request.user,
            Dealurl=url,
            Name=name,
            sale_price=sale_price_decimal,
            Price=price_decimal,
            Description=description,
            store=store,
            brand=brand,
            image=pic,
            category=category,
            city=location,
        )

        # Check for wishlist matches and create notifications
        check_deal_against_wishlist(deal)


        messages.success(request, "Deal posted successfully!")
            
        return redirect('product', pk=deal.id)
    
    # For GET requests - just display the form
    categories = Category.objects.all()
    return render(request, "post_deal.html", {'categories': categories})





@login_required 
def like_product(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    user = request.user

    if user.is_authenticated:
        if user in product.likes.all():
            product.likes.remove(user)
            liked = False
        else:
            product.likes.add(user)
            liked = True

        return JsonResponse({"liked": liked, "like_count": product.likes.count()})
    
    return JsonResponse({"error": "User not authenticated"}, status=401)

    

# @login_required
# def user_profile(request, identifier):
#     try:
#         # First, try to get the Firebase user by UID
#         try:
#             firebase_user = firebase_auth.get_user(identifier)
#             user_id = firebase_user.uid
#         except:
#             # If that fails, try to get by email
#             try:
#                 # Check if it's an email
#                 if '@' in identifier:
#                     firebase_user = firebase_auth.get_user_by_email(identifier)
#                     user_id = firebase_user.uid
#                 else:
#                     # If not UID or email, check if it's a Django User ID
#                     django_user = get_object_or_404(User, id=identifier)
#                     firebase_user_record = FirebaseUser.objects.get(user=django_user)
#                     user_id = firebase_user_record.firebase_uid
#             except:
#                 return redirect('home')
        
#         # Get the user profile from Firestore
#         user_doc = db.collection('users').document(user_id).get()
        
#         if not user_doc.exists:
#             messages.error(request, "User profile not found")
#             return redirect('home')
            
#         profile_data = user_doc.to_dict()
        
#         # Get all deals (products) posted by this user from Firestore
#         products_ref = db.collection('products').where('user_id', '==', user_id).get()
#         user_products = [doc.to_dict() for doc in products_ref]
        
#         # Calculate stats for the user (deal count, comments, etc.)
#         deal_count = len(user_products)
        
#         # Get likes and views data 
#         total_likes_received = sum([product.get('likes_count', 0) for product in user_products])
#         total_views = sum([product.get('views', 0) for product in user_products])
        
#         # Find the best deal (highest likes)
#         best_deal = None
#         highest_likes = 0
#         for product in user_products:
#             if product.get('likes_count', 0) > highest_likes:
#                 highest_likes = product.get('likes_count', 0)
#                 best_deal = product
        
#         # Calculate reputation points
#         reputation_points = total_likes_received * 5
        
#         # Check if the current user is following this user
#         is_following = False
#         if request.user.is_authenticated:
#             # Check followers collection
#             follower_ref = db.collection('followers').document(f"{request.user.username}_{profile_data.get('username')}")
#             is_following = follower_ref.get().exists
        
#         # Get followers and following counts
#         followers_ref = db.collection('followers').where('following_id', '==', user_id).get()
#         followers = [doc.to_dict() for doc in followers_ref]
        
#         following_ref = db.collection('followers').where('follower_id', '==', user_id).get()
#         following = [doc.to_dict() for doc in following_ref]
        
#         # Increment profile views if not viewing your own profile
#         if request.user.is_authenticated and request.session.get('firebase_uid') != user_id:
#             # Update view count in Firestore
#             db.collection('users').document(user_id).update({
#                 'view_count': firestore.Increment(1)
#             })
#             view_count = profile_data.get('view_count', 0) + 1
#         else:
#             view_count = profile_data.get('view_count', 0)
        
#         context = {
#             'user_profile': profile_data,
#             'is_following': is_following,
#             'followers': followers,
#             'following': following,
#             'deal_count': deal_count,
#             'comment_count': profile_data.get('comment_count', 0),
#             'view_count': view_count,
#             'total_views': total_views,
#             'total_likes_received': total_likes_received,
#             'reputation_points': reputation_points,
#             'best_deal': best_deal,
#         }
        
#         return render(request, 'user_profile.html', context)
        
#     except Exception as e:
#         print(f"Error in user_profile: {str(e)}")
#         messages.error(request, "An error occurred when retrieving this profile")
#         return redirect('home')
    
    
def user_profile(request, identifier):
    profile_user = get_object_or_404(User, Q(id=identifier) | Q(username=identifier))

    is_following = Follow.objects.filter(follower=request.user, following=profile_user).exists()
    followers = profile_user.followers.all()
    following = profile_user.following.all()

    deal_count = Product.objects.filter(user=profile_user).count()
    comment_count = Comment.objects.filter(customer=profile_user.customer).count()

    # Find the best deal (highest likes) and annotate with comment count
    best_deal = (
        Product.objects.filter(user=profile_user)
        .annotate(comment_count=Count("comments"))
        .order_by("-likes")
        .first()
    )

    if profile_user != request.user:
        try:
            customer_profile = profile_user.customer
            customer_profile.view_count += 1
            customer_profile.save()
            view_count = customer_profile.view_count
        except Customer.DoesNotExist:
            view_count = 0
    else:
        view_count = 0

    total_views = (
        Product.objects.filter(user=profile_user).aggregate(Sum("views"))["views__sum"] or 0
    )
    total_likes_received = (
        Product.objects.filter(user=profile_user).aggregate(Sum("likes"))["likes__sum"] or 0
    )
    reputation_points = total_likes_received * 5

    return render(
        request,
        "user_profile.html",
        {
            "user_profile": profile_user,
            "is_following": is_following,
            "followers": followers,
            "following": following,
            "deal_count": deal_count,
            "comment_count": comment_count,
            "view_count": view_count,
            "total_views": total_views,
            "total_likes_received": total_likes_received,
            "reputation_points": reputation_points,
            "best_deal": best_deal,
        },
    )





@login_required
def wishlist(request):
    """
    Display the wishlist page with the user's wishlist items
    """
    # Get the user's wishlist items
    wishlist_items = WishlistItem.objects.filter(user=request.user).order_by('-created_at')
    
    # Get all categories from the database
    categories = Category.objects.all()
    
    # Get unread notification count for the navbar
    unread_notification_count = Notification.objects.filter(user=request.user, is_read=False).count()
    
    context = {
        'wishlist_items': wishlist_items,
        'categories': categories,
        'unread_notification_count': unread_notification_count,
    }
    
    return render(request, 'wishlist.html', context)

@login_required
def add_wishlist_item(request):
    """
    Add a new wishlist item
    """
    try:
        # Parse the JSON data from the request
        data = json.loads(request.body)
        
        # Get the category instance
        try:
            category = Category.objects.get(id=data.get('category'))
            category_name = category.name  # Get the name from the Category object
        except Category.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Category not found'}, status=404)
        
        # Create a new wishlist item
        wishlist_item = WishlistItem(
            user=request.user,
            keyword=data.get('keyword'),
            min_price=data.get('minPrice'),
            max_price=data.get('maxPrice'),
            category=category_name  # Store the name, not the object
        )
        wishlist_item.save()
        
        # Return the wishlist item data with the ID
        return JsonResponse({
            'status': 'success',
            'id': wishlist_item.id,
            'category_name': category_name,
            'created_at': wishlist_item.created_at.isoformat(),
        })
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)

@login_required
def update_wishlist_item(request, item_id):
    """
    Update a wishlist item
    """
    try:
        # Get the wishlist item
        wishlist_item = WishlistItem.objects.get(id=item_id, user=request.user)
        
        # Parse the JSON data from the request
        data = json.loads(request.body)
        
        # Get the category instance
        try:
            category = Category.objects.get(id=data.get('category'))
            category_name = category.name  # Get the name from the Category object
        except Category.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Category not found'}, status=404)
        
        # Update the wishlist item
        wishlist_item.keyword = data.get('keyword')
        wishlist_item.min_price = data.get('minPrice')
        wishlist_item.max_price = data.get('maxPrice')
        wishlist_item.category = category_name  # Store the name, not the object
        wishlist_item.save()
        
        return JsonResponse({
            'status': 'success',
            'category_name': category_name
        })
    except WishlistItem.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Wishlist item not found'}, status=404)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)

@login_required
def delete_wishlist_item(request, item_id):
    """
    Delete a wishlist item
    """
    try:
        # Get the wishlist item
        wishlist_item = WishlistItem.objects.get(id=item_id, user=request.user)
        
        # Store the keyword and category for the notification
        keyword = wishlist_item.keyword
        category_name = wishlist_item.category  # This is already a string
        
        # Delete the wishlist item
        wishlist_item.delete()
        
        # Create a notification for the deleted wishlist item
        notification = Notification(
            user=request.user,
            title="Wishlist Alert Removed",
            message=f"You've removed the wishlist alert for \"{keyword}\" in the {category_name} category.",
            notification_type='info'
        )
        notification.save()
        
        return JsonResponse({'status': 'success'})
    except WishlistItem.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Wishlist item not found'}, status=404)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)


@login_required
def follow(request, user_id):
    user_to_follow = get_object_or_404(User, id=user_id)
    if user_to_follow != request.user:
        Follow.objects.get_or_create(follower=request.user, following=user_to_follow)
    return redirect('user_profile', user_id=user_id)

@login_required
def unfollow(request, user_id):
    user_to_unfollow = get_object_or_404(User, id=user_id)
    Follow.objects.filter(follower=request.user, following=user_to_unfollow).delete()
    return redirect('user_profile', user_id=user_id)


# @login_required
# def settings(request):
#     try:
#         # Get Firebase UID from session
#         firebase_uid = request.session.get('firebase_uid')
#         if not firebase_uid:
#             messages.error(request, "Authentication issue. Please log out and log in again.")
#             return redirect('home')
        
#         # Get user profile from Firestore
#         user_doc = db.collection('users').document(firebase_uid).get()
        
#         if not user_doc.exists:
#             messages.error(request, "User profile not found. Please contact support.")
#             return redirect('home')
            
#         user_data = user_doc.to_dict()
#         allow_username_edit = False  # Set to True if you want to allow direct username edits
        
#         if request.method == 'POST':
#             # Handle username change request
#             if 'request_username' in request.POST:
#                 new_username = request.POST.get('new_username')
#                 if new_username:
#                     # Update username in Firebase and Django
#                     db.collection('users').document(firebase_uid).update({
#                         'username': new_username
#                     })
                    
#                     # Also update Django username for consistency
#                     request.user.username = new_username
#                     request.user.save()
                    
#                     messages.success(request, 'Username updated successfully!')
#                     return redirect('settings')
            
#             # Handle email update
#             if 'update_profile' in request.POST:
#                 email = request.POST.get('email')
#                 if email and email != user_data.get('email'):
#                     # Update email in Firebase Auth
#                     firebase_auth.update_user(firebase_uid, email=email)
                    
#                     # Update email in Firestore
#                     db.collection('users').document(firebase_uid).update({
#                         'email': email,
#                         'email_verified': False
#                     })
                    
#                     # Update Django user's email for consistency
#                     request.user.email = email
#                     request.user.save()
                    
#                     messages.success(request, 'Email updated successfully! Please verify your new email.')
#                     return redirect('settings')
        
#         context = {
#             'user_profile': user_data,
#             'allow_username_edit': allow_username_edit,
#         }
#         return render(request, 'settings.html', context)
        
#     except Exception as e:
#         print(f"Error in settings: {str(e)}")
#         messages.error(request, 'An error occurred. Please try again later.')
#         return redirect('home')
@login_required
def settings(request):
    try:
        customer = request.user.customer
        allow_username_edit = False  # Set to True if you want to allow direct username edits
        
        if request.method == 'POST':
            # Handle username change request
            if 'request_username' in request.POST:
                new_username = request.POST.get('new_username')
                if new_username:
                    request.user.username = new_username
                    request.user.save()
                    messages.success(request, 'Username updated successfully!')
                    return redirect('settings')
            
            if 'update_profile' in request.POST:
                email = request.POST.get('email')
                if email and email != request.user.email:
                    request.user.email = email
                    request.user.save()
                    # If email changed, you might want to set email_verified to False
                    customer.email_verified = False
                    customer.save()
                    messages.success(request, 'Email updated successfully! Please verify your new email.')
                    return redirect('settings')
        
        context = {
            'allow_username_edit': allow_username_edit,
        }
        return render(request, 'settings.html', context)
        
    except AttributeError:
        messages.error(request, 'Customer profile not found. Please contact support.')
        return redirect('home')



# def update_info(request):
#     try:
#         # Get Firebase UID from session
#         firebase_uid = request.session.get('firebase_uid')
#         if not firebase_uid:
#             messages.error(request, "Authentication issue. Please log out and log in again.")
#             return redirect('home')
        
#         # Get user profile from Firestore
#         user_doc = db.collection('users').document(firebase_uid).get()
        
#         if not user_doc.exists:
#             messages.error(request, "User profile not found. Please contact support.")
#             return redirect('home')
            
#         user_data = user_doc.to_dict()
        
#         if request.method == 'POST':
#             # Extract form data
#             first_name = request.POST.get('first_name', '')
#             last_name = request.POST.get('last_name', '')
#             phone = request.POST.get('phone', '')
#             address = request.POST.get('address', '')
#             city = request.POST.get('city', '')
#             country = request.POST.get('country', '')
            
#             # Prepare updates
#             update_data = {
#                 'first_name': first_name,
#                 'last_name': last_name,
#                 'phone': phone,
#                 'address': address,
#                 'city': city,
#                 'country': country
#             }
            
#             # Handle image upload if provided
#             if request.FILES.get('image'):
#                 import os
#                 from django.conf import settings
                
#                 image = request.FILES.get('image')
                
#                 # Create a unique filename
#                 import time
#                 timestamp = int(time.time())
#                 filename = f"{firebase_uid}_{timestamp}_{image.name}"
                
#                 # Ensure upload directory exists
#                 upload_path = os.path.join(settings.MEDIA_ROOT, 'user_images', firebase_uid)
#                 os.makedirs(upload_path, exist_ok=True)
                
#                 # Save the image
#                 with open(os.path.join(upload_path, filename), 'wb+') as destination:
#                     for chunk in image.chunks():
#                         destination.write(chunk)
                
#                 # Set the image URL for Firestore
#                 image_path = f"/media/user_images/{firebase_uid}/{filename}"
#                 update_data['image_path'] = image_path
            
#             # Update Firebase Auth display name
#             firebase_auth.update_user(
#                 firebase_uid,
#                 display_name=f"{first_name} {last_name}"
#             )
            
#             # Update user profile in Firestore
#             db.collection('users').document(firebase_uid).update(update_data)
            
#             # Update Django user for consistency
#             request.user.first_name = first_name
#             request.user.last_name = last_name
#             request.user.save()
            
#             messages.success(request, 'Profile updated successfully!')
#             return redirect('update_info')
        
#         # For GET requests, pass user data to the template
#         return render(request, 'update_info.html', {'user_profile': user_data})
        
#     except Exception as e:
#         print(f"Error in update_info: {str(e)}")
#         messages.error(request, 'An error occurred while updating your profile. Please try again later.')
#         return redirect('settings')
    
    
@login_required
def update_info(request):
    try:
        customer = request.user.customer
        
        if request.method == 'POST':
            
            
            request.user.first_name = request.POST.get('first_name', '')
            request.user.last_name = request.POST.get('last_name', '')
            request.user.save()
            
            # Update customer profile information
            customer.phone = request.POST.get('phone', '')
            customer.address = request.POST.get('address', '')
            customer.city = request.POST.get('city', '')
            customer.country = request.POST.get('country', '')

            if request.FILES.get('image'):
                customer.image = request.FILES.get('image')
            
            customer.save()
            messages.success(request, 'Profile updated successfully!')
            return redirect('update_info')
        
        return render(request, 'update_info.html')
        
    except AttributeError:
        messages.error(request, 'Customer profile not found. Please contact support.')
        return redirect('settings')


@login_required
def toggle_save_product(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    customer = get_object_or_404(Customer, user=request.user)
    
    if product in customer.saved_products.all():
        # User has already saved this product, so remove it
        customer.saved_products.remove(product)
        is_saved = False
    else:
        # User hasn't saved this product, so save it
        customer.saved_products.add(product)
        is_saved = True
    
    # For AJAX requests
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({
            'is_saved': is_saved,
            'saved_count': product.saved_by_customers.count()
        })
    
    # For regular requests
    return redirect('product', product_id=product_id)




@login_required
def saved_items(request):
    try:
        # Get the customer associated with the current user
        customer = Customer.objects.get(user=request.user)
        
        # Get all products saved by this customer
        saved_products = customer.saved_products.all().order_by('-id')
        
        context = {
            'saved_products': saved_products,
            'saved_count': saved_products.count(),
        }
        
        return render(request, 'saved_items.html', context)
    
    except Customer.DoesNotExist:
        # Handle case where customer doesn't exist
        context = {
            'saved_products': [],
            'saved_count': 0,
        }
        return render(request, 'saved_items.html', context)
    
    
    
def inbox(request):
    inbox_messages = Message.objects.filter(recipient=request.user).order_by('-date_sent')
    
    context = {
        'user': request.user,
        'total_messages': Message.objects.filter(recipient=request.user).count() + Message.objects.filter(sender=request.user).count(),
        'inbox_count': Message.objects.filter(recipient=request.user).count(),
        'sent_count': Message.objects.filter(sender=request.user).count(),
        'messages': inbox_messages,
        'active_tab': 'inbox'
    }
    
    return render(request, 'inbox.html', context)
@login_required
def send_message(request):
    if request.method == 'POST':
        recipient_username = request.POST.get('recipient')
        subject = request.POST.get('subject')
        body = request.POST.get('body')
        
        # Validate inputs
        if not recipient_username or not subject or not body:
            messages.error(request, 'Please fill in all fields.')
            return render(request, 'send_message.html', {
                'recipient': recipient_username,
                'subject': subject,
                'body': body,
            })
            
        # Find recipient user
        try:
            recipient = User.objects.get(username=recipient_username)
        except User.DoesNotExist:
            messages.error(request, f'User "{recipient_username}" does not exist.')
            return render(request, 'send_message.html', {
                'recipient': recipient_username,
                'subject': subject,
                'body': body,
            })
        
        # Create and save message
        new_message = Message(
            sender=request.user,
            recipient=recipient,
            subject=subject,
            content=body
        )
        new_message.save()
        
        messages.success(request, 'Message sent successfully!')
        return redirect('inbox')
    
    # For GET requests, just show the form
    return render(request, 'send_message.html', {
        'inbox_count': Message.objects.filter(recipient=request.user).count(),
        'sent_count': Message.objects.filter(sender=request.user).count(),
    })


@login_required
def view_message(request, message_id):
    try:
        message = Message.objects.get(id=message_id, recipient=request.user)
    except Message.DoesNotExist:
        messages.error(request, 'Message not found.')
        return redirect('inbox')
    
    context = {
        'message': message,
        'inbox_count': Message.objects.filter(recipient=request.user).count(),
        'sent_count': Message.objects.filter(sender=request.user).count(),
        'active_tab': 'inbox'
    }
    
    return render(request, 'view_message.html', context)

@login_required
def reply_message(request, message_id):
    try:
        original_message = Message.objects.get(id=message_id, recipient=request.user)
    except Message.DoesNotExist:
        messages.error(request, 'Message not found.')
        return redirect('inbox')
    
    if request.method == 'POST':
        content = request.POST.get('content')
        
        if not content:
            messages.error(request, 'Reply cannot be empty.')
            return redirect('view_message', message_id=message_id)
        
        # Create a subject with Re: prefix if not already there
        if original_message.subject.startswith('Re:'):
            subject = original_message.subject
        else:
            subject = f'Re: {original_message.subject}'
        
        # Create and save reply
        reply = Message(
            sender=request.user,
            recipient=original_message.sender,  # Reply to the original sender
            subject=subject,
            content=content,
            is_reply=True,
            parent_message=original_message
        )
        reply.save()
        
        messages.success(request, 'Reply sent successfully.')
        return redirect('inbox')
    
    # For GET requests, redirect to view_message
    return redirect('view_message', message_id=message_id)




@login_required
def sent_items(request):
    sent_messages = Message.objects.filter(sender=request.user).order_by('-date_sent')
    
    context = {
        'user': request.user,
        'total_messages': Message.objects.filter(recipient=request.user).count() + Message.objects.filter(sender=request.user).count(),
        'inbox_count': Message.objects.filter(recipient=request.user).count(),
        'sent_count': Message.objects.filter(sender=request.user).count(),
        'messages': sent_messages,
        'active_tab': 'sent',
        'now': timezone.now(),  # Add current time for display logic
    }
    
    return render(request, 'sent_items.html', context)


def delete_messages(request):
    if request.method == 'POST':
        message_ids = request.POST.getlist('message_ids')
        folder = request.POST.get('folder', 'inbox')
        
        if message_ids:
            if folder == 'inbox':
                # Only delete inbox messages that belong to this user
                messages_to_delete = Message.objects.filter(
                    id__in=message_ids,
                    recipient=request.user
                )
            else:  # sent folder
                # Only delete sent messages that belong to this user
                messages_to_delete = Message.objects.filter(
                    id__in=message_ids,
                    sender=request.user
                )
                
            deleted_count = messages_to_delete.delete()[0]
            messages.success(request, f'{deleted_count} message(s) deleted successfully.')
        
        if folder == 'sent':
            return redirect('sent_items')
        else:
            return redirect('inbox')
            
    return redirect('inbox')



# @login_required
# def close_account(request):
#     if request.method == 'POST':
#         user = request.user
#         confirmation = request.POST.get('confirm', '')
        
#         if confirmation != 'DELETE':
#             messages.error(request, "Please type 'DELETE' to confirm account deletion.")
#             return render(request, 'confirm_account_deletion.html')
        
#         try:
#             # Get Firebase UID from session
#             firebase_uid = request.session.get('firebase_uid')
            
#             if not firebase_uid:
#                 # Try to get from FirebaseUser model as fallback
#                 try:
#                     firebase_user = FirebaseUser.objects.get(user=user)
#                     firebase_uid = firebase_user.firebase_uid
#                 except:
#                     messages.error(request, "Could not retrieve your account information. Please contact support.")
#                     return redirect('settings')
            
#             # Delete user's data from Firestore collections
            
#             # 1. Delete user's products
#             products_ref = db.collection('products').where('user_id', '==', firebase_uid).stream()
#             for product in products_ref:
#                 product.reference.delete()
            
#             # 2. Delete user's comments
#             comments_ref = db.collection('comments').where('user_id', '==', firebase_uid).stream()
#             for comment in comments_ref:
#                 comment.reference.delete()
            
#             # 3. Delete user's wishlist items
#             wishlist_ref = db.collection('wishlist').where('user_id', '==', firebase_uid).stream()
#             for item in wishlist_ref:
#                 item.reference.delete()
            
#             # 4. Delete user's notifications
#             notifications_ref = db.collection('notifications').where('user_id', '==', firebase_uid).stream()
#             for notification in notifications_ref:
#                 notification.reference.delete()
            
#             # 5. Delete user's follows/followers
#             followers_ref = db.collection('followers').where('follower_id', '==', firebase_uid).stream()
#             for follower in followers_ref:
#                 follower.reference.delete()
                
#             following_ref = db.collection('followers').where('following_id', '==', firebase_uid).stream()
#             for following in following_ref:
#                 following.reference.delete()
            
#             # 6. Delete user profile from Firestore
#             db.collection('users').document(firebase_uid).delete()
            
#             # 7. Delete user from Firebase Auth
#             firebase_auth.delete_user(firebase_uid)
            
#             # 8. Log the user out and delete Django user
#             logout(request)
#             user.delete()
            
#             messages.success(request, "Your account has been successfully deleted.")
#             return redirect('home')
            
#         except Exception as e:
#             print(f"Error deleting account: {str(e)}")
#             messages.error(request, f"Error deleting account: {str(e)}")
#             return redirect('settings')
#     else:
#         # Display confirmation page for GET requests
#         return render(request, 'confirm_account_deletion.html')
    
    
def close_account(request):
    if request.method == 'POST':
        user = request.user
        confirmation = request.POST.get('confirm', '')
        
        if confirmation != 'DELETE':
            messages.error(request, "Please type 'DELETE' to confirm account deletion.")
            return render(request, 'confirm_account_deletion.html')
            
        if user.is_authenticated:
            try:
                # Get Firebase UID for the user
                firebase_user = FirebaseUser.objects.get(user=user)
                
                # Delete user from Firebase
                firebase_auth.delete_user(firebase_user.firebase_uid)
                
                # Log the user out
                logout(request)
                
                # Delete Django user (will cascade to Customer due to OneToOneField)
                user.delete()
                
                messages.success(request, "Your account has been successfully deleted.")
                return redirect('home')  # Redirect to home page
                
            except FirebaseUser.DoesNotExist:
                # If no Firebase user exists, just delete the Django user
                logout(request)
                user.delete()
                messages.success(request, "Your account has been successfully deleted.")
                return redirect('home')
                
            except Exception as e:
                messages.error(request, f"Error deleting account: {str(e)}")
                return redirect('settings')
        else:
            messages.error(request, "You must be logged in to delete your account.")
            return redirect('login')
    else:
        # Display confirmation page for GET requests
        return render(request, 'confirm_account_deletion.html')
    
    


def hot_deals(request):
    # Get all products that have a sale price
    products = Product.objects.filter(sale_price__isnull=False).select_related('category', 'user', 'customer_pic_id')
    
    # Calculate and filter products with discount >= 70%
    hot_deals = []
    for product in products:
        if product.Price > 0 and product.sale_price is not None:
            discount_percentage = ((product.Price - product.sale_price) / product.Price) * 100
            
            if discount_percentage >= 70:
                # Add discount_percentage as attribute for display
                product.discount_percentage = round(discount_percentage, 2)
                hot_deals.append(product)
    
    # Start with all hot deals
    filtered_deals = hot_deals.copy()
    
    # Get data for filter dropdowns
    all_stores = Product.objects.values_list('store', flat=True).distinct()
    all_cities = Product.objects.values_list('city', flat=True).distinct()
    all_brands = Product.objects.values_list('brand', flat=True).distinct()
    
    context = {
        'products': filtered_deals,
        'stores': all_stores,
        'locations': all_cities,
        'brands': all_brands,
    }
    
    return render(request, 'hot_deals.html', context)

def filter_hot_deals(request):
    # Get all products that have a sale price
    products = Product.objects.filter(sale_price__isnull=False).select_related('category', 'user', 'customer_pic_id')
    
    # Calculate and filter products with discount >= 70%
    hot_deals = []
    for product in products:
        if product.Price > 0 and product.sale_price is not None:
            discount_percentage = ((product.Price - product.sale_price) / product.Price) * 100
            
            if discount_percentage >= 70:
                # Add discount_percentage as attribute for display
                product.discount_percentage = round(discount_percentage, 2)
                hot_deals.append(product)
    
    # Start with all hot deals
    filtered_deals = hot_deals.copy()
    
    # Get filter parameters
    stores = request.GET.get('stores', '')
    locations = request.GET.get('locations', '')
    brands = request.GET.get('brands', '')
    min_price = request.GET.get('min_price', '0')
    max_price = request.GET.get('max_price', '1000')
    ratings = request.GET.get('ratings', '0')
    
    # Apply store filter
    if stores and stores != '':
        store_list = stores.split(',')
        filtered_deals = [deal for deal in filtered_deals 
                          if deal.store in store_list]
    
    # Apply city/location filter
    if locations and locations != '':
        location_list = locations.split(',')
        filtered_deals = [deal for deal in filtered_deals 
                         if deal.city in location_list]
    
    # Apply brand filter
    if brands and brands != '':
        brand_list = brands.split(',')
        filtered_deals = [deal for deal in filtered_deals 
                         if deal.brand in brand_list]
    
    # Apply price range filters
    if min_price:
        min_price_val = float(min_price)
        filtered_deals = [deal for deal in filtered_deals if float(deal.sale_price) >= min_price_val]
    
    if max_price:
        max_price_val = float(max_price)
        filtered_deals = [deal for deal in filtered_deals if float(deal.sale_price) <= max_price_val]
    
    # Apply rating filter (thumbs/likes)
    if ratings and ratings != '0':
        rating_threshold = int(ratings)
        filtered_deals = [deal for deal in filtered_deals if deal.number_of_likes() >= rating_threshold]
    
    # Prepare JSON response
    products_data = []
    for product in filtered_deals:
        # Get customer pic URL if available
        customer_pic_url = None
        if product.customer_pic_id and product.customer_pic_id.image:
            customer_pic_url = product.customer_pic_id.image.url
        
        # Get comment count (adjust if your model has a different way to count comments)
        comment_count = 0  # Replace with actual comment count if available
        
        # Check if the current user has liked this product
        liked_by_user = request.user in product.likes.all() if request.user.is_authenticated else False
        
        products_data.append({
            'id': product.id,
            'name': product.Name,
            'price': str(product.Price),
            'sale_price': str(product.sale_price),
            'description': product.Description,
            'store': product.store,
            'city': product.city,
            'category_name': product.category.name,
            'image_url': product.image.url if product.image else None,
            'username': product.user.username if product.user else "Unknown",
            'create_at': product.create_at.strftime('%d-%m'),
            'customer_pic_url': customer_pic_url,
            'discount_percentage': product.discount_percentage,
            'likes_count': product.number_of_likes(),
            'comment_count': comment_count,
            'liked_by_user': liked_by_user,
        })
    
    return JsonResponse({'products': products_data})


def popular_deals(request):
    """
    Function to display popular deals based on a combination of likes and views.
    """
    # Get all products and annotate them with like count
    products_list = Product.objects.annotate(
        like_count=Count('likes')
    )
    
    # Create a weighted popularity score (likes * 3 + views)
    # but don't display the score to the user
    products_list = products_list.annotate(
        popularity_score=ExpressionWrapper(
            (F('like_count') * 3) + F('views'),  # Likes are weighted 3x more than views
            output_field=FloatField()
        )
    ).order_by('-popularity_score')
    
    # Set up pagination
    paginator = Paginator(products_list, 2)  # Show 12 deals per page
    page = request.GET.get('page')
    
    try:
        popular_products = paginator.page(page)
    except PageNotAnInteger:
        # If page is not an integer, deliver first page
        popular_products = paginator.page(1)
    except EmptyPage:
        # If page is out of range, deliver last page
        popular_products = paginator.page(paginator.num_pages)
    
    context = {
        'popular_deals': popular_products,
        'title': 'Popular Deals'
    }
    
    return render(request, 'popular_deals.html', context)


@login_required
def edit_deal(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    

    if request.method == "POST":
        try:
            product.Name = request.POST.get('Name')
            product.Description = request.POST.get('Description')
            product.Price = request.POST.get('Price')
            product.sale_price = request.POST.get('sale_price')
            product.Dealurl = request.POST.get('Dealurl')
            product.store = request.POST.get('store')
            
            if 'image' in request.FILES:
                product.image = request.FILES['image']

            product.save()
            
            messages.success(request, "Your deal has been updated successfully!")
            return redirect('product', pk=product_id) 
            
        except Exception as e:
            print(f"Error updating deal: {str(e)}")
            messages.error(request, "An error occurred while updating the deal. Please try again.")
            context = {'product': product}
            return render(request, 'edit_deal.html', context)
    
    # Add this part to handle GET requests
    else:
        context = {'product': product}
        return render(request, 'edit_deal.html', context)
        
        
        
@login_required
def delete_deal(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    
    if request.user != product.user:
        messages.error(request, "You don't have permission to delete this deal.")
        return redirect('product', pk=product_id)
    
    try:
        product.delete()
        messages.success(request, f"Your deal '{product.Name}' has been successfully deleted.")
        return redirect('home') 
        
    except Exception as e:
        print(f"Error deleting deal: {str(e)}")
        messages.error(request, "An error occurred while deleting the deal. Please try again.")
        return redirect('product', pk=product_id)
    
    

@login_required
def notifications_view(request):

    notifications = Notification.objects.filter(user=request.user).order_by('-created_at')
    
    # Count unread notifications
    unread_count = notifications.filter(is_read=False).count()
    
    context = {
        'notifications': notifications,
        'unread_count': unread_count,
    }
    
    return render(request, 'notifications.html', context)

@login_required
def mark_notification_read(request, notification_id):
    try:
        notification = Notification.objects.get(id=notification_id, user=request.user)
        notification.is_read = True
        notification.save()
        return JsonResponse({'status': 'success'})
    except Notification.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Notification not found'}, status=404)

@login_required
def mark_all_read(request):
    Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
    return JsonResponse({'status': 'success'})

@login_required
def delete_notification(request, notification_id):
    try:
        notification = Notification.objects.get(id=notification_id, user=request.user)
        notification.delete()
        return JsonResponse({'status': 'success'})
    except Notification.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Notification not found'}, status=404)

# Ajax endpoint to get the unread notification count
@login_required
def get_notification_count(request):
    count = Notification.objects.filter(user=request.user, is_read=False).count()
    return JsonResponse({'count': count})



