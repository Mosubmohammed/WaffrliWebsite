from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from decimal import Decimal
from unittest.mock import patch, MagicMock
from waffrli.models import (
    Product, Category, Customer, Comment,
    WishlistItem, Notification, Message
)
from authentication.models import SupabaseUser

class WaffrliViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        
        self.user1 = User.objects.create_user(
            username='testuser1',
            email='testuser1@example.com',
            password='password123'
        )
        
        self.user2 = User.objects.create_user(
            username='testuser2',
            email='testuser2@example.com',
            password='password123'
        )
        
        self.supabase_user1 = SupabaseUser.objects.create(
            user=self.user1,
            supabase_id='test_supabase_id_1',
            email_verified=True
        )
        
        self.customer1 = Customer.objects.create(
            user=self.user1,
            first_name='Test',
            last_name='User1',
            phone='1234567890',
            email='testuser1@example.com'
        )
        
        self.category = Category.objects.create(name='Electronics')
        
        self.product1 = Product.objects.create(
            user=self.user1,
            Name='Test Product 1',
            Dealurl='https://example.com/deal1',
            Price=Decimal('100.00'),
            sale_price=Decimal('70.00'),
            Description='Test description 1',
            store='Test Store 1',
            brand='Test Brand 1',
            category=self.category,
            city='Test City 1'
        )
        
        self.product2 = Product.objects.create(
            user=self.user2,
            Name='Test Product 2',
            Dealurl='https://example.com/deal2',
            Price=Decimal('200.00'),
            sale_price=Decimal('150.00'),
            Description='Test description 2',
            store='Test Store 2',
            brand='Test Brand 2',
            category=self.category,
            city='Test City 2'
        )

    def test_home_view(self):
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Test Product 1')
        self.assertContains(response, 'Test Product 2')
        
    def test_product_detail_view(self):
        response = self.client.get(reverse('product', args=[self.product1.id]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Test Product 1')
        self.assertContains(response, 'Test Store 1')
        self.assertContains(response, 'Test Brand 1')
        
    def test_category_view(self):
        response = self.client.get(reverse('category', args=['Electronics']))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Test Product 1')
        self.assertContains(response, 'Test Product 2')
        
    # def test_search_view(self):
    #     response = self.client.get(reverse('search'), {'q': 'Test Product 1'})
    #     print(f"Response content: {response.content.decode()}")
    #     self.assertEqual(response.status_code, 200)
    #     self.assertContains(response, 'Test Product 1')
    #     self.assertNotContains(response, 'Test Product 2')
        
    @patch('authentication.middleware.create_client')
    def test_post_deal_view(self, mock_create_client):
        mock_supabase = MagicMock()
        mock_create_client.return_value = mock_supabase
        
        mock_supabase.auth.get_user.return_value = {
            'id': self.supabase_user1.supabase_id,
            'email': self.user1.email
        }
        
        self.client.login(username='testuser1', password='password123')
        
        response = self.client.post(reverse('post_deal'), {
            'Name': 'New Test Product',
            'Dealurl': 'https://example.com/newdeal',
            'Price': '150.00',
            'sale_price': '100.00',
            'Description': 'New test description',
            'store': 'New Test Store',
            'brand': 'New Test Brand',
            'category': self.category.id,
            'city': 'New Test City'
        })
        
        self.assertEqual(response.status_code, 302)
        
        self.assertTrue(not Product.objects.filter(Name='New Test Product').exists())
        
    @patch('authentication.middleware.create_client')
    def test_like_product_view(self, mock_create_client):
        mock_supabase = MagicMock()
        mock_create_client.return_value = mock_supabase
        
        mock_supabase.auth.get_user.return_value = {
            'id': self.supabase_user1.supabase_id,
            'email': self.user1.email
        }
        
        self.client.login(username='testuser1', password='password123')
        
        response = self.client.post(reverse('like_product', args=[self.product2.id]))
        
        self.assertEqual(response.status_code, 302)
        
        self.assertTrue(self.product2.likes.filter(id=self.user1.id).exists())
        
    # @patch('authentication.middleware.create_client')
    # def test_user_profile_view(self, mock_create_client):
    #     mock_supabase = MagicMock()
    #     mock_create_client.return_value = mock_supabase
    #
    #     mock_supabase.auth.get_user.return_value = {
    #         'id': self.supabase_user1.supabase_id,
    #         'email': self.user1.email
    #     }
    #
    #     self.client.login(username='testuser1', password='password123')
    #
    #     response = self.client.get(reverse('user_profile', args=[self.user1.id]))
    #
    #     self.assertEqual(response.status_code, 200)
    #     self.assertContains(response, 'Test User1')
    #     self.assertContains(response, 'Test Product 1')