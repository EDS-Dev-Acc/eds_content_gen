#!/usr/bin/env python
"""
Phase 10.1 - JWT Authentication Tests

Tests for JWT auth endpoints and OperatorProfile.
"""

import os
import sys
import django

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
django.setup()

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status

from apps.core.models import OperatorProfile

User = get_user_model()


class TestRunner:
    """Simple test runner."""

    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors = []

    def run_test(self, name, test_func):
        """Run a single test."""
        try:
            test_func()
            self.passed += 1
            print(f"  [PASS] {name}")
        except AssertionError as e:
            self.failed += 1
            self.errors.append((name, str(e)))
            print(f"  [FAIL] {name}: {e}")
        except Exception as e:
            self.failed += 1
            self.errors.append((name, str(e)))
            print(f"  [ERROR] {name}: {e}")

    def summary(self):
        """Print test summary."""
        total = self.passed + self.failed
        print(f"\n{'='*60}")
        print(f"Results: {self.passed} passed, {self.failed} failed")
        if self.errors:
            print("\nFailures:")
            for name, error in self.errors:
                print(f"  - {name}: {error}")
        return self.failed == 0


def cleanup_test_users():
    """Remove test users."""
    User.objects.filter(username__startswith='testuser_').delete()


def get_client():
    """Get an API client."""
    return APIClient()


# =============================================================================
# Model Tests
# =============================================================================

def test_operator_profile_auto_created():
    """Test that OperatorProfile is auto-created with new User."""
    cleanup_test_users()
    user = User.objects.create_user(
        username='testuser_1',
        email='test1@example.com',
        password='testpass123'
    )
    
    assert hasattr(user, 'operator_profile'), "User should have operator_profile"
    assert isinstance(user.operator_profile, OperatorProfile)
    assert user.operator_profile.role == 'operator', "Default role should be 'operator'"
    
    # Cleanup
    user.delete()


def test_operator_profile_permissions():
    """Test OperatorProfile permission helpers."""
    cleanup_test_users()
    user = User.objects.create_user(
        username='testuser_2',
        email='test2@example.com',
        password='testpass123'
    )
    
    profile = user.operator_profile
    
    # Test default operator role
    assert not profile.is_admin
    assert profile.can_edit
    
    # Test admin role
    profile.role = 'admin'
    profile.save()
    assert profile.is_admin
    assert profile.can_edit
    
    # Test viewer role
    profile.role = 'viewer'
    profile.save()
    assert not profile.is_admin
    assert not profile.can_edit
    
    # Cleanup
    user.delete()


# =============================================================================
# Auth Endpoint Tests
# =============================================================================

def test_login_valid_credentials():
    """Test login with valid credentials."""
    cleanup_test_users()
    user = User.objects.create_user(
        username='testuser_3',
        email='test3@example.com',
        password='testpass123'
    )
    
    client = get_client()
    response = client.post('/api/auth/login/', {
        'username': 'testuser_3',
        'password': 'testpass123'
    })
    
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    data = response.json()
    assert 'access' in data, "Response should contain access token"
    assert 'refresh' in data, "Response should contain refresh token"
    assert 'user' in data, "Response should contain user data"
    assert data['user']['username'] == 'testuser_3'
    
    # Cleanup
    user.delete()


def test_login_invalid_credentials():
    """Test login with invalid credentials."""
    cleanup_test_users()
    user = User.objects.create_user(
        username='testuser_4',
        email='test4@example.com',
        password='testpass123'
    )
    
    client = get_client()
    response = client.post('/api/auth/login/', {
        'username': 'testuser_4',
        'password': 'wrongpassword'
    })
    
    assert response.status_code == 401, f"Expected 401, got {response.status_code}"
    
    # Cleanup
    user.delete()


def test_token_refresh():
    """Test token refresh endpoint."""
    cleanup_test_users()
    user = User.objects.create_user(
        username='testuser_5',
        email='test5@example.com',
        password='testpass123'
    )
    
    client = get_client()
    
    # Login first
    login_response = client.post('/api/auth/login/', {
        'username': 'testuser_5',
        'password': 'testpass123'
    })
    tokens = login_response.json()
    
    # Refresh token
    refresh_response = client.post('/api/auth/refresh/', {
        'refresh': tokens['refresh']
    })
    
    assert refresh_response.status_code == 200, f"Expected 200, got {refresh_response.status_code}"
    new_tokens = refresh_response.json()
    assert 'access' in new_tokens, "Response should contain new access token"
    
    # Cleanup
    user.delete()


