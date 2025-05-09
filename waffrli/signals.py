from django.db.models.signals import pre_save
from django.dispatch import receiver
from django.utils.html import strip_tags
from .models import ReportedDeal, Notification, Product
from django.db.models.signals import pre_delete
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

# @receiver(pre_save, sender=Product)
# def notify_owner_when_deal_removed(sender, instance, **kwargs):

#     if instance.pk is None:
#         return
    
#     try:
#         original_product = Product.objects.get(pk=instance.pk)
#     except Product.DoesNotExist:
#         return
    
#     # Check if the product has been removed (is_archived changed from False to True)
#     if not original_product.is_archived and instance.is_archived:
#         # Product has been archived/removed
        
#         # Get the owner user
#         owner = instance.user
#         if not owner:
#             return
        

#         title = f"Your Deal Has Been Removed: {instance.Name}"
#         message = f"Your deal '{instance.Name}' has been removed by an administrator."

#         recent_reports = ReportedDeal.objects.filter(product=instance, status='approved').order_by('-updated_at')
        
#         if recent_reports.exists() and recent_reports.first().admin_notes:
#             clean_reason = strip_tags(recent_reports.first().admin_notes)
#             message += f"\n\nReason: {clean_reason}"
        
#         # Create the notification
#         Notification.objects.create(
#             user=owner,
#             title=title,
#             message=message,
#             notification_type='alert',
#             related_object_type='product',
#             related_object_id=instance.pk,
#             url='/my-deals/' 
#         )
        

@receiver(pre_delete, sender=Product)
def notify_owner_when_deal_deleted(sender, instance, **kwargs):

    if instance.is_archived:
        return
    
    owner = instance.user
    if not owner:
        return
    
    title = f"Your Deal Has Been Deleted: {instance.Name}"
    message = f"Your deal '{instance.Name}' has been permanently deleted by an administrator."

    try:
        recent_reports = ReportedDeal.objects.filter(
            product=instance, 
            status='approved'
        ).order_by('-updated_at')
        
        if recent_reports.exists() and recent_reports.first().admin_notes:
            clean_reason = strip_tags(recent_reports.first().admin_notes)
            message += f"\n\nReason: {clean_reason}"
    except Exception as e:

        print(f"Error retrieving reports for deletion notification: {str(e)}")

    try:
        notification = Notification.objects.create(
            user=owner,
            title=title,
            message=message,
            notification_type='alert',
            related_object_type='product',
            related_object_id=instance.pk,
            url='/my-deals/' 
        )
    except Exception as e:
        print(f"Error creating deletion notification: {str(e)}")