from django.test import TestCase
from django.contrib.auth.models import User
from authentication.models import SupabaseUser
from django.utils import timezone

class SupabaseUserModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='password123'
        )
        self.supabase_user = SupabaseUser.objects.create(
            user=self.user,
            supabase_id='test_supabase_id',
            email_verified=True
        )

    def test_supabase_user_creation(self):
        self.assertEqual(self.supabase_user.user, self.user)
        self.assertEqual(self.supabase_user.supabase_id, 'test_supabase_id')
        self.assertTrue(self.supabase_user.email_verified)
        self.assertIsNotNone(self.supabase_user.created_at)
        self.assertIsNotNone(self.supabase_user.updated_at)

    def test_str_representation(self):
        expected = f"test@example.com - test_supabase_id"
        self.assertEqual(str(self.supabase_user), expected)

    def test_one_to_one_relationship(self):
        with self.assertRaises(Exception):
            SupabaseUser.objects.create(
                user=self.user,
                supabase_id='another_supabase_id'
            )
