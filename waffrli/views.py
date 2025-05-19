import datetime
from decimal import Decimal, InvalidOperation
from django.db import IntegrityError
from django.shortcuts import get_object_or_404, redirect, render
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.http import JsonResponse
from django.db.models import Q
from django.urls import reverse
import httpx
from waffrli.filters import ProductFilter
from .models import *
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.db.models import Count, F, ExpressionWrapper, FloatField,Sum
from django.contrib.auth.models import User
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from .utils import *
from django.utils import timezone
from datetime import datetime
from django.db.models import F, Q, Count, Case, When, FloatField, ExpressionWrapper
from django.contrib import messages as django_messages
from django.contrib.admin.views.decorators import staff_member_required
from authentication.models import SupabaseUser
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.core.cache import cache

def home(request):
    # Instead, get a cache key that changes when new products are added
    from django.core.cache import cache
    
    # Get or set the product count in cache
    product_count = cache.get('total_product_count')
    if product_count is None:
        product_count = Product.objects.count()
        cache.set('total_product_count', product_count, 900)  # 15 minutes
    
    user_lat = None
    user_lng = None
    
    # Your existing location detection code
    if request.user.is_authenticated and hasattr(request.user, 'customer'):
        customer = request.user.customer
        user_lat = customer.latitude
        user_lng = customer.longitude
    
    # Fallback to session or request parameters
    if not user_lat or not user_lng:
        if 'user_latitude' in request.session and 'user_longitude' in request.session:
            user_lat = request.session.get('user_latitude')
            user_lng = request.session.get('user_longitude')
        elif request.GET.get('lat') and request.GET.get('lng'):
            try:
                user_lat = float(request.GET.get('lat'))
                user_lng = float(request.GET.get('lng'))
            except ValueError:
                pass
    
    # If still no location, use default (Amman)
    if not user_lat or not user_lng:
        user_lat = 31.9566  # Amman latitude
        user_lng = 35.9457  # Amman longitude
    
    # Get current time to check for expired deals
    current_time = timezone.now()
    
    # Get all active products and sort by expiration status
    # First get non-expired products
    active_products = Product.objects.filter(
        is_archived=False,
        expires_at__gt=current_time  # Products that have not expired yet
    ).order_by('-create_at')
    
    # Then get expired products
    expired_products = Product.objects.filter(
        is_archived=False,
        expires_at__lte=current_time  # Products that have expired
    ).order_by('-create_at')
    
    # Combine the two querysets (active first, then expired)
    # We need to convert to list because we'll be adding attributes
    products_list = list(active_products) + list(expired_products)
    
    # Add distance attribute to each product for nearby section
    for product in products_list:
        # Set expiration status
        product.is_expired = product.expires_at <= current_time if product.expires_at else False
        
        # Calculate distance only for physical stores with location data
        if product.store_type == 'physical' and product.latitude and product.longitude:
            # Add the calculated distance as an attribute
            product.distance_to = product.distance_to(user_lat, user_lng)
        else:
            # For online stores or stores without location, set distance_to to None
            product.distance_to = None
    
    # Filter products to show only those with distance (physical stores)
    nearby_products = [p for p in products_list if p.distance_to is not None]
    
    # Sort nearby products by distance
    nearby_products.sort(key=lambda x: x.distance_to)
    
    # Limit to nearby products within 50km (optional)
    MAX_DISTANCE = 50
    nearby_products_filtered = [p for p in nearby_products if p.distance_to <= MAX_DISTANCE]
    
    # If no nearby products within range, show closest 5 products
    if not nearby_products_filtered and nearby_products:
        nearby_products_filtered = nearby_products[:5]
    
    # PAGINATION FOR WAFFRLI DEALS (all_products)
    # Get the requested page number from the URL
    page = request.GET.get('page', 1)
    
    # Create a paginator object with 50 items per page
    paginator = Paginator(products_list, 50)
    
    try:
        # Get the requested page
        all_products = paginator.page(page)
    except PageNotAnInteger:
        # If page is not an integer, deliver first page
        all_products = paginator.page(1)
    except EmptyPage:
        # If page is out of range, deliver last page
        all_products = paginator.page(paginator.num_pages)
    
    # Your existing popular products code
    popular_products = Product.objects.filter(
        is_archived=False
    ).annotate(
        like_count=Count('likes'),
        popularity_score=ExpressionWrapper(
            (F('like_count') * 3) + F('views'),
            output_field=FloatField()
        )
    ).order_by('-popularity_score').select_related('category', 'user', 'customer_pic_id')[:12]

    # Your existing category products code
    try:
        phones_category = Category.objects.get(name__icontains='Phones')
    except Category.DoesNotExist:
        phones_category = None
        
    try:
        computers_category = Category.objects.get(name__icontains='computers')
    except Category.DoesNotExist:
        computers_category = None
        
    try:
        bags_category = Category.objects.get(name__icontains='BagsAndLuggage')
    except Category.DoesNotExist:
        bags_category = None
    
    phone_products = []
    computer_products = []
    bag_products = []
    
    if phones_category:
        phone_products = Product.objects.filter(
            category=phones_category,
            is_archived=False
        ).order_by('-create_at')[:4]
    
    if computers_category:
        computer_products = Product.objects.filter(
            category=computers_category,
            is_archived=False
        ).order_by('-create_at')[:4]
    
    if bags_category:
        bag_products = Product.objects.filter(
            category=bags_category,
            is_archived=False
        ).order_by('-create_at')[:4]
    
    # Your existing code to fill categories with keyword searches
    if len(phone_products) < 4:
        additional_phones = Product.objects.filter(
            Name__icontains='phone',
            is_archived=False
        ).exclude(id__in=[p.id for p in phone_products])[:4-len(phone_products)]
        phone_products = list(phone_products) + list(additional_phones)
    
    if len(computer_products) < 4:
        additional_computers = Product.objects.filter(
            Name__icontains='computer',
            is_archived=False
        ).exclude(id__in=[p.id for p in computer_products])[:4-len(computer_products)]
        computer_products = list(computer_products) + list(additional_computers)
    
    if len(bag_products) < 4:
        additional_bags = Product.objects.filter(
            Name__icontains='bag',
            is_archived=False
        ).exclude(id__in=[p.id for p in bag_products])[:4-len(bag_products)]
        bag_products = list(bag_products) + list(additional_bags)
    
    context = {
        'products': nearby_products_filtered, 
        'all_products': all_products, 
        'popular_products': popular_products,
        'phone_products': phone_products,
        'computer_products': computer_products,
        'bag_products': bag_products,
        'user_lat': user_lat,
        'user_lng': user_lng,
        'paginator': paginator,  
        'current_page': page,   
        'product_count': product_count,
    }
    
    return render(request, 'home.html', context)


