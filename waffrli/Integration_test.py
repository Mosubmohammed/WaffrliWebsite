

from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from decimal import Decimal
from django.utils import timezone
from unittest.mock import patch, MagicMock
from waffrli.models import (
    Product, Comment, Follow, Message,
    WishlistItem, Notification, Customer, Category,
    FirebaseUser
)

class IntegrationTestCase(TestCase):

    def setUp(self):
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

        self.customer1 = Customer.objects.create(
            user=self.user1,
            first_name='Test',
            last_name='User1',
            phone='0799999999',
            email='testuser1@example.com',
            password='password123'
        )

        self.customer2 = Customer.objects.create(
            user=self.user2,
            first_name='Test',
            last_name='User2',
            phone='0787654321',
            email='testuser2@example.com',
            password='password123'
        )

        self.category1 = Category.objects.create(name='Electronics')
        self.category2 = Category.objects.create(name='Clothing')

        self.product1 = Product.objects.create(
            user=self.user1,
            Name='Test Product 1',
            Dealurl='https://example.com/deal1',
            Price=Decimal('100.00'),
            sale_price=Decimal('70.00'),
            Description='Test description 1',
            store='Test Store 1',
            brand='Test Brand 1',
            category=self.category1,
            city='Test City 1'
        )

        self.product2 = Product.objects.create(
            user=self.user2,
            Name='Test Product 2',
            Dealurl='https://example.com/deal2',
            Price=Decimal('200.00'),
            sale_price=Decimal('50.00'),
            Description='Test description 2',
            store='Test Store 2',
            brand='Test Brand 2',
            category=self.category2,
            city='Test City 2'
        )

        self.client = Client()


class ProductIntegrationTests(IntegrationTestCase):

    def test_product_list_view(self):
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Test Product 1')
        self.assertContains(response, 'Test Product 2')

    def test_product_detail_view(self): # pass
        response = self.client.get(reverse('product', args=[self.product1.id]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Test Product 1')
        self.assertContains(response, 'Test Store 1')
        self.assertContains(response, 'Test Brand 1')

    def test_product_filtering(self):
        response = self.client.get(reverse('category', args=['Electronics']))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Test Product 1')
        self.assertNotContains(response, 'Test Product 2')

    @patch('firebase_admin.auth.verify_id_token')
    def test_post_deal(self, mock_verify_token):
        mock_verify_token.return_value = {
            'uid': self.user1.username,
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
            'category': self.category1.id,
            'city': 'New Test City'
        })

        self.assertEqual(response.status_code, 302)

        self.assertTrue(Product.objects.filter(Name='New Test Product').exists())


class UserAuthenticationTests(IntegrationTestCase):

    @patch('firebase_admin.auth.verify_id_token')
    def test_login_view(self, mock_verify_token):
        mock_verify_token.return_value = {
            'uid': self.user1.username,
            'email': self.user1.email
        }

        response = self.client.post(reverse('login'), {
            'username': 'testuser1',
            'password': 'password123'
        })

        self.assertEqual(response.status_code, 302)

    def test_logout_view(self): # pass
        self.client.login(username='testuser1', password='password123')

        response = self.client.get(reverse('logout'))

        self.assertEqual(response.status_code, 302)


class SocialFeatureTests(IntegrationTestCase):

    def test_follow_user(self): # pass
        self.client.login(username='testuser1', password='password123')

        response = self.client.post(reverse('follow', args=[self.user2.id]))

        self.assertEqual(response.status_code, 302)

        self.assertTrue(Follow.objects.filter(follower=self.user1, following=self.user2).exists())

    def test_like_product(self):
        self.client.login(username='testuser1', password='password123')

        response = self.client.post(reverse('like_product', args=[self.product2.id]))

        self.assertEqual(response.status_code, 200)

        self.assertTrue(self.product2.likes.filter(id=self.user1.id).exists())


class WishlistIntegrationTests(IntegrationTestCase):

    def test_add_wishlist_item(self):
        self.client.login(username='testuser1', password='password123')

        response = self.client.post(reverse('add_wishlist_item'), {
            'keyword': 'laptop',
            'min_price': '500.00',
            'max_price': '1000.00',
            'category': 'Electronics'
        })

        self.assertEqual(response.status_code, 302)

        self.assertTrue(WishlistItem.objects.filter(user=self.user1, keyword='laptop').exists())

    def test_delete_wishlist_item(self):
        wishlist_item = WishlistItem.objects.create(
            user=self.user1,
            keyword='laptop',
            min_price=Decimal('500.00'),
            max_price=Decimal('1000.00'),
            category='Electronics'
        )

        self.client.login(username='testuser1', password='password123')

        response = self.client.post(reverse('delete_wishlist_item', args=[wishlist_item.id]))

        self.assertEqual(response.status_code, 302)

        self.assertFalse(WishlistItem.objects.filter(id=wishlist_item.id).exists())


class MessagingIntegrationTests(IntegrationTestCase):

    def test_send_message(self):
        self.client.login(username='testuser1', password='password123')

        response = self.client.post(reverse('send_message', args=[self.user2.id]), {
            'subject': 'Test Subject',
            'content': 'Test Content'
        })

        self.assertEqual(response.status_code, 302)

        self.assertTrue(Message.objects.filter(
            sender=self.user1,
            recipient=self.user2,
            subject='Test Subject'
        ).exists())

    def test_reply_to_message(self): # pass
        message = Message.objects.create(
            sender=self.user2,
            recipient=self.user1,
            subject='Original Subject',
            content='Original Content'
        )

        self.client.login(username='testuser1', password='password123')

        response = self.client.post(reverse('reply_message', args=[message.id]), {
            'content': 'Reply Content'
        })

        self.assertEqual(response.status_code, 302)

        self.assertTrue(Message.objects.filter(
            sender=self.user1,
            recipient=self.user2,
            is_reply=True,
            parent_message=message
        ).exists())


class NotificationIntegrationTests(IntegrationTestCase):

    def test_mark_notification_read(self):
        notification = Notification.objects.create(
            user=self.user1,
            title='Test Notification',
            message='This is a test notification',
            notification_type='info'
        )

        self.client.login(username='testuser1', password='password123')

        response = self.client.post(reverse('mark_notification_read', args=[notification.id]))

        self.assertEqual(response.status_code, 302)

        notification.refresh_from_db()
        self.assertTrue(notification.is_read)