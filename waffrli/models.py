import json
from django.utils import timezone
from django.db.models.signals import post_save
from django.db import models
from django.contrib.auth.models import User
from math import radians, sin, cos, sqrt, atan2
from django.contrib.auth import get_user_model

def get_default_user():
    User = get_user_model()
    return User.objects.first()  # Or create a new default user if needed


    
class Category(models.Model):
    name = models.CharField(max_length=100, db_index=True)
    
    def __str__(self):
        return self.name
    
    class Meta:
        verbose_name_plural = "Categories"
        ordering = ['name']
        

class Customer(models.Model):
    user = models.OneToOneField(User, related_name='customer', on_delete=models.CASCADE, default=get_default_user)
    view_count = models.IntegerField(default=0)
    first_name = models.CharField(max_length=50)
    last_name = models.CharField(max_length=50)
    phone = models.CharField(max_length=10)
    email = models.EmailField(max_length=100)
    password = models.CharField(max_length=50)
    gender = models.CharField(max_length=1, choices=[
        ('M', 'Male'), ('F', 'Female')
    ])

    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    formatted_address = models.CharField(max_length=255, null=True, blank=True)
    date_modified = models.DateTimeField(auto_now=True)
    # image = models.ImageField(upload_to='uploads/product', null=True, blank=True)
    image = models.ImageField(upload_to='static\img\CustomerPics', null=True, blank=True)
    likes = models.ManyToManyField(User, related_name="Customer_like", blank=True)
    saved_products = models.ManyToManyField('Product', related_name="saved_by_customers", blank=True)
    
    def __str__(self):
        return f"{self.first_name} {self.last_name}"

    def number_of_likes(self):
        return self.likes.count()
    
    
    
    
    
class Product(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    Name = models.CharField(max_length=255)
    Dealurl = models.URLField(unique=True,max_length=2000)
    sale_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    Price = models.DecimalField(max_digits=10, decimal_places=2)
    Description = models.TextField()
    store = models.CharField(max_length=55)
    brand = models.CharField(max_length=55)
    category = models.ForeignKey('Category', on_delete=models.CASCADE)
    city = models.CharField(max_length=255)
    # image = models.ImageField(upload_to='uploads/product/', null=True, blank=True)
    image = models.ImageField(upload_to='static\img\ProductPics', null=True, blank=True)
    customer_pic_id = models.ForeignKey('Customer', on_delete=models.SET_NULL, null=True, blank=True, default=None)
    likes = models.ManyToManyField(User, related_name="Product_like", blank=True)
    views = models.IntegerField(default=0)
    create_at = models.DateTimeField(default=timezone.now)
    expires_at = models.DateTimeField(null=True, blank=True)
    is_archived = models.BooleanField(default=False)
    
    store_type = models.CharField(max_length=10, choices=[
        ('online', 'Online Store'),
        ('physical', 'Physical Store')
    ], default='online')
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    formatted_address = models.CharField(max_length=255, null=True, blank=True)
    

    
    def increment_views(self):
        self.views += 1
        self.save(update_fields=['views']) 
    
    def is_expired(self):
        if not self.expires_at:
            return False
        return timezone.now() >= self.expires_at
        
    def __str__(self) -> str:
        return self.Name
        
    def number_of_likes(self):
        return self.likes.count()
        

    def get_discount_percentage(self):
        """Calculate discount percentage if sale_price exists"""
        if not self.sale_price or self.Price == 0:
            return 0
            
        discount = ((self.Price - self.sale_price) / self.Price) * 100
        return round(discount, 2)
        
    def is_hot_deal(self):
        return self.get_discount_percentage() >= 70
        
    def get_savings_amount(self):
        if not self.sale_price:
            return 0
        return self.Price - self.sale_price
    

    def distance_to(self, user_lat, user_lng):
        """Calculate distance in kilometers between this product's location and a user location"""
        if not self.latitude or not self.longitude or not user_lat or not user_lng:
            return float('inf')
            
        R = 6371  # Earth radius in kilometers
            
        # Convert latitude/longitude from degrees to radians
        lat1 = radians(self.latitude)
        lon1 = radians(self.longitude)
        lat2 = radians(user_lat)
        lon2 = radians(user_lng)
            
        # Haversine formula
        dlon = lon2 - lon1
        dlat = lat2 - lat1
        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
        c = 2 * atan2(sqrt(a), sqrt(1-a))
        distance = R * c
            
        return round(distance, 2)
    
        
    class Meta:
        indexes = [
            models.Index(fields=['sale_price', 'Price']), 
            models.Index(fields=['views', '-create_at']),  
            models.Index(fields=['store', 'city', 'brand']),  
            models.Index(fields=['category', 'sale_price']),  
            models.Index(fields=['store_type']), 
            models.Index(fields=['latitude', 'longitude']),  
        ]
        ordering = ['-create_at']  




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
    date_sent = models.DateTimeField(default=timezone.now)
    is_read = models.BooleanField(default=False)
    is_reply = models.BooleanField(default=False)
    parent_message = models.ForeignKey('self', null=True, blank=True, related_name='replies', on_delete=models.SET_NULL)
    # New field to flag messages for admin attention
    for_admin = models.BooleanField(default=False)
    # Admin who handled the message (if applicable)
    handled_by = models.ForeignKey(User, null=True, blank=True, related_name='handled_messages', on_delete=models.SET_NULL)

    def __str__(self):
        return f"{self.subject} - From: {self.sender.username} To: {self.recipient.username}"

    class Meta:
        ordering = ['-date_sent']
        
        
    
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
        


class ReportedDeal(models.Model):
    REPORT_REASONS = (
        ('expired', 'Expired'),
        ('spam', 'Spam'),
        ('repost', 'Repost'),
        ('troll', 'Troll'),
        ('other', 'Other')
    )
    
    STATUS_CHOICES = (
        ('pending', 'Pending Review'),
        ('approved', 'Report Approved'),
        ('rejected', 'Report Rejected'),
        ('resolved', 'Issue Resolved')
    )
    
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='reports')
    reporter = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='reported_deals')
    reason = models.CharField(max_length=20, choices=REPORT_REASONS)
    details = models.TextField(blank=True, help_text="Additional details about the report")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    admin_notes = models.TextField(blank=True, help_text="Admin notes on resolution")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Report on {self.product.Name} by {self.reporter.first_name} {self.reporter.last_name} - {self.get_reason_display()}"
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = "Reported Deal"
        verbose_name_plural = "Reported Deals"
        # Prevent multiple reports for the same reason by the same user
        unique_together = ('product', 'reporter', 'reason')