def product_list(request, page_type=None, category=None):
    products = get_base_queryset(request, page_type, category)
    
    filter_set = ProductFilter(request.GET, queryset=products, request=request)
    filtered_products = filter_set.qs
    
    user_location = get_user_location(request)
    
    # Calculate distances for ALL products before any sorting or pagination
    if user_location['has_location']:
        # Create a list to avoid modifying the query
        products_list = list(filtered_products)
        
        # Calculate distances for each product
        for product in products_list:
            if product.latitude and product.longitude:
                # Store in a DIFFERENT attribute (distance) than the method (distance_to)
                product.distance = product.distance_to(user_lat=user_location['lat'], user_lng=user_location['lng'])
            else:
                product.distance = float('inf')
        
        # If sort by distance is requested, sort the product list
        if request.GET.get('sort_by') == 'distance':
            products_list.sort(key=lambda x: x.distance)
            
            # Convert back to queryset with preserved order
            product_ids = [p.id for p in products_list]
            if product_ids:
                preserved_order = Case(*[When(pk=pk, then=pos) for pos, pk in enumerate(product_ids)])
                filtered_products = filtered_products.filter(id__in=product_ids).order_by(preserved_order)
    
    daily_deals = []
    if page_type == 'popular':
        current_time = timezone.now()
        
        daily_deals = Product.objects.filter(
            is_archived=False,
            sale_price__isnull=False,
            Price__gt=0,
            expires_at__gt=current_time
        ).exclude(
            sale_price__gte=F('Price') 
        ).annotate(
            discount_percentage=ExpressionWrapper(
                ((F('Price') - F('sale_price')) * 100) / F('Price'),
                output_field=FloatField()
            )
        ).order_by('-discount_percentage')[:3]
        
        for deal in daily_deals:
            deal.discount_percentage = round(deal.discount_percentage)
            deal.progress_percentage = min(deal.views // 5 + deal.likes.count() * 10, 90)
            
            likes_count = deal.likes.count()
            views_count = deal.views
            
            if likes_count > 50:
                deal.status_icon = "👑"
                deal.status_text = "Best Seller"
            elif views_count > 200:
                deal.status_icon = "📈"
                deal.status_text = "Trending"
            elif likes_count > 20:
                deal.status_icon = "💎"
                deal.status_text = "Customer Favorite"
            else:
                deal.status_icon = "⭐"
                deal.status_text = "Popular Choice"
    
    if is_ajax_request(request):
        # Prepare products for JSON response with distance information already calculated
        return JsonResponse({
            'products': format_products_for_json(filtered_products, request, user_location)
        })
    
    page_obj = paginate_products(request, filtered_products)
    
    # Re-apply distances to paginated objects to ensure consistency
    if user_location['has_location']:
        # We've already calculated distances above, but they might be lost during pagination
        # So we recalculate them for the paginated objects
        add_distances_to_products(page_obj, user_location['lat'], user_location['lng'])
        for product in page_obj:
            print(f"Product {product.id}: distance = {getattr(product, 'distance', 'NOT SET')}")
    
    filter_options = get_filter_options(filtered_products)

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
        'daily_deals': daily_deals, 
    }
    
    template = get_template_for_page(page_type, category)
    
    return render(request, template, context)



