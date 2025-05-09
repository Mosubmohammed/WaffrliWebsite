import re
from .models import WishlistItem, Notification
from django.db.models import Q

def improved_keyword_matching(deal_title, wishlist_keyword):
    """
    Advanced algorithm for matching deal titles with wishlist keywords
    
    Args:
        deal_title: String, the title of the deal
        wishlist_keyword: String, the keyword from wishlist
        
    Returns:
        float: Match score between 0 and 1, higher means better match
    """
    if not deal_title or not wishlist_keyword:
        return 0.0
        
    # Clean and normalize text
    deal_title = deal_title.lower().strip()
    wishlist_keyword = wishlist_keyword.lower().strip()
    
    # Direct contains check
    if wishlist_keyword in deal_title:
        return 1.0
    
    # Tokenize into words
    deal_words = set(re.findall(r'\b\w+\b', deal_title))
    keyword_words = set(re.findall(r'\b\w+\b', wishlist_keyword))
    
    if not keyword_words:  # Empty set check
        return 0.0
        
    # Word overlap check
    common_words = deal_words.intersection(keyword_words)
    
    # Calculate match percentage
    match_ratio = len(common_words) / len(keyword_words) if keyword_words else 0.0
    
    # For single word keywords, be more strict
    if len(keyword_words) == 1:
        # Get the single word without using pop() which modifies the set
        single_keyword = next(iter(keyword_words), "")
        
        # Check for partial word match (e.g. "phone" in "smartphone")
        for word in deal_words:
            if single_keyword in word:
                return 0.8
        return 0.0  # No match found
    
    # For multi-word keywords, use a sliding threshold based on length
    if len(keyword_words) == 2:
        return 1.0 if match_ratio >= 0.95 else 0.0
    elif len(keyword_words) <= 4:
        return match_ratio if match_ratio >= 0.7 else 0.0  
    else:
        return match_ratio if match_ratio >= 0.5 else 0.0
    
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
        match_score = improved_keyword_matching(deal.Name, item.keyword)
        
        # Consider a match if score is above threshold (0.7 is a good starting point)
        if match_score >= 0.7:
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

