from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from unittest.mock import patch, MagicMock
from authentication.models import SupabaseUser

class AuthenticationViewTests(TestCase):
    def setUp(self):
        self.client = Client()
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

    @patch('authentication.views.create_client')
    def test_login_view(self, mock_create_client):
        """Test the login view with valid credentials"""
        # Mock the Supabase client
        mock_supabase = MagicMock()
        mock_create_client.return_value = mock_supabase

        # Mock the auth.sign_in_with_password method
        mock_supabase.auth.sign_in_with_password.return_value = {
            'user': {
                'id': self.supabase_user.supabase_id,
                'email': self.user.email
            },
            'session': {
                'access_token': 'test_access_token'
            }
        }

        response = self.client.post(reverse('login'), {
            'email': 'test@example.com',
            'password': 'password123'
        })

        self.assertEqual(response.status_code, 302)

    @patch('authentication.views.create_client')
    def test_login_view_invalid_credentials(self, mock_create_client):
        mock_supabase = MagicMock()
        mock_create_client.return_value = mock_supabase

        mock_supabase.auth.sign_in_with_password.side_effect = Exception("Invalid credentials")

        response = self.client.post(reverse('login'), {
            'email': 'test@example.com',
            'password': 'wrong_password'
        })

        self.assertEqual(response.status_code, 200)

    def test_logout_view(self):
        self.client.login(username='testuser', password='password123')

        response = self.client.get(reverse('logout'))

        self.assertEqual(response.status_code, 302)

    @patch('authentication.views.create_client')  # Patch the Supabase client creation, not the entire register function
    def test_register_view(self, mock_create_client):
        mock_supabase = MagicMock()
        mock_create_client.return_value = mock_supabase

        mock_supabase.auth.sign_up.return_value = {
            'user': {
                'id': 'new_supabase_id',
                'email': 'newuser@example.com'
            },
            'session': {
                'access_token': 'new_access_token'
            }
        }


        response = self.client.post(reverse('register'), {
            'email': 'newuser@example.com',
            'password': 'password123',
            'confirm_password': 'password123'
        })

        self.assertEqual(response.status_code, 200)

        self.assertTrue(not User.objects.filter(email='newuser@example.com').exists())

        self.assertTrue(not SupabaseUser.objects.filter(supabase_id='new_supabase_id').exists())