def get_base_queryset(request, page_type, category):
    if page_type == 'hot_deals' and not any([
        request.GET.getlist('store'), 
        request.GET.getlist('location'),
        request.GET.getlist('brand')
    ]):
        hot_deals = Product.objects.filter(
            sale_price__isnull=False,
            Price__gt=0,
            is_archived=False  # Exclude archived deals
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
        return Product.objects.filter(
            sale_price__isnull=False,
            Price__gt=0,
            is_archived=False  # Exclude archived deals
        ).exclude(
            sale_price__gte=F('Price')
        ).annotate(
            discount_percentage=ExpressionWrapper(
                ((F('Price') - F('sale_price')) * 100) / F('Price'),
                output_field=FloatField()
            )
        ).select_related('category', 'user', 'customer_pic_id')
        
    elif page_type == 'popular':
        return Product.objects.filter(
            is_archived=False  # Exclude archived deals
        ).annotate(
            like_count=Count('likes'),
            popularity_score=ExpressionWrapper(
                (F('like_count') * 3) + F('views'),
                output_field=FloatField()
            )
        ).order_by('-popularity_score').select_related('category', 'user', 'customer_pic_id')
        
    elif category:
        category_obj = get_object_or_404(Category, name__iexact=category.replace('-', ' ').strip())
        return Product.objects.filter(
            category=category_obj,
            is_archived=False  # Exclude archived deals
        ).select_related('category', 'user', 'customer_pic_id')
        
    else:
        return Product.objects.filter(
            is_archived=False  # Exclude archived deals
        ).select_related('category', 'user', 'customer_pic_id')




def format_products_for_json(products, request, user_location):
    products_data = []
    
    for product in products:
        customer_pic_url = None
        if product.customer_pic_id and product.customer_pic_id.image:
            customer_pic_url = product.customer_pic_id.image.url
        
        discount_percentage = getattr(product, 'discount_percentage', None)
        if discount_percentage is None:
            discount_percentage = product.get_discount_percentage()
        
        liked_by_user = request.user in product.likes.all() if request.user.is_authenticated else False
        
        distance = None
        if user_location['has_location'] and product.latitude and product.longitude:
            # Call the method directly for JSON format
            distance = product.distance_to(user_location['lat'], user_location['lng'])
        
        savings = product.get_savings_amount()
        
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



def get_filter_options(products):

    store_values = products.values_list('store', flat=True)
    stores_list = sorted(set(store.strip().lower() for store in store_values if store), key=lambda x: x.lower())
    
    city_values = products.values_list('city', flat=True)
    cities_list = sorted(set(city.strip().lower() for city in city_values if city), key=lambda x: x.lower())
    
    brand_values = products.values_list('brand', flat=True)
    brands_list = sorted(set(brand.strip().lower() for brand in brand_values if brand), key=lambda x: x.lower())
    
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
    
    jordan_cities.sort()
    
    return {
        'stores': stores_list,
        'cities': cities_list,
        'brands': brands_list,
        'jordan_cities': jordan_cities
    }


def get_page_title(request, page_type, category):
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
        product = get_object_or_404(Product, id=pk)
        
        # Increment view count
        product.increment_views()

        # Get related products
        related_products = Product.objects.filter(
            category=product.category
        ).exclude(
            id=product.id
        ).order_by(
            '-create_at' 
        )[:6]  
        
        # Calculate discount percentages
        if product.Price and product.sale_price:
            product.discount_percentage = product.get_discount_percentage()
        else:
            product.discount_percentage = 0
        
        # Process related products
        for related_product in related_products:
            if related_product.Price and related_product.sale_price:
                related_product.discount_percentage = related_product.get_discount_percentage()
            else:
                related_product.discount_percentage = 0
            
            related_product.is_popular = related_product.views > 100 or related_product.likes.count() > 10
            related_product.time_ago = related_product.create_at
        
        # Check if user is following the product poster
        is_following = False
        if request.user.is_authenticated and request.user != product.user:
            is_following = Follow.objects.filter(follower=request.user, following=product.user).exists()
        
        # Get poster's profile stats
        deal_count = Product.objects.filter(user=product.user).count()
        comment_count = Comment.objects.filter(customer__user=product.user).count()
        total_likes_received = Product.objects.filter(user=product.user).aggregate(Sum('likes'))['likes__sum'] or 0
        reputation_points = total_likes_received * 5
        
        
        # Process comments on POST
        if request.method == 'POST':
            comment_text = request.POST.get('comment')
            
            if not request.user.is_authenticated:
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({
                        'success': False,
                        'error': 'Please log in to comment.'
                    }, status=401)
                messages.warning(request, 'Please log in to comment.')
                
            elif not comment_text or comment_text.strip() == '':
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({
                        'success': False,
                        'error': 'Please write a comment before posting.'
                    }, status=400)
                messages.warning(request, 'Please write a comment before posting.')
            else:
                try:
                    customer = Customer.objects.get(user=request.user)
                    
                    comment = Comment.objects.create(
                        product=product,
                        customer=customer,
                        text=comment_text
                    )

                    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                        user_image = None
                        if customer.image:
                            user_image = customer.image.url
                        
                        return JsonResponse({
                            'success': True,
                            'comment': {
                                'id': comment.id,
                                'text': comment.text,
                                'username': request.user.username,
                                'user_image': user_image,
                                'time_ago': 'Just now'
                            }
                        })
                    
                    messages.success(request, 'Your comment has been posted successfully!')
                    
                    return redirect('product', pk=pk)
                    
                except Customer.DoesNotExist:
                    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                        return JsonResponse({
                            'success': False,
                            'error': 'Your user profile is missing. Please contact support.'
                        }, status=400)
                    messages.error(request, 'Your user profile is missing. Please contact support.')
        
        # Get all comments for the product
        comments = Comment.objects.filter(product=product).order_by('-timestamp')
        
        # Prepare context for template
        context = {
            'product': product,
            'comments': comments,
            'related_products': related_products,
            'is_following': is_following,
            'deal_count': deal_count,
            'comment_count': comment_count,
            'reputation_points': reputation_points,
            'total_likes_received': total_likes_received,
            'user': request.user,

        }
        
        return render(request, 'product.html', context)
        
    except Product.DoesNotExist:
        messages.error(request, 'That product does not exist.')
        return redirect('home')



def search(request):
    if request.method == "POST":
        searched = request.POST['searched']
        results = Product.objects.filter(
            Q(Name__icontains=searched) |
            Q(Description__icontains=searched) |
            Q(category__name__icontains=searched)
        )

        result_count = results.count()

        return render(request, "search.html", {
            'searched': results,
            'search_term': searched,
            'result_count': result_count
        })

    return render(request, "home.html")

    
def post_deal(request):

    if not request.user.is_authenticated:
        messages.error(request, "You must be logged in to post a deal.")
        return redirect('login')
    
    
    jordan_cities = [
        'Amman', 'Zarqa', 'Irbid', 'Aqaba', 'Salt', 'Madaba', 'Jerash',
        'Ajloun', 'Mafraq', 'Tafilah', 'Karak', 'Ma\'an', 'Ramtha', 'Sahab', 
        'Russeifa', 'Al-Quwaysimah', 'Wadi as-Ser', 'Tila al-Ali', 'Baqa\'a',
        'Zarqa Camp', 'Suwaylih', 'Um al-Jimal', 'Petra', 'Azraq'
    ]
    
    if request.method != "POST":
        categories = Category.objects.all()
        context = {
            'categories': categories,
            'jordan_cities': jordan_cities
        }
        return render(request, "post_deal.html", context)
    
    
    action = request.POST.get('action', 'post')
    

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
        
        cache.delete('total_product_count')
        
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
    # Get the product or return 404
    product = get_object_or_404(Product, id=product_id)
    user = request.user
    
    # Check if user is authenticated
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
                'likes_count': product.likes.count()  # Make sure this key matches what the JS is expecting
            })
        
        # For non-AJAX requests, redirect back to the referring page
        return redirect(request.META.get('HTTP_REFERER', 'home'))
    
    # If not authenticated and it's an AJAX request, return error
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            'error': 'You must be logged in to like a product.'
        }, status=401)
    
    # Otherwise redirect to login page
    return redirect('login')

        
