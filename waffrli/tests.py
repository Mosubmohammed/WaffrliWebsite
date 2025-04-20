from django.test import TestCase
from django.contrib.auth.models import User
from decimal import Decimal
from django.utils import timezone
from datetime import timedelta
from waffrli.models import (
    Product, Comment, Follow, Message,
    WishlistItem, Notification, Customer, Category
)


class ProductModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='password')
        self.category = Category.objects.create(name='Electronics')

        self.product = Product.objects.create(
            user=self.user,
            Name='Test Product',
            Dealurl='https://example.com/deal',
            Price=Decimal('100.00'),
            sale_price=Decimal('30.00'),
            Description='Test description',
            store='Test Store',
            brand='Test Brand',
            category=self.category,
            city='Test City',
            store_type='physical',
            latitude=37.7749,
            longitude=-122.4194
        )

    def test_product_creation(self):
        self.assertEqual(self.product.Name, 'Test Product')
        self.assertEqual(self.product.Price, Decimal('100.00'))

    def test_str_representation(self):
        self.assertEqual(str(self.product), 'Test Product')

    def test_number_of_likes(self):
        self.assertEqual(self.product.number_of_likes(), 0)

        user2 = User.objects.create_user(username='testuser2', password='password')
        self.product.likes.add(user2)
        self.assertEqual(self.product.number_of_likes(), 1)

    def test_discount_percentage(self):
        self.assertEqual(self.product.get_discount_percentage(), 70.0)

    def test_is_hot_deal(self):
        self.assertTrue(self.product.is_hot_deal())

        self.product.sale_price = Decimal('31.00')
        self.product.save()
        self.assertFalse(self.product.is_hot_deal())

    def test_get_savings_amount(self):
        self.assertEqual(self.product.get_savings_amount(), Decimal('70.00'))

    def test_distance_to(self):
        distance = self.product.distance_to(37.7749, -122.4194)
        self.assertEqual(distance, 0.0)

        distance = self.product.distance_to(37.8049, -122.4194)
        self.assertGreater(distance, 0)

    def test_increment_views(self):
        self.assertEqual(self.product.views, 0)
        self.product.increment_views()
        self.assertEqual(self.product.views, 1)


class CommentModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='password')
        self.customer = Customer.objects.create(user=self.user, first_name='Test', last_name='User')
        self.category = Category.objects.create(name='Electronics')

        self.product = Product.objects.create(
            Name='Test Product',
            Dealurl='https://example.com/deal',
            Price=Decimal('100.00'),
            Description='Test description',
            store='Test Store',
            brand='Test Brand',
            category=self.category,
            city='Test City'
        )

        self.comment = Comment.objects.create(
            product=self.product,
            customer=self.customer,
            text='This is a test comment'
        )

    def test_comment_creation(self):
        self.assertEqual(self.comment.text, 'This is a test comment')

    def test_str_representation(self):
        expected = f"Comment by Test on Test Product"
        self.assertEqual(str(self.comment), expected)


class FollowModelTests(TestCase):
    def setUp(self):
        self.user1 = User.objects.create_user(username='follower', password='password')
        self.user2 = User.objects.create_user(username='following', password='password')

        self.follow = Follow.objects.create(
            follower=self.user1,
            following=self.user2
        )

    def test_follow_creation(self):
        self.assertEqual(self.follow.follower, self.user1)
        self.assertEqual(self.follow.following, self.user2)

    def test_unique_constraint(self):
        with self.assertRaises(Exception):
            Follow.objects.create(follower=self.user1, following=self.user2)


class MessageModelTests(TestCase):
    def setUp(self):
        self.sender = User.objects.create_user(username='sender', password='password')
        self.recipient = User.objects.create_user(username='recipient', password='password')

        self.message = Message.objects.create(
            sender=self.sender,
            recipient=self.recipient,
            subject='Test Subject',
            content='Test Content'
        )

    def test_message_creation(self):
        self.assertEqual(self.message.subject, 'Test Subject')
        self.assertEqual(self.message.content, 'Test Content')
        self.assertFalse(self.message.is_read)

    def test_str_representation(self):
        expected = f"Test Subject - From: {self.sender} To: {self.recipient}"
        self.assertEqual(str(self.message), expected)

    def test_reply_relationship(self):
        reply = Message.objects.create(
            sender=self.recipient,
            recipient=self.sender,
            subject='Re: Test Subject',
            content='Reply Content',
            is_reply=True,
            parent_message=self.message
        )

        self.assertEqual(reply.parent_message, self.message)
        self.assertTrue(reply in self.message.replies.all())


class WishlistItemTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='password')

        self.wishlist_item = WishlistItem.objects.create(
            user=self.user,
            keyword='laptop',
            min_price=Decimal('500.00'),
            max_price=Decimal('1000.00'),
            category='Electronics'
        )

    def test_wishlist_creation(self):
        self.assertEqual(self.wishlist_item.keyword, 'laptop')
        self.assertEqual(self.wishlist_item.min_price, Decimal('500.00'))

    def test_str_representation(self):
        expected = f"laptop - testuser"
        self.assertEqual(str(self.wishlist_item), expected)


class NotificationModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='password')

        self.notification = Notification.objects.create(
            user=self.user,
            title='Test Notification',
            message='This is a test notification',
            notification_type='info'
        )

    def test_notification_creation(self):
        self.assertEqual(self.notification.title, 'Test Notification')
        self.assertEqual(self.notification.notification_type, 'info')
        self.assertFalse(self.notification.is_read)

    def test_str_representation(self):
        expected = f"Test Notification - testuser"
        self.assertEqual(str(self.notification), expected)

