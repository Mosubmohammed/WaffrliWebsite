import datetime
from decimal import Decimal, InvalidOperation
from urllib import request
from django.db import IntegrityError
from django.shortcuts import get_object_or_404, redirect, render
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.http import JsonResponse
from django.db.models import Q
import firebase_admin
from waffrli.filters import ProductFilter
from .models import *
from django.contrib.auth.decorators import login_required
from django.db.models import Count, F, ExpressionWrapper, FloatField,Sum
from django.contrib.auth.models import User
from firebase_admin import auth as firebase_auth
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from .utils import *
from waffrliApp.settings import db
from django.utils import timezone
from datetime import datetime
from django.db.models import F, Q, Count, Case, When, FloatField, ExpressionWrapper


def home(request):

    products = Product.objects.filter(is_archived=False).order_by('-create_at')

    current_time = timezone.now()
    for product in products:
        product.is_expired = product.expires_at <= current_time if product.expires_at else False
    
    return render(request, 'home.html', {'products': products})



def product_list(request, page_type=None, category=None):
    # Build base queryset according to page type
    products = get_base_queryset(request, page_type, category)
    
    # Apply filters
    filter_set = ProductFilter(request.GET, queryset=products, request=request)
    filtered_products = filter_set.qs
    
    # Handle distance-based sorting if user has location
    user_location = get_user_location(request)
    if request.GET.get('sort_by') == 'distance' and user_location['has_location']:
        filtered_products = sort_by_distance(
            filtered_products, 
            user_location['lat'], 
            user_location['lng']
        )
    
    # Handle AJAX/JSON requests
    if is_ajax_request(request):
        return JsonResponse({
            'products': format_products_for_json(filtered_products, request, user_location)
        })
    
    # Handle pagination
    page_obj = paginate_products(request, filtered_products)
    
    # Calculate distances for products in current page if user has location
    if user_location['has_location']:
        add_distances_to_products(page_obj, user_location['lat'], user_location['lng'])
    
    # Get filter options (unique stores, cities, brands)
    filter_options = get_filter_options(filtered_products)
    
    # Prepare context
    context = {
        'products': page_obj,
        'page_obj': page_obj,
        'stores': filter_options['stores'],
        'locations': filter_options['cities'],
        'jordan_cities': filter_options['jordan_cities'],
        'brands': filter_options['brands'],
        'store_types': [('online', 'Online Store'), ('physical', 'Physical Store')],
        'selected_stores': request.GET.getlist('store'),
        'selected_locations': request.GET.getlist('location'),
        'selected_brands': request.GET.getlist('brand'),
        'selected_store_type': request.GET.get('store_type', ''),
        'min_price': request.GET.get('min_price'),
        'max_price': request.GET.get('max_price'),
        'rating': request.GET.get('rating'),
        'page_title': get_page_title(request, page_type, category),
        'page_type': page_type,
        'category': category,
        'sort_by': request.GET.get('sort_by', ''),
        'user_has_location': user_location['has_location'],
        'include_expired': request.GET.get('include_expired') == 'true',
    }
    
    # Choose the appropriate template
    template = get_template_for_page(page_type, category)
    
    return render(request, template, context)

def get_base_queryset(request, page_type, category):
    """Get the base queryset according to page type and category."""
    if page_type == 'hot_deals' and not any([
        request.GET.getlist('store'), 
        request.GET.getlist('location'), 
        request.GET.getlist('brand')
    ]):
        # Hot deals with no filters - apply 70% discount requirement
        # We can use the model's is_hot_deal method to filter products with >=70% discount
        hot_deals = Product.objects.filter(
            sale_price__isnull=False,
            Price__gt=0
        ).exclude(
            sale_price__gte=F('Price')
        ).annotate(
            discount_percentage=ExpressionWrapper(
                ((F('Price') - F('sale_price')) * 100) / F('Price'),
                output_field=FloatField()
            )
        ).filter(discount_percentage__gte=70).select_related('category', 'user', 'customer_pic_id')
        
        return hot_deals
    
    elif page_type == 'hot_deals':
        # Hot deals with filters - basic criteria without 70% requirement
        return Product.objects.filter(
            sale_price__isnull=False,
            Price__gt=0
        ).exclude(
            sale_price__gte=F('Price')
        ).annotate(
            discount_percentage=ExpressionWrapper(
                ((F('Price') - F('sale_price')) * 100) / F('Price'),
                output_field=FloatField()
            )
        ).select_related('category', 'user', 'customer_pic_id')
    
    elif page_type == 'popular':
        # Popular deals based on likes and views
        return Product.objects.annotate(
            like_count=Count('likes'),
            popularity_score=ExpressionWrapper(
                (F('like_count') * 3) + F('views'),
                output_field=FloatField()
            )
        ).order_by('-popularity_score').select_related('category', 'user', 'customer_pic_id')
    
    elif category:
        # Category filter
        category_obj = get_object_or_404(Category, name__iexact=category.replace('-', ' ').strip())
        return Product.objects.filter(category=category_obj).select_related('category', 'user', 'customer_pic_id')
    
    else:
        # All products
        return Product.objects.all().select_related('category', 'user', 'customer_pic_id')

