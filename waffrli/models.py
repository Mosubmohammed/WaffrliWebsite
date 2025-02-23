from django.utils import timezone
from django.db.models.signals import post_save
from django.db import models
from django.contrib.auth.models import User
from django.dispatch import receiver
# Create your models here.

from django.contrib.auth import get_user_model

def get_default_user():
    User = get_user_model()
    return User.objects.first()  # Or create a new default user if needed


class Category(models.Model):
    name=models.CharField(max_length=100)
    def __str__(self) -> str:
        return self.name
    class Meta:
        verbose_name_plural='Categories'
        
        



class Customer(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, default=get_default_user)
    view_count = models.IntegerField(default=0)
    first_name = models.CharField(max_length=50)
    last_name = models.CharField(max_length=50)
    phone = models.CharField(max_length=10)
    email = models.EmailField(max_length=100)
    password = models.CharField(max_length=50)
    gender = models.CharField(max_length=1, choices=[
        ('M', 'Male'), ('F', 'Female'), ('O', 'Other'), ('N', 'Prefer not to say')
    ], default='N')
    address = models.CharField(max_length=100)

    date_modified = models.DateTimeField(auto_now=True)
    image = models.ImageField(upload_to='uploads/product', null=True, blank=True)
    likes=models.ManyToManyField(User, related_name="Customer_like",blank=True)

    def __str__(self):
        return f"{self.first_name} {self.last_name}"

    def number_of_likes(self):
            return self.likes.count()
    
class Product(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    Name = models.CharField(max_length=255)
    Dealurl = models.URLField(unique=True)
    sale_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    Price = models.DecimalField(max_digits=10, decimal_places=2)
    Description = models.TextField()
    store = models.CharField(max_length=255)
    category = models.ForeignKey('Category', on_delete=models.CASCADE)
    city = models.CharField(max_length=255)
    image = models.ImageField(upload_to='uploads/product/', null=True, blank=True)
    customer_pic_id = models.ForeignKey(Customer, on_delete=models.SET_NULL, null=True, blank=True, default=None)
    likes=models.ManyToManyField(User, related_name="Product_like",blank=True)
    views  = models.IntegerField(default=0)
    create_at = models.DateTimeField(default=timezone.now)
    
    def increment_views(self):
        self.views += 1
        self.save()

    def __str__(self) -> str:
        return self.Name

    def number_of_likes(self):
        return self.likes.count()




class Follow(models.Model):
    follower = models.ForeignKey(User, related_name="following", on_delete=models.CASCADE)
    following = models.ForeignKey(User, related_name="followers", on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('follower', 'following')  # Prevent duplicate follows

    def __str__(self):
        return f"{self.follower.username} follows {self.following.username}"
    



# Create Profile When New User Signs Up
# @receiver(post_save, sender=User)

# # ✅ Auto-create a Customer when a User is created
# @receiver(post_save, sender=User)
# def create_customer_profile(sender, instance, created, **kwargs):
#     if created:
#         Customer.objects.create(
#             user=instance,
#             first_name=instance.first_name if instance.first_name else "First",
#             last_name=instance.last_name if instance.last_name else "Last",
#             phone="0000000000",  # Placeholder phone number
#             email=instance.email if instance.email else "default@example.com",
#             password=instance.password,  # Storing hashed password
#             gender="N",  # Default to 'Prefer not to say'
#             address="Not Provided",  # Default address
#             image=None,  # No profile image by default
#         )

