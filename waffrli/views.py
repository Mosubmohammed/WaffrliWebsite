import datetime
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
from waffrliApp.settings import db
from django.utils import timezone
from datetime import datetime


def test(request):
    return render(request,'test.html',{})
def home(request):
    Product.objects.filter(expires_at__lte=timezone.now()).delete()
    products = Product.objects.all()
    return render(request, 'home.html',{'products':products})



# def category(request, foo):
#     foo = foo.replace('-', ' ').strip()
#     try:
#         category = Category.objects.get(name__iexact=foo)
#         products = Product.objects.filter(category=category)
        
#         # Get unique store names from products in this category
#         stores = Product.objects.filter(category=category).values_list('store', flat=True).distinct()
        
#         # Get unique city names (instead of location)
#         cities = Product.objects.filter(category=category).values_list('city', flat=True).distinct()
        
#         # Get unique brand names
#         brands = Product.objects.filter(category=category).values_list('brand', flat=True).distinct()

#         return render(request, 'category.html', {
#             'products': products, 
#             'category': category, 
#             'stores': stores,
#             'locations': cities,  # Pass cities as locations for the template
#             'brands': brands
#         })
#     except Category.DoesNotExist:
#         messages.error(request, 'That category does not exist')
#     except Exception as e:
#         print(f"Unexpected error: {e}")
#         messages.error(request, 'An unexpected error occurred')

#     return redirect('home')


def product_list_base(request, page_type=None, category=None):
    """
    Base view function for all product listings with filtering
    Handles hot deals, popular deals, and category filtering
    """
    # Start with the appropriate base query depending on page type
    if page_type == 'hot_deals':
        # Hot deals filter: calculate discount ≥ 70%
        # Using database-level filtering for better performance
        products = Product.objects.filter(
            sale_price__isnull=False,
            Price__gt=0
        ).exclude(
            sale_price__gte=F('Price')
        ).annotate(
            discount_percentage=ExpressionWrapper(
                ((F('Price') - F('sale_price')) * 100) / F('Price'),
                output_field=FloatField()
            )
        ).filter(discount_percentage__gte=70)
        
        page_title = "Hot Deals"
    
    elif page_type == 'popular':
        # Popular deals filter: based on likes and views
        products = Product.objects.annotate(
            like_count=Count('likes'),
            popularity_score=ExpressionWrapper(
                (F('like_count') * 3) + F('views'),  # Likes weighted 3x more than views
                output_field=FloatField()
            )
        ).order_by('-popularity_score')
        
        page_title = "Popular Deals"
    
    elif category:
        # Category filter
        category_obj = get_object_or_404(Category, name__iexact=category.replace('-', ' ').strip())
        products = Product.objects.filter(category=category_obj)
        page_title = f"{category_obj.name} Deals"
    
    else:
        # All products
        products = Product.objects.all()
        page_title = "All Deals"
    
    # Use select_related to avoid N+1 queries
    products = products.select_related('category', 'user', 'customer_pic_id')
    
    # Get filter parameters
    # ---------------------
    
    # Store filter - Get checkbox values directly
    stores = request.GET.getlist('store')
    if stores:
        query = Q()
        for store in stores:
            query |= Q(store__iexact=store.strip())
        products = products.filter(query)
    
    # Location/City filter - Get checkbox values directly
    locations = request.GET.getlist('location')
    if locations:
        query = Q()
        for location in locations:
            query |= Q(city__iexact=location.strip())
        products = products.filter(query)
    
    # Brand filter - Get checkbox values directly
    brands = request.GET.getlist('brand')
    if brands:
        query = Q()
        for brand in brands:
            query |= Q(brand__iexact=brand.strip())
        products = products.filter(query)
    
    # Price range filter
    min_price = request.GET.get('min_price')
    max_price = request.GET.get('max_price')
    
    if min_price:
        try:
            min_price_value = float(min_price)
            products = products.filter(sale_price__gte=min_price_value)
        except (ValueError, TypeError):
            # Handle invalid input silently
            pass
    
    if max_price:
        try:
            max_price_value = float(max_price)
            products = products.filter(sale_price__lte=max_price_value)
        except (ValueError, TypeError):
            # Handle invalid input silently
            pass
    
    # Rating/Likes filter
    rating = request.GET.get('rating')
    if rating and rating != '0':
        try:
            rating_value = int(rating)
            # Using annotation to get accurate likes count
            products = products.annotate(like_count=Count('likes'))
            products = products.filter(like_count__gte=rating_value)
        except (ValueError, TypeError):
            # Handle invalid input silently
            pass
    
    # Handle JSON response for AJAX requests
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or 'json' in request.GET:
        products_data = []
        
        for product in products:
            # Get customer pic URL if available
            customer_pic_url = None
            if product.customer_pic_id and product.customer_pic_id.image:
                customer_pic_url = product.customer_pic_id.image.url
            
            # Calculate discount percentage if not already done
            discount_percentage = getattr(product, 'discount_percentage', None)
            if discount_percentage is None:
                discount_percentage = product.get_discount_percentage()
            
            # Check if the current user has liked this product
            liked_by_user = request.user in product.likes.all() if request.user.is_authenticated else False
            
            products_data.append({
                'id': product.id,
                'name': product.Name,
                'price': str(product.Price),
                'sale_price': str(product.sale_price) if product.sale_price else None,
                'description': product.Description,
                'store': product.store,
                'city': product.city,
                'brand': product.brand,
                'category_name': product.category.name,
                'image_url': product.image.url if product.image else None,
                'username': product.user.username if product.user else "Unknown",
                'create_at': product.create_at.strftime('%d-%m'),
                'customer_pic_url': customer_pic_url,
                'discount_percentage': round(discount_percentage, 2) if discount_percentage else 0,
                'likes_count': product.number_of_likes(),
                'comment_count': 0,  # Replace with actual comment count if available
                'liked_by_user': liked_by_user,
            })
        
        return JsonResponse({'products': products_data})
    
    # Regular HTML response
    # --------------------
    
    # Apply pagination
    paginator = Paginator(products, 20)  # Show 20 products per page
    page_number = request.GET.get('page')
    
    try:
        page_obj = paginator.page(page_number)
    except PageNotAnInteger:
        # If page is not an integer, deliver first page
        page_obj = paginator.page(1)
    except EmptyPage:
        # If page is out of range, deliver last page
        page_obj = paginator.page(paginator.num_pages)
    
    # Get data for filter dropdowns
    # Only fetch distinct values for better performance
    stores_list = Product.objects.values_list('store', flat=True).distinct()
    cities_list = Product.objects.values_list('city', flat=True).distinct()
    brands_list = Product.objects.values_list('brand', flat=True).distinct()
    
    context = {
        'products': page_obj,
        'page_obj': page_obj,
        'stores': stores_list,
        'locations': cities_list,
        'brands': brands_list,
        'selected_stores': stores,
        'selected_locations': locations,
        'selected_brands': brands,
        'min_price': min_price,
        'max_price': max_price,
        'rating': rating,
        'page_title': page_title,
        'page_type': page_type,
        'category': category,
    }
    
    # Choose the appropriate template
    if page_type == 'hot_deals':
        template = 'hot_deals.html'
    elif page_type == 'popular':
        template = 'popular_deals.html'
    elif category:
        template = 'category.html'
    else:
        template = 'products.html'
    
    return render(request, template, context)