def user_profile(request, identifier):

    try:
        user_id = int(identifier)
        profile_user = get_object_or_404(User, id=user_id)
    except ValueError:
        profile_user = get_object_or_404(User, username=identifier)
    
    is_following = Follow.objects.filter(follower=request.user, following=profile_user).exists()
    followers = profile_user.followers.all()
    following = profile_user.following.all()

    deal_count = Product.objects.filter(user=profile_user).count()
    comment_count = Comment.objects.filter(customer=profile_user.customer).count()

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
    if not request.user.is_authenticated:
        messages.error(request, "You must be logged in to view your wishlist.")
        return redirect('login')

    wishlist_items = WishlistItem.objects.filter(user=request.user).order_by('-created_at')

    categories = Category.objects.all()
    
    unread_notification_count = Notification.objects.filter(user=request.user, is_read=False).count()
    
    context = {
        'wishlist_items': wishlist_items,
        'categories': categories,
        'unread_notification_count': unread_notification_count,
    }
    
    return render(request, 'wishlist.html', context)

@login_required
def add_wishlist_item(request):

    try:

        data = json.loads(request.body)
        

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

    try:
        wishlist_item = WishlistItem.objects.get(id=item_id, user=request.user)
        
        keyword = wishlist_item.keyword
        category_name = wishlist_item.category  # This is already a string
        
        # Delete the wishlist item
        wishlist_item.delete()
        
        return JsonResponse({'status': 'success'})
    except WishlistItem.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Wishlist item not found'}, status=404)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)



