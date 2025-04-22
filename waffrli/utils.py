from .models import WishlistItem, Notification
from django.db.models import Q

def improved_keyword_matching(deal_title, wishlist_keyword):
    """
    Improved algorithm for matching deal titles with wishlist keywords
    
    Args:
        deal_title: String, the title of the deal
        wishlist_keyword: String, the keyword from wishlist
        
    Returns:
        bool: True if there's a match, False otherwise
    """
    # Clean and normalize text
    deal_title = deal_title.lower().strip()
    wishlist_keyword = wishlist_keyword.lower().strip()
    
    # Direct contains check (both ways)
    if wishlist_keyword in deal_title or deal_title in wishlist_keyword:
        return True
    
    # Split into words for more flexible matching
    deal_words = set(deal_title.split())
    keyword_words = set(wishlist_keyword.split())
    
    # Word overlap check
    common_words = deal_words.intersection(keyword_words)
    
    # If wishlist keyword is just 1-2 words, require direct match
    if len(keyword_words) <= 2:
        return len(common_words) == len(keyword_words)
    
    # For longer keywords, be more flexible
    return len(common_words) >= 2  # At least 2 words match
    
def check_deal_against_wishlist(deal):
    """
    Check if a deal matches any wishlist items and create notifications
    
    Args:
        deal: The Product object to check against wishlist items
        
    Returns:
        int: The number of notifications created
    """
    # Don't match wishlist items from the same user who posted the deal
    all_wishlist_items = WishlistItem.objects.exclude(user=deal.user)

    match_count = 0
    for item in all_wishlist_items:
        # Check if there's a keyword match using improved algorithm
        keyword_match = improved_keyword_matching(deal.Name, item.keyword)
        
        # If keywords match, also check price range and category
        if keyword_match:
            # Price match
            try:
                price_match = (
                    float(item.min_price) <= float(deal.sale_price) <= float(item.max_price)
                )
                
                # Category match
                if hasattr(item.category, 'id'):
                    category_match = (item.category.id == deal.category.id)
                else:
                    category_match = (item.category == deal.category.name)
                
                if price_match and category_match:
                    # Create notification
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
                # Skip this item if there's any error in comparison
                continue

    return match_count

# utils.py
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

