from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone
from django.db.models import Count
from .models import (
    FirebaseUser, Category, Customer, Product, Comment, 
    Follow, Message, WishlistItem, Notification, ReportedDeal
)

# FirebaseUser Admin
@admin.register(FirebaseUser)
class FirebaseUserAdmin(admin.ModelAdmin):
    list_display = ('user', 'firebase_uid', 'email_verified')
    search_fields = ('user__username', 'user__email', 'firebase_uid')
    list_filter = ('email_verified',)
    raw_id_fields = ('user',)

# Category Admin
@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'product_count')
    search_fields = ('name',)
    
    def product_count(self, obj):
        return obj.product_set.count()
    product_count.short_description = 'Products'

# Customer Admin
@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ('id', 'full_name', 'email', 'phone', 'gender', 'view_count', 'like_count', 'date_modified')
    list_filter = ('gender', 'date_modified')
    search_fields = ('first_name', 'last_name', 'email', 'phone')
    readonly_fields = ('date_modified', 'view_count')
    raw_id_fields = ('user', 'likes', 'saved_products')
    
    fieldsets = (
        ('User Information', {
            'fields': ('user', 'first_name', 'last_name', 'email', 'phone', 'password', 'gender')
        }),
        ('Location', {
            'fields': ('latitude', 'longitude', 'formatted_address')
        }),
        ('Profile', {
            'fields': ('image',)
        }),
        ('Engagement', {
            'fields': ('view_count', 'likes', 'saved_products')
        }),
        ('Timestamps', {
            'fields': ('date_modified',),
            'classes': ('collapse',)
        }),
    )
    
    def full_name(self, obj):
        return f"{obj.first_name} {obj.last_name}"
    full_name.short_description = 'Name'
    
    def like_count(self, obj):
        return obj.likes.count()
    like_count.short_description = 'Likes'

# Product Admin
@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('id', 'Name', 'category_link', 'store', 'brand', 'price_display', 
                   'discount_display', 'views', 'likes_count', 'city', 'store_type', 'is_archived', 'created_date', 'expires_display')
    list_filter = ('category', 'store', 'brand', 'store_type', 'is_archived', 'create_at')
    search_fields = ('Name', 'Description', 'store', 'brand', 'city')
    readonly_fields = ('views', 'create_at', 'is_hot_deal', 'get_discount_percentage', 'get_savings_amount')
    list_editable = ('is_archived',)
    raw_id_fields = ('user', 'customer_pic_id', 'likes')
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('Name', 'Description', 'category', 'brand', 'store')
        }),
        ('Pricing', {
            'fields': ('Price', 'sale_price', 'get_discount_percentage', 'get_savings_amount', 'is_hot_deal')
        }),
        ('Deal Details', {
            'fields': ('Dealurl', 'user', 'customer_pic_id', 'image')
        }),
        ('Location', {
            'fields': ('store_type', 'city', 'latitude', 'longitude', 'formatted_address')
        }),
        ('Engagement', {
            'fields': ('views', 'likes')
        }),
        ('Timestamps', {
            'fields': ('create_at', 'expires_at', 'is_archived'),
        }),
    )
    
    def price_display(self, obj):
        if obj.sale_price:
            return format_html('<strike>${}</strike> <span style="color: green">${}</span>', 
                              obj.Price, obj.sale_price)
        return f"${obj.Price}"
    price_display.short_description = 'Price'
    
    def discount_display(self, obj):
        discount = obj.get_discount_percentage()
        if discount > 0:
            return format_html('<span style="color: {}; font-weight: bold">{}%</span>', 
                              'red' if discount >= 70 else 'green', 
                              discount)
        return "-"
    discount_display.short_description = 'Discount'
    
    def category_link(self, obj):
        return format_html('<a href="/admin/your_app/category/{}/change/">{}</a>', 
                          obj.category.id, obj.category.name)
    category_link.short_description = 'Category'
    category_link.admin_order_field = 'category__name'
    
    def created_date(self, obj):
        return obj.create_at.strftime("%Y-%m-%d")
    created_date.short_description = 'Created'
    created_date.admin_order_field = 'create_at'
    
    def expires_display(self, obj):
        if obj.expires_at:
            now = timezone.now()
            if obj.expires_at < now:
                return format_html('<span style="color: red">Expired</span>')
            return obj.expires_at.strftime("%Y-%m-%d")
        return "-"
    expires_display.short_description = 'Expires'
    
    def likes_count(self, obj):
        return obj.likes.count()
    likes_count.short_description = 'Likes'
    
    # Admin actions
    actions = ['mark_as_archived', 'mark_as_active']
    
    def mark_as_archived(self, request, queryset):
        queryset.update(is_archived=True)
    mark_as_archived.short_description = "Mark selected products as archived"
    
    def mark_as_active(self, request, queryset):
        queryset.update(is_archived=False)
    mark_as_active.short_description = "Mark selected products as active"