def get_user_location(request):
    """Extract user location data if available."""
    result = {'has_location': False, 'lat': None, 'lng': None}
    
    if request.user.is_authenticated:
        try:
            customer = request.user.customer
            if customer.latitude is not None and customer.longitude is not None:
                result['has_location'] = True
                result['lat'] = customer.latitude
                result['lng'] = customer.longitude
        except (AttributeError, Customer.DoesNotExist):
            pass
    
    return result

def sort_by_distance(queryset, user_lat, user_lng):
    """Sort products by distance to user."""
    products_list = list(queryset)
    
    # Calculate distances
    for product in products_list:
        if product.latitude is not None and product.longitude is not None:
            product.distance_to = product.distance_to(user_lat, user_lng)
        else:
            product.distance_to = float('inf')
    
    # Sort by distance
    products_list.sort(key=lambda x: x.distance_to if isinstance(x.distance_to, (int, float)) else float('inf'))
    
    # Convert back to a Django queryset with preserved order
    product_ids = [p.id for p in products_list]
    
    if product_ids:
        preserved_order = Case(*[When(pk=pk, then=pos) for pos, pk in enumerate(product_ids)])
        return queryset.filter(id__in=product_ids).order_by(preserved_order)
    
    return queryset

def is_ajax_request(request):
    """Determine if this is an AJAX/JSON request."""
    return request.headers.get('X-Requested-With') == 'XMLHttpRequest' or 'json' in request.GET

def format_products_for_json(products, request, user_location):
    """Format products for JSON response (without using serializers)."""
    products_data = []
    
    for product in products:
        # Get customer pic URL if available
        customer_pic_url = None
        if product.customer_pic_id and product.customer_pic_id.image:
            customer_pic_url = product.customer_pic_id.image.url
        
        # Use the model's get_discount_percentage method
        discount_percentage = getattr(product, 'discount_percentage', None)
        if discount_percentage is None:
            discount_percentage = product.get_discount_percentage()
        
        # Check if liked by current user
        liked_by_user = request.user in product.likes.all() if request.user.is_authenticated else False
        
        # Calculate distance using the model's distance_to method
        distance = None
        if user_location['has_location'] and product.latitude and product.longitude:
            distance = product.distance_to(user_location['lat'], user_location['lng'])
        
        # Use the model's get_savings_amount method for savings
        savings = product.get_savings_amount()
        
        # Check if product is expired
        is_expired = product.is_expired()
        
        products_data.append({
            'id': product.id,
            'name': product.Name,
            'price': str(product.Price),
            'sale_price': str(product.sale_price) if product.sale_price else None,
            'description': product.Description,
            'store': product.store,
            'store_type': product.store_type,
            'city': product.city,
            'brand': product.brand,
            'category_name': product.category.name,
            'image_url': product.image.url if product.image else None,
            'username': product.user.username if product.user else "Unknown",
            'create_at': product.create_at.strftime('%d-%m'),
            'customer_pic_url': customer_pic_url,
            'discount_percentage': round(discount_percentage, 2) if discount_percentage else 0,
            'savings_amount': savings,
            'likes_count': product.number_of_likes(),
            'liked_by_user': liked_by_user,
            'distance': distance,
            'is_expired': is_expired,
            'is_archived': product.is_archived,
            'is_hot_deal': product.is_hot_deal(),
            'dealurl': product.Dealurl,
        })
    
    return products_data
# Updated pagination function to ensure ordering
def paginate_products(request, products):
    """Handle pagination logic with consistent ordering."""
    # Ensure products have a consistent ordering if not already ordered
    if not products.query.order_by:
        products = products.order_by('-create_at')  # Default ordering from your model
    
    # Check if filters are applied
    filters_applied = any([
        request.GET.getlist('store'),
        request.GET.getlist('location'),
        request.GET.getlist('brand'),
        request.GET.get('min_price'),
        request.GET.get('max_price'),
        request.GET.get('rating'),
        request.GET.get('store_type'),
        request.GET.get('include_expired'),
    ])
    
    if filters_applied:
        # Use larger per-page count for filtered results
        paginator = Paginator(products, 1000)
        try:
            return paginator.page(1)
        except EmptyPage:
            return paginator.page(paginator.num_pages)
    else:
        # Normal pagination for unfiltered results
        paginator = Paginator(products, 20)
        page_number = request.GET.get('page')
        
        try:
            return paginator.page(page_number)
        except PageNotAnInteger:
            return paginator.page(1)
        except EmptyPage:
            return paginator.page(paginator.num_pages)

def add_distances_to_products(products, user_lat, user_lng):
    """Add distance attribute to each product in the collection."""
    for product in products:
        if product.latitude and product.longitude:
            product.distance_to = product.distance_to(user_lat, user_lng)
        else:
            product.distance_to = None

