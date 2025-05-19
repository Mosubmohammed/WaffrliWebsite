import debug_toolbar 
from debug_toolbar.toolbar import debug_toolbar_urls 
from django.contrib import admin 
from django.urls import path, include 
from . import settings 
from django.conf.urls.static import static
from django.views.decorators.cache import cache_control
from django.views.static import serve

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('waffrli.urls')),
    path('auth/', include('authentication.urls')),
] + debug_toolbar_urls()


if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

else:
    urlpatterns += [
        path('static/<path:path>', 
             cache_control(max_age=3600*24*30)(serve),  # Cache for 30 days
             {'document_root': settings.STATIC_ROOT}),
        path('media/<path:path>', 
             cache_control(max_age=3600*24*7)(serve),  # Cache for 7 days
             {'document_root': settings.MEDIA_ROOT}),
    ]