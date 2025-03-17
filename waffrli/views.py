from decimal import Decimal, InvalidOperation
from django.shortcuts import get_object_or_404, redirect, render
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.http import JsonResponse
from django.db.models import Q
import firebase_admin
from .models import *
from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.db.models import Count
import json
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.models import User
from firebase_admin import auth as firebase_auth
from .forms import UserUpdateForm, ProfileUpdateForm


def home(request):
    products = Product.objects.all()
    return render(request, 'home.html',{'products':products})


# Category view - Display products of a specific category
def category(request, foo):
    foo = foo.replace('-', ' ').strip()
    try:
        category = Category.objects.get(name__iexact=foo)
        products = Product.objects.filter(category=category)
        
        # Get unique store names from products in this category
        stores = Product.objects.filter(category=category).values_list('store', flat=True).distinct()

        return render(request, 'category.html', {'products': products, 'category': category, 'stores': stores})
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
        
        store_names = request.GET.get("stores", "").split(",") if request.GET.get("stores") else []
        min_price = request.GET.get("min_price", 0)
        max_price = request.GET.get("max_price", 999999)
        rating_filter = request.GET.get("ratings", "").split(",") if request.GET.get("ratings") else []

        # Convert to numbers to prevent errors
        try:
            min_price = float(min_price)
            max_price = float(max_price)
            rating_filter = [int(r) for r in rating_filter if r.isdigit()]
        except ValueError:
            return JsonResponse({"error": "Invalid filters"}, status=400)

        # Start filtering by category and **sale_price**
        products = Product.objects.filter(category=category, sale_price__gte=min_price, sale_price__lte=max_price)

        # Apply store filtering only if stores are selected
        if store_names and store_names[0] != "":
            products = products.filter(store__in=store_names)

        # Apply rating (likes) filtering
        if rating_filter:
            query = Q()
            for rating in rating_filter:
                query |= Q(likes__gte=rating)  # Filter products with at least X likes
            products = products.filter(query)

        # Ensure distinct products
        products = products.distinct()

        data = {
            "products": [
                {
                    "id": p.id,
                    "name": p.Name,
                    "store": p.store,
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
        
        # Create context with all necessary data
        context = {
            'product': product,
            'comments': comments,
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
        address = request.POST.get('address')
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
                address=address
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
    """Handle password reset completion and sync with Firebase"""
    # This would be called after a user completes the Django password reset process
    
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




# Search functionality
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
        pic = request.FILES.get('pic')
        if not pic:
            messages.error(request, "Please upload an image.")
            return redirect('post_deal')

        # Fetch form data
        name = request.POST.get('name')
        url = request.POST.get('url')
        sale_price = request.POST.get('sale_price')
        price = request.POST.get('price')
        description = request.POST.get('description')
        store = request.POST.get('store')
        category_id = request.POST.get('category')
        location = request.POST.get('location')

        # Validate required fields
        if not name or not store or not category_id or not location:
            messages.error(request, "Please fill in all required fields.")
            return redirect('post_deal')

        # Fetch category
        try:
            category = Category.objects.get(id=int(category_id))
        except Category.DoesNotExist:
            messages.error(request, "Invalid category selected.")
            return redirect('post_deal')

        # Check if URL already exists
        if Product.objects.filter(Dealurl=url).exists():
            messages.error(request, "A product with this URL already exists.")
            return redirect('post_deal')

        # Convert price fields to Decimal safely
        try:
            sale_price = Decimal(sale_price) if sale_price else Decimal("0.00")
            price = Decimal(price) if price else Decimal("0.00")
        except (ValueError, InvalidOperation):
            messages.error(request, "Invalid price format.")
            return redirect('post_deal')

        # Create and save the product
        deal = Product.objects.create(
            user=request.user,  # Corrected: Assign the user directly
            Dealurl=url,
            Name=name,
            sale_price=sale_price,
            Price=price,
            Description=description,
            store=store,
            image=pic,
            category=category,
            city=location,
        )

        messages.success(request, "Deal posted successfully!")
        return redirect('home')

    print("GET request received")  # Debugging output

    # Fetch categories to display in the form
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

    

@login_required
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




def wishlist(request):
    return render(request, "wishlist.html", {})


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


def settings(request):
    return render(request, "settings.html", {})


    
@login_required
def update_info(request):
    try:
        # Get the customer profile associated with the user
        customer = Customer.objects.get(user=request.user)
        
        if request.method == 'POST':
            user_form = UserUpdateForm(request.POST, instance=request.user)
            profile_form = ProfileUpdateForm(request.POST, request.FILES, instance=request.user.customer)
            
            if user_form.is_valid() and profile_form.is_valid():
                user_form.save()
                profile_form.save()
                messages.success(request, 'Your profile has been updated successfully!')
                return redirect('update_info')
        else:
            user_form = UserUpdateForm(instance=request.user)
            profile_form = ProfileUpdateForm(instance=customer)
        
        context = {
            'user_form': user_form,
            'profile_form': profile_form,
        }
        
        return render(request, 'update_info.html', context)
    
    except Customer.DoesNotExist:
        # Handle the case where a Customer doesn't exist for this user
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
