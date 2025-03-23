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
    print(f"DEBUG: Starting wishlist check for deal: {deal.Name}, price: ${deal.sale_price}, category: {deal.category.name}")
    
    # Don't match wishlist items from the same user who posted the deal
    all_wishlist_items = WishlistItem.objects.exclude(user=deal.user)
    print(f"DEBUG: Found {all_wishlist_items.count()} potential wishlist items from other users")
    
    matching_items = []
    for item in all_wishlist_items:
        print(f"DEBUG: Checking wishlist item: {item.keyword}, price range: ${item.min_price}-${item.max_price}, category: {item.category.name}")
        
        # Check if there's a keyword match using improved algorithm
        keyword_match = improved_keyword_matching(deal.Name, item.keyword)
        print(f"DEBUG:   - Keyword match: {keyword_match}")
        
        # If keywords match, also check price range and category
        if keyword_match:
            # Price match (using sale_price)
            price_match = (
                float(item.min_price) <= float(deal.sale_price) <= float(item.max_price)
            )
            print(f"DEBUG:   - Price match: {price_match}")
            
            # Category match
            category_match = (item.category == deal.category)
            print(f"DEBUG:   - Category match: {category_match}")
            
            if price_match and category_match:
                matching_items.append(item)
                print(f"DEBUG:   - OVERALL MATCH!")
    
    # Create notifications for all matches
    notification_count = 0
    for item in matching_items:
        print(f"DEBUG: Creating notification for user: {item.user.username}")
        create_deal_match_notification(item, deal)
        notification_count += 1
    
    print(f"DEBUG: Created {notification_count} notifications")
    return notification_count

def create_deal_match_notification(wishlist_item, deal):
    """
    Create a notification for a user when a deal matches their wishlist item
    
    Args:
        wishlist_item: The WishlistItem that matched
        deal: The Product that matched the wishlist item
    
    Returns:
        Notification: The created notification object
    """
    notification = Notification(
        user=wishlist_item.user,
        title=f"Deal Match: {wishlist_item.keyword}",
        message=f"We found a deal matching your wishlist: {deal.Name} for ${deal.sale_price}",
        notification_type='deal',
        wishlist_item=wishlist_item,
        related_object_id=deal.id,
        related_object_type='deal',
        url=f"/product/{deal.id}",  # Using your URL structure for product detail page
    )
    notification.save()
    return notification

def debug_wishlist_matching(deal):
    """
    Debug function to output detailed matching information for a deal
    
    Args:
        deal: A Product instance to test against wishlist items
        
    Returns:
        dict: Detailed matching information
    """
    # Don't match wishlist items from the same user who posted the deal
    all_wishlist_items = WishlistItem.objects.exclude(user=deal.user)
    
    results = {
        'deal': {
            'id': deal.id,
            'name': deal.Name,
            'sale_price': float(deal.sale_price),
            'category': deal.category.name,
            'posted_by': deal.user.username,
        },
        'potential_matches': [],
        'matches': [],
    }
    
    for item in all_wishlist_items:
        # Create a detailed analysis for each wishlist item
        item_analysis = {
            'id': item.id,
            'user': item.user.username,
            'keyword': item.keyword,
            'min_price': float(item.min_price),
            'max_price': float(item.max_price),
            'category': item.category.name,
            'keyword_match': False,
            'price_match': False,
            'category_match': False,
            'overall_match': False,
        }
        
        # Check keyword match
        item_analysis['keyword_match'] = improved_keyword_matching(deal.Name, item.keyword)
        
        # Check price match
        item_analysis['price_match'] = (
            float(item.min_price) <= float(deal.sale_price) <= float(item.max_price)
        )
        
        # Check category match
        item_analysis['category_match'] = (item.category == deal.category)
        
        # Overall match
        item_analysis['overall_match'] = (
            item_analysis['keyword_match'] and 
            item_analysis['price_match'] and 
            item_analysis['category_match']
        )
        
        # Add to appropriate result list
        results['potential_matches'].append(item_analysis)
        
        if item_analysis['overall_match']:
            results['matches'].append(item_analysis)
    
    print(f"DEBUG: Deal '{deal.Name}' ({deal.id}) matching results:")
    print(f"  - Found {len(results['matches'])} matches out of {len(results['potential_matches'])} potential wishlist items")
    for match in results['matches']:
        print(f"  - MATCH: '{match['keyword']}' (User: {match['user']}, Price: ${match['min_price']}-${match['max_price']}, Category: {match['category']})")
    
    return results