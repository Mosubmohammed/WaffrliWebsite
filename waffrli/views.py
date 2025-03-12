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
            if comment_text:
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
                messages.warning(request, 'Please write a comment.')

        # Retrieve all comments for this product
        comments = product.comments.all()

        return render(request, 'product.html', {'product': product, 'comments': comments})

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
            
            # Generate email verification link
            verification_link = firebase_auth.generate_email_verification_link(
                email, 
                action_code_settings=firebase_admin.auth.ActionCodeSettings(
                    url="http://localhost:8000/verified/",  # Use localhost instead of 127.0.0.1
                    handle_code_in_app=False
                )
            )
            
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


def login_user(request):
    if request.method == 'POST':
        username_or_email = request.POST.get('username')
        password = request.POST.get('password')
        
        # Check if input is email or username
        if '@' in username_or_email:
            # It's an email
            try:
                user = User.objects.get(email=username_or_email)
                username = user.username
            except User.DoesNotExist:
                messages.error(request, "No account found with this email")
                return render(request, 'login.html')
        else:
            # It's a username
            username = username_or_email
        
        # Authenticate user
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            login(request, user)
            messages.success(request, "Login successful!")
            return redirect('home')  # Redirect to home or dashboard
        else:
            messages.error(request, "Invalid credentials")
            return render(request, 'login.html')
    
    # For GET requests
    return render(request, 'login.html')

def logout_user(request):
    logout(request)
    messages.success(request, 'Logged out successfully!')
    return redirect('home')

def restPassword(request):
    return render(request,'restPassword.html',{})

@csrf_exempt
def firebase_login(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            token = request.headers.get("Authorization").split("Bearer ")[-1]

            decoded_token = auth.verify_id_token(token)
            uid = decoded_token["uid"]
            email = decoded_token.get("email")

            # Get or create a user in Django
            user, created = User.objects.get_or_create(username=uid, defaults={"email": email})

            # Log the user in
            login(request, user)

            return JsonResponse({"message": "User authenticated successfully"}, status=200)

        except Exception as e:
            return JsonResponse({"error": str(e)}, status=400)

    return JsonResponse({"error": "Invalid request"}, status=400)
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