# Comment Admin
@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ('id', 'truncated_text', 'product_link', 'customer_link', 'timestamp')
    list_filter = ('timestamp',)
    search_fields = ('text', 'product__Name', 'customer__first_name', 'customer__last_name')
    readonly_fields = ('timestamp',)
    
    def truncated_text(self, obj):
        return obj.text[:50] + "..." if len(obj.text) > 50 else obj.text
    truncated_text.short_description = 'Comment'
    
    def product_link(self, obj):
        return format_html('<a href="/admin/your_app/product/{}/change/">{}</a>', 
                          obj.product.id, obj.product.Name)
    product_link.short_description = 'Product'
    
    def customer_link(self, obj):
        return format_html('<a href="/admin/your_app/customer/{}/change/">{} {}</a>', 
                          obj.customer.id, obj.customer.first_name, obj.customer.last_name)
    customer_link.short_description = 'Customer'

# Follow Admin
@admin.register(Follow)
class FollowAdmin(admin.ModelAdmin):
    list_display = ('id', 'follower_display', 'following_display', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('follower__username', 'following__username')
    readonly_fields = ('created_at',)
    
    def follower_display(self, obj):
        return format_html('<a href="/admin/auth/user/{}/change/">{}</a>', 
                          obj.follower.id, obj.follower.username)
    follower_display.short_description = 'Follower'
    
    def following_display(self, obj):
        return format_html('<a href="/admin/auth/user/{}/change/">{}</a>', 
                          obj.following.id, obj.following.username)
    following_display.short_description = 'Following'

# Message Admin
@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ('id', 'subject', 'sender_display', 'recipient_display', 'date_sent', 'is_read', 'is_reply')
    list_filter = ('is_read', 'is_reply', 'date_sent')
    search_fields = ('subject', 'content', 'sender__username', 'recipient__username')
    readonly_fields = ('date_sent',)
    
    fieldsets = (
        ('Message Information', {
            'fields': ('sender', 'recipient', 'subject', 'content')
        }),
        ('Status', {
            'fields': ('is_read', 'is_reply', 'parent_message')
        }),
        ('Timestamps', {
            'fields': ('date_sent',),
            'classes': ('collapse',)
        }),
    )
    
    def sender_display(self, obj):
        return format_html('<a href="/admin/auth/user/{}/change/">{}</a>', 
                          obj.sender.id, obj.sender.username)
    sender_display.short_description = 'Sender'
    
    def recipient_display(self, obj):
        return format_html('<a href="/admin/auth/user/{}/change/">{}</a>', 
                          obj.recipient.id, obj.recipient.username)
    recipient_display.short_description = 'Recipient'
    
    # Admin actions
    actions = ['mark_as_read', 'mark_as_unread']
    
    def mark_as_read(self, request, queryset):
        queryset.update(is_read=True)
    mark_as_read.short_description = "Mark selected messages as read"
    
    def mark_as_unread(self, request, queryset):
        queryset.update(is_read=False)
    mark_as_unread.short_description = "Mark selected messages as unread"

# WishlistItem Admin
@admin.register(WishlistItem)
class WishlistItemAdmin(admin.ModelAdmin):
    list_display = ('id', 'keyword', 'user_display', 'price_range', 'category', 'created_at')
    list_filter = ('category', 'created_at')
    search_fields = ('keyword', 'user__username', 'category')
    readonly_fields = ('created_at', 'updated_at')
    
    def user_display(self, obj):
        return format_html('<a href="/admin/auth/user/{}/change/">{}</a>', 
                          obj.user.id, obj.user.username)
    user_display.short_description = 'User'
    
    def price_range(self, obj):
        return f"${obj.min_price} - ${obj.max_price}"
    price_range.short_description = 'Price Range'

# Notification Admin
@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('id', 'title', 'user_display', 'notification_type', 'is_read', 'created_at')
    list_filter = ('notification_type', 'is_read', 'created_at')
    search_fields = ('title', 'message', 'user__username')
    readonly_fields = ('created_at',)
    
    fieldsets = (
        ('Notification Information', {
            'fields': ('user', 'title', 'message', 'notification_type')
        }),
        ('Status', {
            'fields': ('is_read',)
        }),
        ('Related Information', {
            'fields': ('wishlist_item', 'related_object_type', 'related_object_id', 'url')
        }),
        ('Timestamps', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )
    
    def user_display(self, obj):
        return format_html('<a href="/admin/auth/user/{}/change/">{}</a>', 
                          obj.user.id, obj.user.username)
    user_display.short_description = 'User'
    
    # Admin actions
    actions = ['mark_as_read', 'mark_as_unread']
    
    def mark_as_read(self, request, queryset):
        queryset.update(is_read=True)
    mark_as_read.short_description = "Mark selected notifications as read"
    
    def mark_as_unread(self, request, queryset):
        queryset.update(is_read=False)
    mark_as_unread.short_description = "Mark selected notifications as unread"

# ReportedDeal Admin
@admin.register(ReportedDeal)
class ReportedDealAdmin(admin.ModelAdmin):
    list_display = ('id', 'product_name', 'reporter_name', 'reason_display', 'status_badge', 
                   'created_at', 'updated_at')
    list_filter = ('status', 'reason', 'created_at')
    search_fields = ('product__Name', 'reporter__first_name', 'reporter__last_name', 'details', 'admin_notes')
    readonly_fields = ('created_at', 'updated_at')
    
    # Custom fields for better display
    fieldsets = (
        ('Report Information', {
            'fields': ('product', 'reporter', 'reason', 'details')
        }),
        ('Status Information', {
            'fields': ('status', 'admin_notes')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    # Actions
    actions = ['mark_as_approved', 'mark_as_rejected', 'mark_as_resolved']
    
    def product_name(self, obj):
        """Display product name with a link to the product admin page"""
        return format_html('<a href="/admin/your_app/product/{}/change/">{}</a>', 
                          obj.product.id, obj.product.Name)
    product_name.short_description = 'Product'
    product_name.admin_order_field = 'product__Name'
    
    def reporter_name(self, obj):
        """Display reporter name with a link to the customer admin page"""
        return format_html('<a href="/admin/your_app/customer/{}/change/">{} {}</a>',
                         obj.reporter.id, obj.reporter.first_name, obj.reporter.last_name)
    reporter_name.short_description = 'Reporter'
    reporter_name.admin_order_field = 'reporter__last_name'
    
    def reason_display(self, obj):
        """Display the human-readable reason"""
        return obj.get_reason_display()
    reason_display.short_description = 'Reason'
    reason_display.admin_order_field = 'reason'
    
    def status_badge(self, obj):
        """Display status as a colored badge"""
        colors = {
            'pending': 'orange',
            'approved': 'red',
            'rejected': 'green',
            'resolved': 'blue'
        }
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 7px; '
            'border-radius: 8px;">{}</span>',
            colors.get(obj.status, 'gray'),
            obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    status_badge.admin_order_field = 'status'
    
    # Admin actions
    def mark_as_approved(self, request, queryset):
        queryset.update(status='approved')
    mark_as_approved.short_description = "Mark selected reports as approved"
    
    def mark_as_rejected(self, request, queryset):
        queryset.update(status='rejected')
    mark_as_rejected.short_description = "Mark selected reports as rejected"
    
    def mark_as_resolved(self, request, queryset):
        queryset.update(status='resolved')
    mark_as_resolved.short_description = "Mark selected reports as resolved"