def test_get_current_user():
    """Test GET /api/auth/me/ endpoint."""
    cleanup_test_users()
    user = User.objects.create_user(
        username='testuser_6',
        email='test6@example.com',
        password='testpass123'
    )
    
    client = get_client()
    
    # Login
    login_response = client.post('/api/auth/login/', {
        'username': 'testuser_6',
        'password': 'testpass123'
    })
    tokens = login_response.json()
    
    # Access protected endpoint
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
    me_response = client.get('/api/auth/me/')
    
    assert me_response.status_code == 200, f"Expected 200, got {me_response.status_code}"
    data = me_response.json()
    assert data['username'] == 'testuser_6'
    assert 'profile' in data
    assert data['profile']['role'] == 'operator'
    
    # Cleanup
    user.delete()


def test_update_current_user():
    """Test PATCH /api/auth/me/ endpoint."""
    cleanup_test_users()
    user = User.objects.create_user(
        username='testuser_7',
        email='test7@example.com',
        password='testpass123'
    )
    
    client = get_client()
    
    # Login
    login_response = client.post('/api/auth/login/', {
        'username': 'testuser_7',
        'password': 'testpass123'
    })
    tokens = login_response.json()
    
    # Update user info
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
    update_response = client.patch('/api/auth/me/', {
        'first_name': 'Test',
        'last_name': 'User',
        'profile': {'timezone': 'America/New_York'}
    }, format='json')
    
    assert update_response.status_code == 200, f"Expected 200, got {update_response.status_code}"
    data = update_response.json()
    assert data['first_name'] == 'Test'
    assert data['last_name'] == 'User'
    
    # Verify profile updated
    user.refresh_from_db()
    assert user.operator_profile.timezone == 'America/New_York'
    
    # Cleanup
    user.delete()


def test_protected_endpoint_without_token():
    """Test that protected endpoints reject requests without token."""
    client = get_client()
    response = client.get('/api/auth/me/')
    
    assert response.status_code == 401, f"Expected 401, got {response.status_code}"


def test_logout():
    """Test logout endpoint blacklists refresh token."""
    cleanup_test_users()
    user = User.objects.create_user(
        username='testuser_8',
        email='test8@example.com',
        password='testpass123'
    )
    
    client = get_client()
    
    # Login
    login_response = client.post('/api/auth/login/', {
        'username': 'testuser_8',
        'password': 'testpass123'
    })
    tokens = login_response.json()
    
    # Logout
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
    logout_response = client.post('/api/auth/logout/', {
        'refresh': tokens['refresh']
    }, format='json')
    
    assert logout_response.status_code == 200, f"Expected 200, got {logout_response.status_code}"
    
    # Try to use the refresh token - should fail
    refresh_response = client.post('/api/auth/refresh/', {
        'refresh': tokens['refresh']
    })
    
    assert refresh_response.status_code == 401, f"Blacklisted token should return 401, got {refresh_response.status_code}"
    
    # Cleanup
    user.delete()


def test_token_contains_user_claims():
    """Test that JWT contains custom user claims."""
    import jwt
    from django.conf import settings
    
    cleanup_test_users()
    user = User.objects.create_user(
        username='testuser_9',
        email='test9@example.com',
        password='testpass123'
    )
    user.operator_profile.role = 'admin'
    user.operator_profile.save()
    
    client = get_client()
    login_response = client.post('/api/auth/login/', {
        'username': 'testuser_9',
        'password': 'testpass123'
    })
    tokens = login_response.json()
    
    # Decode the access token
    decoded = jwt.decode(
        tokens['access'],
        settings.SECRET_KEY,
        algorithms=['HS256']
    )
    
    assert decoded['username'] == 'testuser_9'
    assert decoded['email'] == 'test9@example.com'
    assert decoded['role'] == 'admin'
    
    # Cleanup
    user.delete()


# =============================================================================
# Main
# =============================================================================

def main():
    """Run all tests."""
    print("="*60)
    print("Phase 10.1 - JWT Authentication Tests")
    print("="*60)
    
    runner = TestRunner()
    
    print("\n[Model Tests]")
    runner.run_test("OperatorProfile auto-created", test_operator_profile_auto_created)
    runner.run_test("OperatorProfile permissions", test_operator_profile_permissions)
    
    print("\n[Auth Endpoint Tests]")
    runner.run_test("Login with valid credentials", test_login_valid_credentials)
    runner.run_test("Login with invalid credentials", test_login_invalid_credentials)
    runner.run_test("Token refresh", test_token_refresh)
    runner.run_test("Get current user", test_get_current_user)
    runner.run_test("Update current user", test_update_current_user)
    runner.run_test("Protected endpoint without token", test_protected_endpoint_without_token)
    runner.run_test("Logout blacklists token", test_logout)
    runner.run_test("Token contains user claims", test_token_contains_user_claims)
    
    success = runner.summary()
    
    if success:
        print("\n[SUCCESS] All Phase 10.1 tests passed!")
    else:
        print("\n[FAILURE] Some tests failed")
    
    # Final cleanup
    cleanup_test_users()
    
    return 0 if success else 1


if __name__ == '__main__':
    sys.exit(main())
