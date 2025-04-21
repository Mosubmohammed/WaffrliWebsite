from django.db.models.signals import pre_save
from django.dispatch import receiver
from django.utils.html import strip_tags
from .models import ReportedDeal, Notification

@receiver(pre_save, sender=ReportedDeal)
def create_report_status_notification(sender, instance, **kwargs):
    """
    Signal handler to create notifications when a ReportedDeal status changes
    """
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