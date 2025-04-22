
from django.db.models import Count, Q
from django.utils import timezone

class ProductFilter:
    """
    Filter class for Product model that processes filter parameters from request.
    Updated to include additional filters based on the Product model.
    """
    
    def __init__(self, query_params, queryset, request=None):
        self.queryset = queryset
        self.query_params = query_params
        self.request = request
        self.qs = self.apply_filters()
    
    def apply_filters(self):
        """Apply all filters to the base queryset."""
        queryset = self.queryset
        
        # Filter out expired and archived products by default
        queryset = self.filter_active_products(queryset)
        
        # Apply store filter
        queryset = self.filter_by_store(queryset)
        
        # Apply store type filter
        queryset = self.filter_by_store_type(queryset)
        
        # Apply location filter
        queryset = self.filter_by_location(queryset)
        
        # Apply brand filter
        queryset = self.filter_by_brand(queryset)
        
        # Apply price range filters
        queryset = self.filter_by_price_range(queryset)
        
        # Apply rating/likes filter
        queryset = self.filter_by_likes(queryset)
        
        return queryset
    
    def filter_active_products(self, queryset):
        """Filter out expired and archived products."""
        # Check if we should include expired/archived products
        include_expired = self.query_params.get('include_expired') == 'true'
        
        if not include_expired:
            # Filter out expired products
            queryset = queryset.filter(
                Q(expires_at__isnull=True) | Q(expires_at__gt=timezone.now())
            )
            
        return queryset
    
    def filter_by_store(self, queryset):
        """Filter by store name (case-insensitive)."""
        stores = self.query_params.getlist('store')
        if stores:
            query = Q()
            for store in stores:
                clean_store = store.strip().lower()
                query |= Q(store__iexact=clean_store)
            return queryset.filter(query)
        return queryset
    
    def filter_by_store_type(self, queryset):
        """Filter by store type (online or physical)."""
        store_type = self.query_params.get('store_type')
        if store_type and store_type in ['online', 'physical']:
            return queryset.filter(store_type=store_type)
        return queryset
    
    def filter_by_location(self, queryset):
        """Filter by city/location (case-insensitive)."""
        locations = self.query_params.getlist('location')
        if locations:
            query = Q()
            for location in locations:
                query |= Q(city__iexact=location.strip())
            return queryset.filter(query)
        return queryset
    
    def filter_by_brand(self, queryset):
        """Filter by brand (case-insensitive)."""
        brands = self.query_params.getlist('brand')
        if brands:
            query = Q()
            for brand in brands:
                query |= Q(brand__iexact=brand.strip())
            return queryset.filter(query)
        return queryset
    
    def filter_by_price_range(self, queryset):
        """Filter by min and max price."""
        min_price = self.query_params.get('min_price')
        max_price = self.query_params.get('max_price')
        
        # Store filtered products before max_price
        store_filtered_products = None
        stores = self.query_params.getlist('store')
        
        if min_price:
            try:
                min_price_value = float(min_price)
                queryset = queryset.filter(sale_price__gte=min_price_value)
            except (ValueError, TypeError):
                pass
        
        # If filtering by store, save the products before applying max_price
        if stores and max_price:
            store_filtered_products = queryset
        
        if max_price:
            try:
                max_price_value = float(max_price)
                queryset = queryset.filter(sale_price__lte=max_price_value)
            except (ValueError, TypeError):
                pass
        
        # If filtering by store and have fewer than 2 products after price filtering,
        # restore the original store-filtered products
        if stores and store_filtered_products and queryset.count() < 2 and store_filtered_products.count() >= 2:
            queryset = store_filtered_products
        
        return queryset
    
    def filter_by_likes(self, queryset):
        """Filter by minimum number of likes."""
        rating = self.query_params.get('rating')
        if rating and rating != '0':
            try:
                rating_value = int(rating)
                return queryset.annotate(like_count=Count('likes')).filter(like_count__gte=rating_value)
            except (ValueError, TypeError):
                pass
        return queryset