def get_filter_options(products):
    """Get unique values for filter dropdowns."""
    # Get unique store names (case-insensitive)
    store_values = products.values_list('store', flat=True)
    stores_list = sorted(set(store.strip().lower() for store in store_values if store), key=lambda x: x.lower())
    
    # Get unique city names (case-insensitive)
    city_values = products.values_list('city', flat=True)
    cities_list = sorted(set(city.strip().lower() for city in city_values if city), key=lambda x: x.lower())
    
    # Get unique brand names (case-insensitive)
    brand_values = products.values_list('brand', flat=True)
    brands_list = sorted(set(brand.strip().lower() for brand in brand_values if brand), key=lambda x: x.lower())
    
    # Define list of main Jordan cities
    jordan_cities = [
        'Amman', 'Zarqa', 'Irbid', 'Aqaba', 'Salt', 'Madaba', 'Jerash',
        'Ajloun', 'Mafraq', 'Tafilah', 'Karak', 'Ma\'an', 'Ramtha', 'Sahab', 
        'Russeifa', 'Al-Quwaysimah', 'Wadi as-Ser', 'Tila al-Ali', 'Baqa\'a',
        'Zarqa Camp', 'Suwaylih', 'Um al-Jimal', 'Petra', 'Azraq'
    ]
    
    # Add any cities from database not in predefined list
    for city in cities_list:
        if city and city.capitalize() not in jordan_cities:
            jordan_cities.append(city.capitalize())
    
    # Sort the cities alphabetically
    jordan_cities.sort()
    
    return {
        'stores': stores_list,
        'cities': cities_list,
        'brands': brands_list,
        'jordan_cities': jordan_cities
    }

def get_page_title(request, page_type, category):
    """Get the appropriate page title."""
    if page_type == 'hot_deals':
        if any([request.GET.getlist('store'), request.GET.getlist('location'), request.GET.getlist('brand')]):
            return "Hot Deals (Filtered)"
        return "Hot Deals"
    elif page_type == 'popular':
        return "Popular Deals"
    elif category:
        category_obj = get_object_or_404(Category, name__iexact=category.replace('-', ' ').strip())
        return f"{category_obj.name} Deals"
    else:
        return "All Deals"

def get_template_for_page(page_type, category):
    """Get the appropriate template for the page."""
    if page_type == 'hot_deals':
        return 'hot_deals.html'
    elif page_type == 'popular':
        return 'popular_deals.html'
    elif category:
        return 'category.html'
    else:
        return 'products.html'



    
    
    
def AllCategory(request):
    categories = Category.objects.all()
    return render(request, 'AllCategory.html', {})




