from .models import Category,Message

def category_list(request):
    return {'categories': Category.objects.all()}  # Makes categories available in all templates

def unread_messages_count(request):
    """
    Context processor to add unread message count to all templates
    """
    if request.user.is_authenticated:
        unread_count = Message.objects.filter(recipient=request.user, is_read=False).count()
        return {'unread_count': unread_count}
    return {'unread_count': 0}