def filter_products(request, category):
    category_slug = category.replace('-', ' ').strip()
    return product_list_base(request, category=category_slug)

    
    
    
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
            'user': request.user,  # Ensure user is in context
        }
        
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
        
        # Get expiration date info
        expiration_type = request.POST.get('expiration-type', 'default')
        expiration_date_str = request.POST.get('expiration-date')
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
        
        
# Set expiration date
        if expiration_type == 'custom' and expiration_date_str:
            try:
                # Parse the date from the string (format: YYYY-MM-DD)
                expiration_date = timezone.make_aware(datetime.strptime(expiration_date_str, '%Y-%m-%d'))
                
                # Validate that the expiration date is in the future
                if expiration_date <= timezone.now():
                    messages.error(request, "Expiration date must be in the future.")
                    return redirect('post_deal')
                    
                # Validate that the expiration date is not more than 30 days in the future
                max_date = timezone.now() + timezone.timedelta(days=30)
                if expiration_date > max_date:
                    messages.error(request, "Expiration date cannot be more than 30 days in the future.")
                    return redirect('post_deal')
            except ValueError:
                messages.error(request, "Invalid date format.")
                return redirect('post_deal')
        else:
            # Default: 10 days from now
            expiration_date = timezone.now() + timezone.timedelta(days=1)
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
            expires_at=expiration_date,  
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
    
    


def hot_deals(request):
    return product_list_base(request, page_type='hot_deals')

# def filter_hot_deals(request):
#     return product_list_base(request, page_type='hot_deals')


def popular_deals(request):
    return product_list_base(request, page_type='popular')


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



