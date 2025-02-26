from .views import *
from django.urls import path 
urlpatterns = [
    path('', home, name='home'),
     path('category/<str:foo>/', category, name='category'),
    path('deal_or_product/<int:pk>/', deal_or_product_detail, name='deal_or_product_detail'),
    path('register/', register, name='register'),
    path('login/', login_user, name='login'),
    path('logout/', logout_user, name='logout'),
    path('search/', search, name='search'),
    path('post_deal/', post_deal, name='post_deal'),
    path("user_profile/<int:identifier>/", user_profile, name="user_profile"),
    path("follow/<int:user_id>/", follow, name="follow"),
    path("unfollow/<int:user_id>/", unfollow, name="unfollow"),
    path('wishlist/', wishlist, name='wishlist'),
    path('like/<int:product_id>/', like_product, name='like_product'),
]
