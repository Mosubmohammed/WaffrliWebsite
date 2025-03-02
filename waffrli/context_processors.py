from .models import Category

def category_list(request):
    return {'categories': Category.objects.all()}  # Makes categories available in all templates