def product(request, pk):
    try:
        # Get the product
        product = get_object_or_404(Product, id=pk)
        
        # Increment views
        product.increment_views()
        
        # Get related products right away (so it's always defined)
        related_products = Product.objects.filter(
            category=product.category
        ).exclude(
            id=product.id
        ).order_by(
            '-create_at'  # Sort by newest first
        )[:6]  # Limit to 6 products
        
        # Calculate discount percentage for product
        if product.Price and product.sale_price:
            product.discount_percentage = product.get_discount_percentage()
        else:
            product.discount_percentage = 0
        
        # Calculate discount for related products
        for related_product in related_products:
            if related_product.Price and related_product.sale_price:
                related_product.discount_percentage = related_product.get_discount_percentage()
            else:
                related_product.discount_percentage = 0
            
            # Add a flag for popular products
            related_product.is_popular = related_product.views > 100 or related_product.likes.count() > 10
            
            # Add time ago for display
            related_product.time_ago = related_product.create_at
        
        # Get the user's following status if logged in
        is_following = False
        if request.user.is_authenticated and request.user != product.user:
            # Assuming you have a following relationship model
            # is_following = Following.objects.filter(follower=request.user, followed=product.user).exists()
            pass
        
        # Count deals by this user
        deal_count = Product.objects.filter(user=product.user).count()
        
        # Handle POST request for comment submission
        if request.method == 'POST':
            comment_text = request.POST.get('comment')
            
            if not request.user.is_authenticated:
                messages.warning(request, 'Please log in to comment.')
            elif not comment_text or comment_text.strip() == '':
                messages.warning(request, 'Please write a comment before posting.')
            else:
                try:
                    # Get the current logged-in user's customer
                    customer = Customer.objects.get(user=request.user)
                    
                    # Create and save the comment
                    Comment.objects.create(
                        product=product,
                        customer=customer,
                        text=comment_text
                    )
                    messages.success(request, 'Your comment has been posted successfully!')
                    
                    # Redirect after POST to prevent duplicate submissions
                    return redirect('product', pk=pk)
                    
                except Customer.DoesNotExist:
                    messages.error(request, 'Your user profile is missing. Please contact support.')
        
        # Retrieve all comments for this product
        comments = Comment.objects.filter(product=product).order_by('-timestamp')
        
        # Create context with all necessary data
        context = {
            'product': product,
            'comments': comments,
            'related_products': related_products,
            'is_following': is_following,
            'deal_count': deal_count,
            'user': request.user,
        }
        
        # Debug image URLs
        print(f"Product image URL: {product.image.url if product.image else 'No image'}")
        
        return render(request, 'product.html', context)
        
    except Product.DoesNotExist:
        messages.error(request, 'That product does not exist.')
        return redirect('home')



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
        
        # Get location data from form
        latitude = request.POST.get('latitude')
        longitude = request.POST.get('longitude')
        formatted_address = request.POST.get('formatted_address')
        
        # Generate username from email (or use a field in your form for username)
        username = first_name
        
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
            
            # Create Customer profile with location data
            customer = Customer.objects.create(
                user=django_user,
                first_name=first_name,
                last_name=last_name,
                phone=phone,
                email=email,
                password=password,
                gender=gender,
                # Add location data
                latitude=float(latitude) if latitude else None,
                longitude=float(longitude) if longitude else None,
                formatted_address=formatted_address,
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
            
            # Update Customer model password
            try:
                customer = Customer.objects.get(user=user)
                customer.password = new_password  # Note: This stores plaintext password which is not recommended
                customer.save()
            except Customer.DoesNotExist:
                messages.warning(request, "User found but customer profile not found.")
            
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

        result_count = results.count()  # Count the number of results

        if not results:
            messages.error(request, "No matching products found.")
            return render(request, "home.html")

        return render(request, "search.html", {
            'searched': results,
            'search_term': searched,  # Pass the search term
            'result_count': result_count  # Pass the result count
        })

    return render(request, "home.html")

    
def post_deal(request):
    """View to handle posting new deals and archiving deals"""
    if not request.user.is_authenticated:
        messages.error(request, "You must be logged in to post a deal.")
        return redirect('login')
    
    # For GET requests - just display the form
    if request.method != "POST":
        categories = Category.objects.all()
        return render(request, "post_deal.html", {'categories': categories})
    
    # Get the action type (post or archive)
    action = request.POST.get('action', 'post')
    
    # Fetch common form data for both actions
    name = request.POST.get('deal-title', '')
    url = request.POST.get('deal-url', '')
    sale_price = request.POST.get('sale-price', '')
    price = request.POST.get('list-price', '')
    description = request.POST.get('description', '')
    store = request.POST.get('store', '')
    brand = request.POST.get('brand', '')
    category_id = request.POST.get('category', '')
    location = request.POST.get('location', '')
    store_type = request.POST.get('store-type', 'online')
    pic = request.FILES.get('image')
    
    # Handle expiration date
    expiration_type = request.POST.get('expiration-type', 'default')
    
    if expiration_type == 'custom':
        # Get the custom expiration date from the form
        expiration_date_str = request.POST.get('expiration-date')
        try:
            # Parse the date string to a datetime object
            expiration_date = datetime.strptime(expiration_date_str, '%Y-%m-%d')
            # Set time to end of day (23:59:59)
            expiration_date = expiration_date.replace(hour=23, minute=59, second=59)
            # Convert to timezone-aware datetime if using timezone
            expiration_date = timezone.make_aware(expiration_date)
            
            # Validate expiration date
            if expiration_date <= timezone.now():
                if action == 'post':
                    messages.error(request, "Expiration date must be in the future.")
                    return redirect('post_deal')
                else:
                    # For archived deals, use default
                    expiration_date = timezone.now() + timezone.timedelta(days=10)
        except (ValueError, TypeError):
            # If date parsing fails, fall back to default
            expiration_date = timezone.now() + timezone.timedelta(days=10)
    else:
        # Use default expiration (10 days)
        expiration_date = timezone.now() + timezone.timedelta(days=10)
    
    # Handle location data for physical stores
    latitude = None
    longitude = None
    formatted_address = None
    if store_type == 'physical':
        latitude_str = request.POST.get('latitude')
        longitude_str = request.POST.get('longitude')
        formatted_address = request.POST.get('formatted_address')
        
        if latitude_str and longitude_str:
            try:
                latitude = float(latitude_str)
                longitude = float(longitude_str)
            except (ValueError, TypeError):
                if action == 'post':
                    messages.error(request, "Invalid location coordinates.")
                    return redirect('post_deal')
        
        # For non-archived deals, require location data for physical stores
        if action == 'post' and not (latitude_str and longitude_str and formatted_address):
            messages.error(request, "Please specify the store location on the map.")
            return redirect('post_deal')
    
    # For non-archived deals, require image
    if action == 'post' and not pic:
        messages.error(request, "Please upload an image.")
        return redirect('post_deal')
    
    # Get category (use default if not provided)
    try:
        category = Category.objects.get(id=int(category_id)) if category_id else Category.objects.first()
    except (Category.DoesNotExist, ValueError):
        if action == 'post':
            messages.error(request, "Invalid category selection.")
            return redirect('post_deal')
        category = Category.objects.first()  # Default category for archived deals
    
    # Convert price fields to Decimal safely
    try:
        sale_price_decimal = Decimal(sale_price) if sale_price else Decimal("0.00")
        price_decimal = Decimal(price) if price else Decimal("0.00")
    except (ValueError, InvalidOperation):
        if action == 'post':
            messages.error(request, "Invalid price format.")
            return redirect('post_deal')
        else:
            sale_price_decimal = Decimal("0.00")
            price_decimal = Decimal("0.00")
    
    # Validate required fields for non-archived deals
    if action == 'post' and not (name and store and category_id and location):
        messages.error(request, "Please fill in all required fields.")
        return redirect('post_deal')
    
    # Handle URL field - with special case for empty URLs in archived deals
    final_url = url.strip()  # Remove any whitespace
    
    if not final_url:
        if action == 'post':
            # Require URL for posting
            messages.error(request, "Please provide a deal URL.")
            return redirect('post_deal')
        else:
            # For archived deals with empty URL, generate a unique identifier
            # This avoids the unique constraint error
            timestamp = timezone.now().strftime('%Y%m%d%H%M%S')
            final_url = f"archived_empty_{timestamp}_{request.user.id}"
    elif Product.objects.filter(Dealurl=final_url).exists():
        if action == 'post':
            # For posting, show error if URL exists
            messages.error(request, "A product with this URL already exists. Please use a different URL.")
            return redirect('post_deal')
        else:
            # For archiving, modify URL to make it unique
            timestamp = timezone.now().strftime('%Y%m%d%H%M%S')
            final_url = f"{final_url}{'&' if '?' in final_url else '?'}archived={timestamp}"
    
    # Create deal with appropriate archived status
    try:
        deal = Product.objects.create(
            user=request.user,
            Dealurl=final_url,
            Name=name or ("Draft Deal" if action == 'archive' else name),
            sale_price=sale_price_decimal,
            Price=price_decimal,
            Description=description or "",
            store=store or "",
            brand=brand or "",
            image=pic,
            category=category,
            city=location or "",
            expires_at=expiration_date,
            store_type=store_type,
            latitude=latitude,
            longitude=longitude,
            formatted_address=formatted_address,
            is_archived=(action == 'archive'),
        )
        
        # For non-archived deals, check wishlist matches
        if action == 'post':
            check_deal_against_wishlist(deal)
            messages.success(request, "Deal posted successfully!")
            return redirect('product', pk=deal.id)
        else:
            messages.success(request, "Deal archived successfully!")
            return redirect('archived_deals')
            
    except IntegrityError as e:
        # In case we somehow still have an integrity error
        error_message = str(e)
        if 'Dealurl' in error_message:
            messages.error(request, "A product with this URL already exists. Please use a different URL.")
        else:
            messages.error(request, f"An error occurred while saving the deal: {error_message}")
        return redirect('post_deal')





@login_required 
def like_product(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    user = request.user

    if user.is_authenticated:
    # Toggle like status
        if user in product.likes.all():
            product.likes.remove(user)
            liked = False
        else:
            product.likes.add(user)
            liked = True
        
        # Handle AJAX requests
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'liked': liked,
                'likes_count': product.likes.count()
            })
        
        # For non-AJAX requests, redirect back to the referring page
        return redirect(request.META.get('HTTP_REFERER', 'home'))

        
