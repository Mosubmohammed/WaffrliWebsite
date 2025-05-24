from django.db.models.signals import pre_save
from django.dispatch import receiver
from django.utils.html import strip_tags
from .models import ReportedDeal, Notification, Product , Category
from django.db.models.signals import pre_delete
from django.core.cache import cache
from django.db.models.signals import post_save, post_delete
from django.utils import timezone


@receiver(pre_save, sender=ReportedDeal)
def create_report_status_notification(sender, instance, **kwargs):

    if instance.pk is None:
        return
        
    try:
        original_report = ReportedDeal.objects.get(pk=instance.pk)
    except ReportedDeal.DoesNotExist:
        return 
    
    if original_report.status == instance.status:
        return

    status_display = dict(ReportedDeal.STATUS_CHOICES).get(instance.status)
    

    user = instance.reporter.user
    product_name = instance.product.Name
    

    if instance.status == 'approved':
        title = f"Report Approved: {product_name}"
        message = f"Your report about '{product_name}' has been reviewed and approved. Thank you for helping us maintain quality listings."
    elif instance.status == 'rejected':
        title = f"Report Rejected: {product_name}"
        message = f"Your report about '{product_name}' has been reviewed and was not approved."
    elif instance.status == 'resolved':
        title = f"Issue Resolved: {product_name}"
        message = f"The issue you reported about '{product_name}' has been resolved. Thank you for your feedback!"
    else:
        title = f"Report Status Update: {product_name}"
        message = f"The status of your report for '{product_name}' has been updated to '{status_display}'."
    

    if instance.admin_notes:

        clean_notes = strip_tags(instance.admin_notes)
        message += f"\n\nAdmin comments: {clean_notes}"

    Notification.objects.create(
        user=user,
        title=title,
        message=message,
        notification_type='alert',
        related_object_type='reported_deal',
        related_object_id=instance.pk,
        url=f'/product/{instance.product.id}/' 
    )
    
    if instance.status == 'resolved' and original_report.status != 'resolved':
        owner = instance.product.user
        if owner:
            owner_title = f"Your Post Has Been Reviewed: {product_name}"
            owner_message = f"Your post '{product_name}' was reported and has been reviewed by our team."
            
            if instance.admin_notes:
                clean_notes = strip_tags(instance.admin_notes)
                owner_message += f"\n\nAdmin comments: {clean_notes}"
            
            Notification.objects.create(
                user=owner,
                title=owner_title,
                message=owner_message,
                notification_type='alert',
                related_object_type='reported_deal',
                related_object_id=instance.pk,
                url=f'/product/{instance.product.id}/'
            )

@receiver(post_save, sender=Product)
def clear_cache_on_product_save(sender, instance, **kwargs):
    """Clear cache when a product is created or updated"""
    cache.delete('total_product_count')
    
    # Clear time-based cache keys
    current_time = timezone.now()
    current_hour = current_time.strftime('%Y%m%d%H')
    prev_hour = (current_time.replace(hour=current_time.hour-1)).strftime('%Y%m%d%H')
    current_day = current_time.strftime('%Y%m%d')
    
    # Delete relevant cache keys
    cache.delete(f'products_list_{current_hour}')
    cache.delete(f'products_list_{prev_hour}')
    cache.delete(f'popular_products_{current_day}')
    cache.delete(f'category_products_{current_hour}')
    cache.delete(f'category_products_{prev_hour}')
    
    print(f"Cache cleared due to Product save: {instance.Name}")

@receiver(post_delete, sender=Product)
def clear_cache_on_product_delete(sender, instance, **kwargs):
    """Clear cache when a product is deleted"""
    cache.delete('total_product_count')
    current_time = timezone.now()
    current_hour = current_time.strftime('%Y%m%d%H')
    current_day = current_time.strftime('%Y%m%d')
    
    cache.delete(f'products_list_{current_hour}')
    cache.delete(f'popular_products_{current_day}')
    cache.delete(f'category_products_{current_hour}')
    
    print(f"Cache cleared due to Product deletion: {instance.Name}")

@receiver(post_save, sender=Category)
def clear_cache_on_category_save(sender, instance, **kwargs):
    """Clear cache when a category is modified"""
    current_time = timezone.now()
    current_hour = current_time.strftime('%Y%m%d%H')
    cache.delete(f'category_products_{current_hour}')
    
    print(f"Cache cleared due to Category save: {instance.name}")