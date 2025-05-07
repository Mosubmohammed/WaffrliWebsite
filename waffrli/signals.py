from django.db.models.signals import pre_save
from django.dispatch import receiver
from django.utils.html import strip_tags
from .models import ReportedDeal, Notification, Product

@receiver(pre_save, sender=ReportedDeal)
def create_report_status_notification(sender, instance, **kwargs):

    # Check if this is a new report (no notification needed)
    if instance.pk is None:
        return
        
    # Get the original/existing report before changes
    try:
        original_report = ReportedDeal.objects.get(pk=instance.pk)
    except ReportedDeal.DoesNotExist:
        return  # New report, no notification needed
    
    # Only proceed if status has changed
    if original_report.status == instance.status:
        return
    
    # Get status display name (human readable)
    status_display = dict(ReportedDeal.STATUS_CHOICES).get(instance.status)
    
    # Create notification for the reporter
    user = instance.reporter.user
    product_name = instance.product.Name
    
    # Create notification message based on status
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
    
    # Add admin notes if provided
    if instance.admin_notes:
        # Strip any HTML tags for security
        clean_notes = strip_tags(instance.admin_notes)
        message += f"\n\nAdmin comments: {clean_notes}"
    
    # Create the notification
    Notification.objects.create(
        user=user,
        title=title,
        message=message,
        notification_type='alert',
        related_object_type='reported_deal',
        related_object_id=instance.pk,
        url=f'/product/{instance.product.id}/'  # Link to the product page
    )
    
    # If report is approved and the issue is resolved, notify the post owner as well
    if instance.status == 'resolved' and original_report.status != 'resolved':
        # Create notification for the post owner
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
                url=f'/product/{instance.product.id}/'  # Link to the product page
            )

@receiver(pre_save, sender=Product)
def notify_owner_when_deal_removed(sender, instance, **kwargs):

    if instance.pk is None:
        return
    
    try:
        original_product = Product.objects.get(pk=instance.pk)
    except Product.DoesNotExist:
        return
    
    # Check if the product has been removed (is_archived changed from False to True)
    if not original_product.is_archived and instance.is_archived:
        # Product has been archived/removed
        
        # Get the owner user
        owner = instance.user
        if not owner:
            return
        

        title = f"Your Deal Has Been Removed: {instance.Name}"
        message = f"Your deal '{instance.Name}' has been removed by an administrator."

        recent_reports = ReportedDeal.objects.filter(product=instance, status='approved').order_by('-updated_at')
        
        if recent_reports.exists() and recent_reports.first().admin_notes:
            clean_reason = strip_tags(recent_reports.first().admin_notes)
            message += f"\n\nReason: {clean_reason}"
        
        # Create the notification
        Notification.objects.create(
            user=owner,
            title=title,
            message=message,
            notification_type='alert',
            related_object_type='product',
            related_object_id=instance.pk,
            url='/my-deals/'  # Link to their deals page
        )