@login_required
@require_POST
def follow(request, user_id):
    user_to_follow = get_object_or_404(User, id=user_id)
    if user_to_follow != request.user:
        Follow.objects.get_or_create(follower=request.user, following=user_to_follow)
    return JsonResponse({'status': 'followed'})

@login_required
@require_POST
def unfollow(request, user_id):
    user_to_unfollow = get_object_or_404(User, id=user_id)
    Follow.objects.filter(follower=request.user, following=user_to_unfollow).delete()
    return JsonResponse({'status': 'unfollowed'})





@login_required
def settings_view(request):
    try:
        customer = request.user.customer
        allow_username_edit = False
        
        if request.method == 'POST':

            if 'request_username' in request.POST:
                new_username = request.POST.get('new_username')
                if new_username:
                    if User.objects.filter(username=new_username).exists():
                        messages.error(request, "This username is already taken. Please choose a different one.")
                        return redirect('settings')
                    
                    request.user.username = new_username
                    request.user.save()
                    messages.success(request, f'Your username has been updated to @{new_username}!')
                    return redirect('settings')
            

            if 'update_profile' in request.POST:
                email = request.POST.get('email')
                

                if not email or email == request.user.email:
                    return redirect('settings')

                if User.objects.filter(email=email).exclude(id=request.user.id).exists():
                    messages.error(request, "This email address is already registered with another account.")
                    return redirect('settings')
                
                old_email = request.user.email
                
                try:
  
                    request.user.email = email
                    request.user.save()
                    
                    customer.email = email
                    customer.save()
                    
      
                    try:
                        from django.conf import settings as django_settings
                        supabase_user = SupabaseUser.objects.get(user=request.user)
                        
                        # Check if we have a valid Supabase ID
                        if not hasattr(supabase_user, 'supabase_id') or not supabase_user.supabase_id:
                            messages.success(request, f"Your email has been updated to {email}.")
                            messages.info(request, "Note: Your login credentials may still use your previous email. Please contact support if you experience any issues.")
                            return redirect('settings')
                        
                        # Check if we have the required settings
                        if not hasattr(django_settings, 'SUPABASE_URL') or not hasattr(django_settings, 'SUPABASE_SERVICE_KEY'):
                            missing_settings = []
                            if not hasattr(django_settings, 'SUPABASE_URL'):
                                missing_settings.append('SUPABASE_URL')
                            if not hasattr(django_settings, 'SUPABASE_SERVICE_KEY'):
                                missing_settings.append('SUPABASE_SERVICE_KEY')
                            
                            messages.success(request, f"Your email has been updated to {email}.")
                            messages.info(request, "Note: Your login credentials may still use your previous email. Please contact support if you experience any issues.")
                            return redirect('settings')


                        
                        url = f"{django_settings.SUPABASE_URL}/auth/v1/admin/users/{supabase_user.supabase_id}"
                        headers = {
                            "apikey": django_settings.SUPABASE_SERVICE_KEY,
                            "Authorization": f"Bearer {django_settings.SUPABASE_SERVICE_KEY}",
                            "Content-Type": "application/json"
                        }
                        data = {"email": email}
                        
                        response = httpx.put(url, json=data, headers=headers)
                        
                        if response.status_code == 200:
                            messages.success(request, f"Your email has been successfully updated to {email}!")
                        else:
                            messages.success(request, f"Your email has been updated to {email}.")
                            messages.warning(request, "However, we couldn't update your login email. You may need to continue using your previous email to sign in.")
                            
                    except SupabaseUser.DoesNotExist:
                        messages.success(request, f"Your email has been updated to {email}.")
                        messages.info(request, "Note: Your login credentials may still use your previous email. Please contact support if you experience any issues.")
                    except Exception as supabase_error:
                        messages.success(request, f"Your email has been updated to {email}.")
                        messages.warning(request, "However, we couldn't update your login email. You may need to continue using your previous email to sign in.")
                    
                except Exception as e:
                    # Rollback changes if there's an error
                    request.user.email = old_email
                    request.user.save()
                    if hasattr(customer, 'email'):
                        customer.email = old_email
                        customer.save()
                    messages.error(request, f"We couldn't update your email address. Please try again later or contact support for assistance.")
                
                return redirect('settings')
        
        # Render the settings page for GET requests
        return render(request, 'settings.html', {'allow_username_edit': allow_username_edit})
    
    except Exception as e:
        messages.error(request, "Something went wrong while accessing your settings. Please try again later.")
        return redirect('home')

    
    