def user_profile(request, identifier):
    # Try to see if identifier is numeric (an ID)
    try:
        user_id = int(identifier)
        profile_user = get_object_or_404(User, id=user_id)
    except ValueError:
        # If not numeric, treat as username
        profile_user = get_object_or_404(User, username=identifier)
    
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
    return redirect('user_profile', identifier=user_id)

@login_required
def unfollow(request, user_id):
    user_to_unfollow = get_object_or_404(User, id=user_id)
    Follow.objects.filter(follower=request.user, following=user_to_unfollow).delete()
    return redirect('user_profile', identifier=user_id)

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
                    # Check if username already exists
                    if User.objects.filter(username=new_username).exists():
                        messages.error(request, "Username already exists. Please choose another one.")
                        return redirect('settings')
                    
                    request.user.username = new_username
                    request.user.save()
                    messages.success(request, 'Username updated successfully!')
                    return redirect('settings')
            
            # Handle the main form with Save Changes button
            if 'update_profile' in request.POST:
                email = request.POST.get('email')
                
                # Check if email has changed
                if email and email != request.user.email:
                    # Check if email already exists for another user
                    if User.objects.filter(email=email).exclude(id=request.user.id).exists():
                        messages.error(request, "Email already in use by another account.")
                        return redirect('settings')
                    
                    # Store old email for reference
                    old_email = request.user.email
                    
                    try:
                        # Update Django User model
                        request.user.email = email
                        request.user.save()
                        
                        # Update Customer model
                        customer.email = email
                        customer.save()
                        
                        # Update Firebase
                        try:
                            firebase_user = FirebaseUser.objects.get(user=request.user)
                            
                            import firebase_admin
                            from firebase_admin import auth
                            
                            # Update Firebase email
                            auth.update_user(
                                firebase_user.firebase_uid,
                                email=email
                            )
                            
                            messages.success(request, 'Email updated successfully!')
                        
                        except FirebaseUser.DoesNotExist:
                            messages.warning(request, "Email updated in our system but not in authentication system. Please contact support.")
                        
                    except Exception as e:
                        # Revert changes if something went wrong
                        request.user.email = old_email
                        request.user.save()
                        if hasattr(customer, 'email'):
                            customer.email = old_email
                            customer.save()
                        messages.error(request, f"Failed to update email: {str(e)}")
                
                messages.success(request, 'Settings updated successfully!')
                return redirect('settings')
        
        context = {
            'allow_username_edit': allow_username_edit,
        }
        return render(request, 'settings.html', context)
    
    except Exception as e:
        messages.error(request, f"An error occurred: {str(e)}")
        return redirect('home')


    
    
