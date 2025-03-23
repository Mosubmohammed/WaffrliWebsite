import json
from django.utils import timezone
from django.db.models.signals import post_save
from django.db import models
from django.contrib.auth.models import User
from django.dispatch import receiver
# Create your models here.

from django.contrib.auth import get_user_model

def get_default_user():
    User = get_user_model()
    return User.objects.first()  # Or create a new default user if needed

class FirebaseUser(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    firebase_uid = models.CharField(max_length=128, unique=True)
    email_verified = models.BooleanField(default=False)
    
    def __str__(self):
        return self.user.username
    
class Category(models.Model):
    name=models.CharField(max_length=100)
    def __str__(self) -> str:
        return self.name
    class Meta:
        verbose_name_plural='Categories'
        

class Customer(models.Model):
    user = models.OneToOneField(User, related_name='customer', on_delete=models.CASCADE, default=get_default_user)
    view_count = models.IntegerField(default=0)
    first_name = models.CharField(max_length=50)
    last_name = models.CharField(max_length=50)
    phone = models.CharField(max_length=10)
    email = models.EmailField(max_length=100)
    password = models.CharField(max_length=50)
    gender = models.CharField(max_length=1, choices=[
        ('M', 'Male'), ('F', 'Female'), ('O', 'Other'), ('N', 'Prefer not to say')
    ], default='N')
    address = models.CharField(max_length=100)
    City = models.CharField(max_length=100)
    date_modified = models.DateTimeField(auto_now=True)
    image = models.ImageField(upload_to='uploads/product', null=True, blank=True)
    likes=models.ManyToManyField(User, related_name="Customer_like",blank=True)
    saved_products = models.ManyToManyField('Product', related_name="saved_by_customers", blank=True)

    def __str__(self):
        return f"{self.first_name} {self.last_name}"

    def number_of_likes(self):
            return self.likes.count()
    
    
    
    
    
class Product(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    Name = models.CharField(max_length=255)
    Dealurl = models.URLField(unique=True)
    sale_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    Price = models.DecimalField(max_digits=10, decimal_places=2)
    Description = models.TextField()
    store = models.CharField(max_length=55)
    brand = models.CharField(max_length=55)
    category = models.ForeignKey('Category', on_delete=models.CASCADE)
    city = models.CharField(max_length=255)
    image = models.ImageField(upload_to='uploads/product/', null=True, blank=True)
    customer_pic_id = models.ForeignKey('Customer', on_delete=models.SET_NULL, null=True, blank=True, default=None)
    likes = models.ManyToManyField(User, related_name="Product_like", blank=True)
    views = models.IntegerField(default=0)
    create_at = models.DateTimeField(default=timezone.now)

    def increment_views(self):
        self.views += 1
        self.save()
        
    def __str__(self) -> str:
        return self.Name
    
    def number_of_likes(self):
        return self.likes.count()
    
    # New methods for hot deals functionality
    def get_discount_percentage(self):
        """Calculate discount percentage if sale_price exists"""
        if not self.sale_price or self.Price == 0:
            return 0
        
        discount = ((self.Price - self.sale_price) / self.Price) * 100
        return round(discount, 2)
    
    def is_hot_deal(self):
        """Check if product qualifies as a hot deal (discount >= 70%)"""
        return self.get_discount_percentage() >= 70
    
    def get_savings_amount(self):
        """Calculate amount saved"""
        if not self.sale_price:
            return 0
        return self.Price - self.sale_price




class Comment(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='comments')
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    text = models.TextField()
    timestamp = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"Comment by {self.customer.first_name} on {self.product.Name}"



class Follow(models.Model):
    follower = models.ForeignKey(User, related_name="following", on_delete=models.CASCADE)
    following = models.ForeignKey(User, related_name="followers", on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('follower', 'following')  # Prevent duplicate follows

    def __str__(self):
        return f"{self.follower.username} follows {self.following.username}"
    

class Message(models.Model):
    sender = models.ForeignKey(User, related_name='sent_messages', on_delete=models.CASCADE)
    recipient = models.ForeignKey(User, related_name='received_messages', on_delete=models.CASCADE)
    subject = models.CharField(max_length=255)
    content = models.TextField()
    date_sent = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)
    is_reply = models.BooleanField(default=False)
    parent_message = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='replies')

    
    def __str__(self):
        return f"{self.subject} - From: {self.sender} To: {self.recipient}"
    
class WishlistItem(models.Model):

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    keyword = models.CharField(max_length=100)
    min_price = models.DecimalField(max_digits=10, decimal_places=2)
    max_price = models.DecimalField(max_digits=10, decimal_places=2)
    category = models.CharField(max_length=50, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.keyword} - {self.user.username}"
    
    class Meta:
        ordering = ['-created_at']

class Notification(models.Model):

    NOTIFICATION_TYPES = (
        ('deal', 'Deal Match'),
        ('info', 'Information'),
        ('alert', 'Alert'),
    )
    
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    title = models.CharField(max_length=200)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    notification_type = models.CharField(max_length=20, choices=NOTIFICATION_TYPES, default='info')
    wishlist_item = models.ForeignKey(WishlistItem, on_delete=models.SET_NULL, null=True, blank=True)
    related_object_type = models.CharField(max_length=50, blank=True)
    related_object_id = models.IntegerField(null=True, blank=True)
    url = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.title} - {self.user.username}"
    
    class Meta:
        ordering = ['-created_at']
        
# @receiver(post_save, sender=Product)
# def check_for_matching_wishlist_items(sender, instance, created, **kwargs):
#     """
#     Signal handler to check for matching wishlist items whenever a new Product is created
#     """
#     if created:  # Only run when a new product is created, not on updates
#         # Import here to avoid circular imports
#         from .utils import improved_keyword_matching
        
#         # Don't match wishlist items from the same user who posted the deal
#         all_wishlist_items = WishlistItem.objects.exclude(user=instance.user)
        
#         matching_items = []
#         for item in all_wishlist_items:
#             # Check if there's a keyword match using improved algorithm
#             keyword_match = improved_keyword_matching(instance.Name, item.keyword)
            
#             # If keywords match, also check price range and category
#             if keyword_match:
#                 # Price match (using sale_price)
#                 price_match = (
#                     float(item.min_price) <= float(instance.sale_price) <= float(item.max_price)
#                 )
                
#                 # Category match
#                 category_match = (item.category.id == instance.category.id)
                
#                 if price_match and category_match:
#                     # Create notification
#                     Notification.objects.create(
#                         user=item.user,
#                         title=f"Deal Match: {item.keyword}",
#                         message=f"We found a deal matching your wishlist: {instance.Name} for ${instance.sale_price}",
#                         notification_type='deal',
#                         wishlist_item=item,
#                         related_object_id=instance.id,
#                         related_object_type='deal',
#                         url=f"/product/{instance.id}",
#                     )