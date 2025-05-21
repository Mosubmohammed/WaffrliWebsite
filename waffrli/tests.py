from django.test import TestCase
from django.contrib.auth.models import User
from decimal import Decimal
from waffrli.models import (
    Product, Comment, Follow, Message,
    WishlistItem, Notification, Customer, Category,
    ReportedDeal
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


class CustomerModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testcustomer',
            email='testcustomer@example.com',
            password='password123'
        )

        self.customer = Customer.objects.create(
            user=self.user,
            first_name='Test',
            last_name='Customer',
            phone='1234567890',
            email='testcustomer@example.com',
            gender='M',
            formatted_address='123 Test St, Test City',
            latitude=37.7749,
            longitude=-122.4194
        )

        self.category = Category.objects.create(name='Test Category')
        self.product = Product.objects.create(
            user=self.user,
            Name='Test Product',
            Dealurl='https://example.com/deal',
            Price=Decimal('100.00'),
            Description='Test description',
            store='Test Store',
            category=self.category
        )

    def test_customer_creation(self):
        self.assertEqual(self.customer.user, self.user)
        self.assertEqual(self.customer.first_name, 'Test')
        self.assertEqual(self.customer.last_name, 'Customer')
        self.assertEqual(self.customer.phone, '1234567890')
        self.assertEqual(self.customer.email, 'testcustomer@example.com')
        self.assertEqual(self.customer.gender, 'M')
        self.assertEqual(self.customer.formatted_address, '123 Test St, Test City')
        self.assertEqual(self.customer.latitude, 37.7749)
        self.assertEqual(self.customer.longitude, -122.4194)

    def test_str_representation(self):
        expected = f"Test Customer"
        self.assertEqual(str(self.customer), expected)

    def test_number_of_likes(self):
        self.assertEqual(self.customer.number_of_likes(), 0)

        self.product.likes.add(self.user)
        self.assertEqual(self.customer.number_of_likes(), 0)


class ReportedDealTests(TestCase):
    def setUp(self):
        self.reporter_user = User.objects.create_user(
            username = 'reporter',
            email = 'reporter@example.com',
            password = 'password123'
        )

        self.reporter = Customer.objects.create(
            user = self.reporter_user ,
            first_name='reporter',
            email='reporter@example.com',
            password='password123'
        )

        self.deal_owner = User.objects.create_user(
            username='dealowner',
            email='dealowner@example.com',
            password='password123'
        )

        self.category = Category.objects.create(name='Test Category')

        self.product = Product.objects.create(
            user=self.deal_owner,
            Name='Reported Product',
            Dealurl='https://example.com/deal',
            Price=Decimal('100.00'),
            Description='Test description',
            store='Test Store',
            category=self.category
        )

        self.reported_deal = ReportedDeal.objects.create(
            reporter=self.reporter,
            product=self.product,
            reason='price_incorrect',
            details='The price is actually $150, not $100'
        )

    def test_reported_deal_creation(self):
        self.assertEqual(self.reported_deal.reporter, self.reporter)
        self.assertEqual(self.reported_deal.product, self.product)
        self.assertEqual(self.reported_deal.reason, 'price_incorrect')
        self.assertEqual(self.reported_deal.details, 'The price is actually $150, not $100')

    def test_str_representation(self):
        expected = f"Report on Reported Product by reporter  - price_incorrect"
        self.assertEqual(str(self.reported_deal), expected)

    def test_resolve_report(self):
        self.reported_deal.is_resolved = True
        self.reported_deal.resolution_notes = "Updated the price to $150"
        self.reported_deal.save()

        self.reported_deal.refresh_from_db()

        self.assertTrue(self.reported_deal.is_resolved)
        self.assertEqual(self.reported_deal.resolution_notes, "Updated the price to $150")