@login_required
def update_info(request):
    try:
        customer = request.user.customer
        
        if request.method == 'POST':
            # Get updated information
            first_name = request.POST.get('first_name', '')
            last_name = request.POST.get('last_name', '')
            
            # Update user information in Django User model
            request.user.first_name = first_name
            request.user.last_name = last_name
            request.user.save()
            
            # Update customer profile information including first_name and last_name
            customer.first_name = first_name
            customer.last_name = last_name
            customer.phone = request.POST.get('phone', '')
            
            # Get location data from form
            latitude = request.POST.get('latitude')
            longitude = request.POST.get('longitude')
            formatted_address = request.POST.get('formatted_address')
            
            # Update location data if provided
            if latitude and longitude:
                customer.latitude = float(latitude)
                customer.longitude = float(longitude)
            
            if formatted_address:
                customer.formatted_address = formatted_address
            
            # Update profile image if provided
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
def send_message(request, user_id=None):
    recipient = None
    recipient_username = ""
    
    # Try to get recipient if user_id is provided
    if user_id:
        try:
            recipient = User.objects.get(id=user_id)
            recipient_username = recipient.username
        except User.DoesNotExist:
            messages.error(request, 'User does not exist.')
            return redirect('inbox')
    
    if request.method == 'POST':
        # Get form data
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
                'inbox_count': Message.objects.filter(recipient=request.user).count(),
                'sent_count': Message.objects.filter(sender=request.user).count(),
            })
        
        # Find recipient user (even if we already got it from URL, to validate the form input)
        try:
            recipient = User.objects.get(username=recipient_username)
        except User.DoesNotExist:
            messages.error(request, f'User "{recipient_username}" does not exist.')
            return render(request, 'send_message.html', {
                'recipient': recipient_username,
                'subject': subject,
                'body': body,
                'inbox_count': Message.objects.filter(recipient=request.user).count(),
                'sent_count': Message.objects.filter(sender=request.user).count(),
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
    
    # For GET requests, show the form with pre-filled recipient if available
    return render(request, 'send_message.html', {
        'recipient': recipient_username,
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
    
    


# def hot_deals(request):
#     return product_list_base(request, page_type='hot_deals')

# def filter_hot_deals(request):
#     return product_list_base(request, page_type='hot_deals')


# def popular_deals(request):
#     return product_list_base(request, page_type='popular')


@login_required
def edit_deal(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    
    # Check if the user is the owner of the deal
    if product.user != request.user:
        messages.error(request, "You do not have permission to edit this deal.")
        return redirect('product', pk=product_id)
    
    if request.method == "POST":
        try:
            # Basic information
            product.Name = request.POST.get('Name')
            product.Description = request.POST.get('Description')
            product.Price = request.POST.get('Price')
            product.sale_price = request.POST.get('sale_price')
            product.Dealurl = request.POST.get('Dealurl')
            product.store = request.POST.get('store')
            product.brand = request.POST.get('brand')
            
            # Handle store type and location
            store_type = request.POST.get('store_type')
            if store_type:
                product.store_type = store_type
                
                # If it's a physical store, update location information
                if store_type == 'physical':
                    product.city = request.POST.get('location')
                    
                    # Get location coordinates
                    latitude_str = request.POST.get('latitude')
                    longitude_str = request.POST.get('longitude')
                    formatted_address = request.POST.get('formatted_address')
                    
                    # Validate location data for physical stores
                    if latitude_str and longitude_str:
                        try:
                            product.latitude = float(latitude_str)
                            product.longitude = float(longitude_str)
                            product.formatted_address = formatted_address
                        except (ValueError, TypeError):
                            messages.warning(request, "Invalid location coordinates. Location not updated.")
                else:
                    # For online stores, clear location data
                    product.city = request.POST.get('location')  # Still keep the city/location
                    product.latitude = None
                    product.longitude = None
                    product.formatted_address = None
            
            # Handle expiration date
            expiration_type = request.POST.get('expiration_type', 'default')
            expiration_date_str = request.POST.get('expiration_date')
            
            if expiration_type == 'custom' and expiration_date_str:
                try:
                    # Parse the date from the string (format: YYYY-MM-DD)
                    expiration_date = timezone.make_aware(datetime.strptime(expiration_date_str, '%Y-%m-%d'))
                    
                    # Validate that the expiration date is in the future
                    if expiration_date <= timezone.now():
                        messages.warning(request, "Expiration date must be in the future. Using default (10 days).")
                        expiration_date = timezone.now() + timezone.timedelta(days=10)
                    
                    # Validate that the expiration date is not more than 30 days in the future
                    max_date = timezone.now() + timezone.timedelta(days=30)
                    if expiration_date > max_date:
                        messages.warning(request, "Expiration date cannot be more than 30 days. Set to maximum allowed.")
                        expiration_date = max_date
                        
                    product.expires_at = expiration_date
                except ValueError:
                    messages.warning(request, "Invalid date format. Expiration date not updated.")
            elif expiration_type == 'default':
                # Default: 10 days from now
                product.expires_at = timezone.now() + timezone.timedelta(days=10)
            
            # Handle image upload
            if 'image' in request.FILES:
                product.image = request.FILES['image']
            
            # Save the updated product
            product.save()
            
            messages.success(request, "Your deal has been updated successfully!")
            return redirect('product', pk=product_id)
            
        except Exception as e:
            print(f"Error updating deal: {str(e)}")
            messages.error(request, "An error occurred while updating the deal. Please try again.")
    
    # For GET requests, calculate the discount percentage for display
    discount_percentage = product.get_discount_percentage()
    
    # Calculate min and max dates for the date picker
    today = timezone.now().date()
    max_date = today + timezone.timedelta(days=30)
    
    context = {
        'product': product,
        'discount_percentage': discount_percentage,
        'min_date': today,
        'max_date': max_date,
    }
    
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


def archived_deals(request):
    if not request.user.is_authenticated:
        messages.error(request, "You must be logged in to view archived deals.")
        return redirect('login')
    
    archived_deals = Product.objects.filter(
        user=request.user,
        is_archived=True
    )
    
    return render(request, 'archived_deals.html', {'archived_deals': archived_deals})

def continue_archived_deal(request, deal_id):
    """View to continue editing an archived deal"""
    if not request.user.is_authenticated:
        messages.error(request, "You must be logged in to edit deals.")
        return redirect('login')
    
    try:
        deal = Product.objects.get(id=deal_id, user=request.user, is_archived=True)
    except Product.DoesNotExist:
        messages.error(request, "Archived deal not found.")
        return redirect('archived_deals')
    
    # For GET requests - just display the form
    if request.method != "POST":
        categories = Category.objects.all()
        return render(request, "post_deal.html", {
            'categories': categories,
            'deal': deal,
            'edit_mode': True
        })
    
    # Handle form submission (POST request)
    # Check if this is an archive action or a publish action
    action = request.POST.get('action', 'post')
    
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
    store_type = request.POST.get('store-type', 'online')
    
    # Handle expiration date
    expiration_type = request.POST.get('expiration-type', 'default')
    
    if expiration_type == 'custom':
        # Get the custom expiration date from the form
        expiration_date_str = request.POST.get('expiration-date')
        try:
            # Parse the date string to a datetime object
            expiration_date = datetime.strptime(expiration_date_str, '%Y-%m-%d')
            # Set time to end of day (23:59:59)
            expiration_date = expiration_date.replace(hour=23, minute=59, second=59)
            # Convert to timezone-aware datetime if using timezone
            expiration_date = timezone.make_aware(expiration_date)
            
            # If date is in the past and we're publishing, show error
            if action == 'post' and expiration_date <= timezone.now():
                messages.error(request, "Expiration date must be in the future.")
                return redirect('continue_archived_deal', deal_id=deal.id)
        except (ValueError, TypeError):
            # If date parsing fails, fall back to default
            expiration_date = timezone.now() + timezone.timedelta(days=10)
    else:
        # Use default expiration (10 days)
        expiration_date = timezone.now() + timezone.timedelta(days=10)
    
    # Get location data (only for physical stores)
    latitude = None
    longitude = None
    formatted_address = None
    if store_type == 'physical':
        latitude_str = request.POST.get('latitude')
        longitude_str = request.POST.get('longitude')
        formatted_address = request.POST.get('formatted_address')
        
        if latitude_str and longitude_str:
            try:
                latitude = float(latitude_str)
                longitude = float(longitude_str)
            except (ValueError, TypeError):
                if action == 'post':
                    messages.error(request, "Invalid location coordinates.")
                    return redirect('continue_archived_deal', deal_id=deal.id)
    
    # Handle image - keep existing if no new one provided
    pic = request.FILES.get('image') or deal.image
    
    # Validate required fields if publishing
    if action == 'post':
        if not name or not store or not category_id or not location:
            messages.error(request, "Please fill in all required fields.")
            return redirect('continue_archived_deal', deal_id=deal.id)
        
        # Convert price fields to Decimal safely
        try:
            sale_price_decimal = Decimal(sale_price) if sale_price else Decimal("0.00")
            price_decimal = Decimal(price) if price else Decimal("0.00")
        except (ValueError, InvalidOperation):
            messages.error(request, "Invalid price format.")
            return redirect('continue_archived_deal', deal_id=deal.id)
    else:
        # For archiving, use default values if fields are empty
        try:
            sale_price_decimal = Decimal(sale_price) if sale_price else Decimal("0.00")
            price_decimal = Decimal(price) if price else Decimal("0.00")
        except (ValueError, InvalidOperation):
            sale_price_decimal = Decimal("0.00")
            price_decimal = Decimal("0.00")
    
    # Get category
    try:
        category = Category.objects.get(id=int(category_id)) if category_id else deal.category
    except (Category.DoesNotExist, ValueError):
        if action == 'post':
            messages.error(request, "Invalid category selected.")
            return redirect('continue_archived_deal', deal_id=deal.id)
        category = deal.category
    
    original_url = deal.Dealurl
    if url and url != original_url:
        if Product.objects.filter(Dealurl=url).exclude(id=deal.id).exists():
            messages.error(request, "This URL is already in use by another deal. Please enter a different URL.")
            return redirect('continue_archived_deal', deal_id=deal.id)
    

    deal.Dealurl = url or original_url
    deal.Name = name or "Draft Deal"
    deal.sale_price = sale_price_decimal
    deal.Price = price_decimal
    deal.Description = description or ""
    deal.store = store or ""
    deal.brand = brand or ""
    deal.image = pic
    deal.category = category
    deal.city = location or ""
    deal.expires_at = expiration_date
    deal.store_type = store_type
    deal.latitude = latitude
    deal.longitude = longitude
    deal.formatted_address = formatted_address
    
    # Set archived status based on action
    if action == 'post':
        deal.is_archived = False
        deal.archived_at = None
    else:
        deal.is_archived = True
        deal.archived_at = timezone.now()
    
    try:
        # Save the deal
        deal.save()
        
        # If publishing, check for wishlist matches
        if action == 'post':
            check_deal_against_wishlist(deal)
            messages.success(request, "Deal published successfully!")
            return redirect('product', pk=deal.id)
        else:
            messages.success(request, "Deal updated and saved as draft.")
            return redirect('archived_deals')
            
    except IntegrityError as e:
        # Show specific error message for URL uniqueness constraint
        if 'Dealurl' in str(e):
            messages.error(request, "This URL is already in use by another deal. Please enter a different URL.")
        else:
            messages.error(request, "An error occurred while saving the deal. Please try again.")
        
        return redirect('continue_archived_deal', deal_id=deal.id)

def delete_archived_deal(request, deal_id):
    if not request.user.is_authenticated:
        messages.error(request, "You must be logged in to delete deals.")
        return redirect('login')
    
    if request.method == "POST":
        try:
            deal = Product.objects.get(id=deal_id, user=request.user, is_archived=True)
            deal.delete()
            messages.success(request, "Archived deal deleted successfully.")
        except Product.DoesNotExist:
            messages.error(request, "Archived deal not found.")
    
    return redirect('archived_deals')

def publish_archived_deal(request, deal_id):
    """View to publish an archived deal with proper validation"""
    if not request.user.is_authenticated:
        messages.error(request, "You must be logged in to publish deals.")
        return redirect('login')
        
    if request.method == "POST":
        try:
            deal = Product.objects.get(id=deal_id, user=request.user, is_archived=True)
            
            # Validate required fields before publishing
            validation_errors = []
            
            # Check required fields
            if not deal.Name or deal.Name == "Draft Deal":
                validation_errors.append("Deal title is required")
                
            if not deal.store:
                validation_errors.append("Store name is required")
                
            if not deal.category:
                validation_errors.append("Category is required")
                
            # Validate prices
            if deal.Price <= 0:
                validation_errors.append("List price must be greater than zero")
                
            # If there's a sale price, make sure it's less than the regular price
            if deal.sale_price > 0 and deal.sale_price >= deal.Price:
                validation_errors.append("Sale price must be less than list price")
                
            # Location validation
            if deal.store_type == 'physical':
                if not deal.latitude or not deal.longitude:
                    validation_errors.append("Physical store location is required")
            
            # If city is missing but formatted_address exists, try to extract city
            if not deal.city and deal.formatted_address:
                # Try to extract city from formatted address
                address_parts = deal.formatted_address.split(',')
                if len(address_parts) >= 2:
                    # Use the second part as a potential city
                    deal.city = address_parts[1].strip()
                else:
                    # Fallback to the first address part if we can't extract a city
                    deal.city = address_parts[0].strip()
            
            # If store type is online but no city, default to a common city
            if not deal.city and deal.store_type == 'online':
                deal.city = "Amman"  # Default city for online stores
            
            # Check expiration date
            if not deal.expires_at or deal.expires_at <= timezone.now():
                # Set a default expiration date (10 days from now)
                deal.expires_at = timezone.now() + timezone.timedelta(days=10)
            
            # If there are validation errors, show a single message and redirect to edit page
            if validation_errors:
                messages.error(request, "This deal cannot be published because some required information is missing. Please complete all required fields.")
                return redirect('continue_archived_deal', deal_id=deal.id)
            
            # All validation passed, change status to published
            deal.is_archived = False
            deal.archived_at = None
            deal.save()
            
            # Check for wishlist matches and create notifications
            check_deal_against_wishlist(deal)
            
            messages.success(request, "Deal published successfully!")
            return redirect('product', pk=deal.id)
            
        except Product.DoesNotExist:
            messages.error(request, "Archived deal not found.")
    
    return redirect('archived_deals')




@login_required
def report_deal(request, product_id):
    """AJAX view for reporting a deal"""
    product = get_object_or_404(Product, id=product_id)
    
    # Get the customer profile for the logged-in user
    try:
        customer = Customer.objects.get(user=request.user)
    except Customer.DoesNotExist:
        return JsonResponse({
            'success': False,
            'message': 'You need a customer profile to report deals.'
        }, status=400)
    
    # Get form data
    reason = request.POST.get('reason')
    details = request.POST.get('message')
    
    # Validate data
    if not reason or reason not in dict(ReportedDeal.REPORT_REASONS):
        return JsonResponse({
            'success': False,
            'message': 'Please select a valid reason.'
        }, status=400)
    
    # Check if user already reported this product with the same reason
    existing_report = ReportedDeal.objects.filter(
        product=product,
        reporter=customer,
        reason=reason
    ).exists()
    
    if existing_report:
        return JsonResponse({
            'success': False,
            'message': f"You've already reported this deal as '{dict(ReportedDeal.REPORT_REASONS).get(reason)}'."
        })
    
    # Create the report
    report = ReportedDeal.objects.create(
        product=product,
        reporter=customer,
        reason=reason,
        details=details
    )
    
    return JsonResponse({
        'success': True,
        'message': 'Thank you for your report. Our team will review it soon.'
    })