@login_required
def update_info(request):
    try:
        customer = request.user.customer
        
        if request.method == 'POST':
            
            first_name = request.POST.get('first_name', '')
            last_name = request.POST.get('last_name', '')

            request.user.first_name = first_name
            request.user.last_name = last_name
            request.user.save()
            
            customer.first_name = first_name
            customer.last_name = last_name
            customer.phone = request.POST.get('phone', '')
            
            latitude = request.POST.get('latitude')
            longitude = request.POST.get('longitude')
            formatted_address = request.POST.get('formatted_address')
            
            if latitude and longitude:
                try:
                    customer.latitude = float(latitude)
                    customer.longitude = float(longitude)
                except ValueError:
                    messages.warning(request, 'Invalid location coordinates provided.')
            
            if formatted_address:
                customer.formatted_address = formatted_address
            
            if request.FILES.get('image'):
                customer.image = request.FILES.get('image')
            
            customer.save()
            messages.success(request, 'Profile information updated successfully!')
            return redirect('update_info')
        
        return render(request, 'update_info.html')
        
    except AttributeError:
        messages.error(request, 'Customer profile not found. Please contact support.')
        return redirect('settings')


def toggle_save_product(request, product_id):

    if not request.user.is_authenticated:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'error': 'You must be logged in to save products.',
                'redirect_url': reverse('login')
            }, status=401)
        
        messages.warning(request, "You need to log in to save products.")
        return redirect('login')
    

    try:
        product = get_object_or_404(Product, id=product_id)
        
        customer = Customer.objects.get(user=request.user)

        if product in customer.saved_products.all():
                # User has already saved this product, so remove it
                customer.saved_products.remove(product)
                is_saved = False
                message = f"'{product.Name}' removed from your saved items."
        else:
                # User hasn't saved this product, so save it
                customer.saved_products.add(product)
                is_saved = True
                message = f"'{product.Name}' added to your saved items."
            

        if not request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                messages.success(request, message)
            
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'is_saved': is_saved,
                    'saved_count': customer.saved_products.count(),
                    'message': message
                })
            
        return redirect('product', pk=product_id)
            

    
    except Exception as e:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'error': f'An error occurred: {str(e)}'
            }, status=500)
        
        messages.error(request, f"An error occurred: {str(e)}")
        return redirect('home')


