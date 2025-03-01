from decimal import Decimal, InvalidOperation
from itertools import count
from django.shortcuts import get_object_or_404, redirect, render
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm
from django.http import JsonResponse
from django.db.models import Q
from .models import *
from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.db.models import Count


# Home view - Display all products
def home(request):
    products = Product.objects.all()
    return render(request, 'home.html',{'products':products})


# Category view - Display products of a specific category
def category(request, foo):
    foo = foo.replace('-', ' ').strip()
    try:
        category = Category.objects.get(name__iexact=foo)
        products = Product.objects.filter(category=category)
        return render(request, 'category.html', {'products': products, 'category': category})
    except Category.DoesNotExist:
        messages.error(request, 'That category does not exist')
    except Exception as e:
        print(f"Unexpected error: {e}")
        messages.error(request, 'An unexpected error occurred')
    return redirect('home')


# # Product detail view
# def product(request, pk):
#     try:
#         product = Product.objects.get(id=pk)
#         return render(request, 'product.html', {'product': product})
#     except Product.DoesNotExist:
#         messages.error(request, 'That product does not exist')
#     except Exception as e:
#         print(f"Unexpected error: {e}")
#         messages.error(request, 'An unexpected error occurred')
#     return redirect('home')

# def deal_detail(request, deal_id):
#     deal = get_object_or_404(Product, id=deal_id)
#     deal.increment_views()  # Increment view count
#     return render(request, 'product.html', {'deal': deal})

def deal_or_product_detail(request, pk):
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




# User registration
def register(request):
    if request.method == 'POST':
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        username = request.POST.get('username', '').strip()
        email = request.POST.get('email', '').strip()
        phone = request.POST.get('phone', '').strip()
        password = request.POST.get('password', '')
        confirm_password = request.POST.get('confirm_password', '')
        address = request.POST.get('address', 'Not Provided')
        gender = request.POST.get('gender', 'N')
        image = request.FILES.get('image', None)
        
        print("Received image:", image)  # Debugging step

        # **1. Validate required fields**
        if not all([first_name, last_name, username, email, phone, password, confirm_password]):
            messages.error(request, "All fields are required.")
            return render(request, 'register.html')

        # **2. Validate passwords**
        if password != confirm_password:
            messages.error(request, "Passwords do not match.")
            return render(request, 'register.html')

        # **3. Check if username or email already exists**
        if User.objects.filter(username=username).exists():
            messages.error(request, "Username is already taken.")
            return render(request, 'register.html')

        if User.objects.filter(email=email).exists():
            messages.error(request, "Email is already in use.")
            return render(request, 'register.html')

        # **4. Create the User**
        user = User.objects.create_user(username=username, email=email, password=password)
        user.first_name = first_name
        user.last_name = last_name
        user.save()

        # **5. Create the Customer profile**
        customer = Customer.objects.create(
            user=user,
            first_name=first_name,
            last_name=last_name,
            phone=phone,
            email=email,
            address=address,
            gender=gender,
            image=image  # This should now store the image
        )

        # **6. Log the user in**
        login(request, user)
        messages.success(request, f'Account created for {user.username}!')
        return redirect('home')

    return render(request, 'register.html')



# User login
def login_user(request):
   if request.method == 'POST':
       username = request.POST['username']
       password = request.POST['password']
       user = authenticate(request,username=username, password=password)
       if user is not None:
           login(request, user)
           
           current_user=Customer.objects.get(user__id=request.user.id)

           messages.success(request,('You have been logged in'))
           return redirect('home')
       else:
           messages.success(request,('There was an error,please try again...'))
           return redirect('login')
   else:
        return render(request,'login.html',{})


# User logout
def logout_user(request):
    logout(request)
    messages.success(request, 'Logged out successfully!')
    return redirect('home')


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


# Post a deal (Ensure user is logged in)
def post_deal(request):
    if not request.user.is_authenticated:
        messages.error(request, "You must be logged in to post a deal.")
        return redirect('login')

    if request.method == "POST":
        print("POST request received")  # Debugging output

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


