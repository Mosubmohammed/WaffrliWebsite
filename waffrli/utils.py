import re
from .models import WishlistItem, Notification, Customer
from django.db.models import Q
from django.db.models import F, Q, Count, Case, When, FloatField, ExpressionWrapper


def improved_keyword_matching(deal_title, wishlist_keyword):
    """

    Returns:
        float: Match score between 0 and 1, higher means better match
    """
    if not deal_title or not wishlist_keyword:
        return 0.0
        
    deal_title = deal_title.lower().strip()
    wishlist_keyword = wishlist_keyword.lower().strip()
    
    if wishlist_keyword in deal_title:
        return 1.0
    
    deal_words = set(re.findall(r'\b\w+\b', deal_title))
    keyword_words = set(re.findall(r'\b\w+\b', wishlist_keyword))
    
    if not keyword_words: 
        return 0.0
        
    common_words = deal_words.intersection(keyword_words)
    
    match_ratio = len(common_words) / len(keyword_words) if keyword_words else 0.0
    
    if len(keyword_words) == 1:
        single_keyword = next(iter(keyword_words), "")
        for word in deal_words:
            if single_keyword in word:
                return 0.8
        return 0.0 
    
    if len(keyword_words) == 2:
        return 1.0 if match_ratio >= 0.95 else 0.0
    elif len(keyword_words) <= 4:
        return match_ratio if match_ratio >= 0.7 else 0.0  
    else:
        return match_ratio if match_ratio >= 0.5 else 0.0
    
def check_deal_against_wishlist(deal):

    all_wishlist_items = WishlistItem.objects.exclude(user=deal.user)
    
    match_count = 0
    for item in all_wishlist_items:
        match_score = improved_keyword_matching(deal.Name, item.keyword)
        
        if match_score >= 0.7:

            try:
                price_match = (
                    float(item.min_price) <= float(deal.sale_price) <= float(item.max_price)
                )
                
                if hasattr(item.category, 'id'):
                    category_match = (item.category.id == deal.category.id)
                else:
                    category_match = (item.category == deal.category.name)
                
                if price_match and category_match:

                    Notification.objects.create(
                        user=item.user,
                        title=f"Deal Match: {item.keyword}",
                        message=f"We found a deal matching your wishlist: {deal.Name} for ${deal.sale_price}",
                        notification_type='deal',
                        wishlist_item=item,
                        related_object_id=deal.id,
                        related_object_type='deal',
                        url=f"/product/{deal.id}",
                    )
                    match_count += 1
            except (TypeError, ValueError, AttributeError):
                continue
    
    return match_count


def get_discount_percentage(price, sale_price):
    """Calculate discount percentage between original price and sale price."""
    if not sale_price or not price or price <= 0:
        return 0
        
    discount = ((price - sale_price) * 100) / price
    return round(discount, 2)

def get_unique_values(queryset, field_name):
    """Get unique values for a field in the queryset."""
    values = queryset.values_list(field_name, flat=True)
    # Filter out None/empty values, strip whitespace, convert to lowercase, and sort
    return sorted(set(value.strip().lower() for value in values if value), 
                  key=lambda x: x.lower())

# utils.py
def get_user_location(request):
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


def add_distances_to_products(products, user_lat, user_lng):
    print(f"Adding distances to {len(products)} products")
    for product in products:
        if product.latitude and product.longitude:
            distance = product.distance_to(user_lat, user_lng)
            product.distance = distance
            print(f"Product {product.id}: distance = {distance} km")
        else:
            product.distance = float('inf')
            print(f"Product {product.id}: No coordinates, setting distance to infinity")
            
            
            
def sort_by_distance(queryset, user_lat, user_lng):
    # Convert to list to perform in-memory calculation
    products_list = list(queryset)
    
    # Calculate distance for each product
    for product in products_list:
        if product.latitude is not None and product.longitude is not None:
            # Store in distance attribute, not overwriting the method
            product.distance = product.distance_to(user_lat, user_lng)
        else:
            product.distance = float('inf')  # Use infinity for missing coordinates

    # Sort by distance
    products_list.sort(key=lambda x: x.distance)
    
    # Convert back to queryset with preserved order
    product_ids = [p.id for p in products_list]
    
    if product_ids:
        preserved_order = Case(*[When(pk=pk, then=pos) for pos, pk in enumerate(product_ids)])
        return queryset.filter(id__in=product_ids).order_by(preserved_order)
    
    return queryset


def is_ajax_request(request):

    return request.headers.get('X-Requested-With') == 'XMLHttpRequest' or 'json' in request.GET