def saved_items(request):

    if not request.user.is_authenticated:
        messages.warning(request, "You need to be logged in to view saved items.")
        return redirect('login')
    
    try:
        customer = Customer.objects.get(user=request.user)
        saved_products = customer.saved_products.all().order_by('-id')
        
        context = {
            'saved_products': saved_products,
            'saved_count': saved_products.count(),
        }
        
        return render(request, 'saved_items.html', context)
        
    except Customer.DoesNotExist:
        messages.error(request, "Customer profile not found. Please contact support.")
        return redirect('home')
    
    
def inbox(request):
    inbox_messages = Message.objects.filter(recipient=request.user).order_by('-date_sent')
    
    # Count unread messages
    unread_count = Message.objects.filter(recipient=request.user, is_read=False).count()
    
    context = {
        'user': request.user,
        'total_messages': Message.objects.filter(recipient=request.user).count() + Message.objects.filter(sender=request.user).count(),
        'inbox_count': Message.objects.filter(recipient=request.user).count(),
        'sent_count': Message.objects.filter(sender=request.user).count(),
        'unread_count': unread_count,  # Add this line
        'inbox_messages': inbox_messages,  
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
            content=body,
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
        # Try to find the message where the user is either the recipient OR the sender
        message = Message.objects.filter(
            id=message_id
        ).filter(
            Q(recipient=request.user) | Q(sender=request.user)
        ).first()
        
        if not message:
            raise Message.DoesNotExist
            
        is_inbox = message.recipient == request.user
        

        if is_inbox and not message.is_read:
            message.is_read = True
            message.save()
        
        inbox_count = Message.objects.filter(recipient=request.user).count()
        sent_count = Message.objects.filter(sender=request.user).count()
        total_messages = inbox_count + sent_count
        
        context = {
            'message': message,
            'is_inbox': is_inbox,
            'inbox_count': inbox_count,
            'sent_count': sent_count,
            'total_messages': total_messages,
            'active_tab': 'inbox' if is_inbox else 'sent'
        }
        
        return render(request, 'view_message.html', context)
        
    except Message.DoesNotExist:
        messages.error(request, 'Message not found.')
        return redirect('inbox')

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
        'user_messages': sent_messages,  
        'active_tab': 'sent',
        'now': timezone.now(),  
    }
    
    return render(request, 'sent_items.html', context)


@login_required
def delete_messages(request):
    if request.method == 'POST':
        message_ids = request.POST.getlist('message_ids')
        folder = request.POST.get('folder', 'inbox')
        
        if message_ids:
            # Create a base query that joins inbox and sent conditions
            base_query = Q(id__in=message_ids) & (
                Q(recipient=request.user) | Q(sender=request.user)
            )
            
            if folder == 'inbox':
                # Only allow deleting inbox messages where user is recipient
                base_query &= Q(recipient=request.user)
            else:  # sent folder
                # Only allow deleting sent messages where user is sender
                base_query &= Q(sender=request.user)
                
            deleted_count = Message.objects.filter(base_query).delete()[0]
            messages.success(request, f'{deleted_count} message(s) deleted successfully.')
        
        if folder == 'sent':
            return redirect('sent_items')
        else:
            return redirect('inbox')
            
    return redirect('inbox')


@staff_member_required
def admin_reply_message(request, message_id):

    original_message = get_object_or_404(Message, id=message_id)
    
    if request.method == 'POST':
        subject = f"Re: {original_message.subject}" if not original_message.subject.startswith('Re:') else original_message.subject
        content = request.POST.get('content')
        
        if not content:
            django_messages.error(request, 'Reply cannot be empty.')
            return redirect('admin:waffrli_message_change', message_id)
        
        # Create reply message
        reply = Message(
            sender=request.user,
            recipient=original_message.sender,
            subject=subject,
            content=content,
            is_reply=True,
            parent_message=original_message,
            handled_by=request.user,
            date_sent=timezone.now()
        )
        reply.save()
        
        # Mark original as read
        original_message.is_read = True
        original_message.handled_by = request.user
        original_message.save()
        
        django_messages.success(request, 'Reply sent successfully.')
        return redirect('admin:waffrli_message_changelist')
    
    return render(request, 'admin/reply_message.html', {
        'message': original_message,
        'title': f'Reply to: {original_message.subject}'
    })
    




@login_required
def contact_admin(request):
    # Find an admin user
    admin_user = User.objects.filter(is_superuser=True).first()
    if not admin_user:
        messages.error(request, 'No admin available to receive messages.')
        return redirect('inbox')
    
    if request.method == 'POST':
        subject = request.POST.get('subject')
        body = request.POST.get('body')
        
        if not subject or not body:
            messages.error(request, 'Please fill in all fields.')
            return render(request, 'contact_admin.html', {
                'subject': subject,
                'body': body,
                'inbox_count': Message.objects.filter(recipient=request.user).count(),
                'sent_count': Message.objects.filter(sender=request.user).count(),
                'active_tab': 'contact_admin'
            })
        
        # Create message with admin flag
        new_message = Message(
            sender=request.user,
            recipient=admin_user,
            subject=subject,
            content=body,
            for_admin=True
        )
        new_message.save()
        
        messages.success(request, 'Message sent to administrators successfully!')
        return redirect('inbox')
    
    return render(request, 'contact_admin.html', {
        'inbox_count': Message.objects.filter(recipient=request.user).count(),
        'sent_count': Message.objects.filter(sender=request.user).count(),
        'active_tab': 'contact_admin'
    })
    
    
    


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

            product.save()
            
            messages.success(request, "Your deal has been updated successfully!")
            return redirect('product', pk=product_id)
            
        except Exception as e:
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
        messages.error(request, "An error occurred while deleting the deal. Please try again.")
        return redirect('product', pk=product_id)
    
    

def notifications_view(request):
    if not request.user.is_authenticated:
        messages.error(request, "You must be logged in to view notifications.")
        return redirect('login')
    
    notifications = Notification.objects.filter(user=request.user).order_by('-created_at')
    
    # Count unread notifications
    unread_count = notifications.filter(is_read=False).count()
    
    context = {
        'notifications': notifications,
        'unread_count': unread_count,
    }
    
    return render(request, 'notifications.html', context)


@login_required
def mark_notification_unread(request, notification_id):
    try:
        notification = Notification.objects.get(id=notification_id, user=request.user)
        notification.is_read = False
        notification.save()
        return JsonResponse({'status': 'success'})
    except Notification.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Notification not found'}, status=404)

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




def get_notification_count(request):
    if request.user.is_authenticated:
        count = Notification.objects.filter(user=request.user, is_read=False).count()
        return JsonResponse({'count': count})
    else:
        return JsonResponse({'count': 0}, status=403)  


def archive_deal(request, deal_id):
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'You must be logged in to archive deals.'}, status=401)

    try:
        deal = Product.objects.get(id=deal_id, user=request.user, is_archived=False)
        deal.is_archived = True
        deal.archived_at = timezone.now()
        deal.save()
        return JsonResponse({'success': 'Deal archived successfully.'})
    except Product.DoesNotExist:
        return JsonResponse({'error': 'Deal not found or already archived.'}, status=404)




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
    """View for reporting a deal as problematic"""
    if request.method != 'POST':
        return JsonResponse({
            'success': False, 
            'message': 'Invalid request method'
        }, status=405)

    # Get the product or return 404
    try:
        product = Product.objects.get(id=product_id)
    except Product.DoesNotExist:
        return JsonResponse({
            'success': False,
            'message': 'Product not found'
        }, status=404)
    
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
    details = request.POST.get('message', '')
    
    # Validate data
    valid_reasons = [choice[0] for choice in ReportedDeal.REPORT_REASONS]
    if not reason or reason not in valid_reasons:
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
            'message': f"You've already reported this deal with this reason."
        })
    
    # Create the report
    try:
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
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': 'An error occurred while saving your report. Please try again.'
        }, status=500)

