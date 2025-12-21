#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script to create a superuser for Django admin.
"""

import sys
import io
import os
import django

# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Setup Django environment
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
django.setup()

from django.contrib.auth import get_user_model

User = get_user_model()

def create_superuser():
    """Create superuser if it doesn't exist."""

    username = 'admin'
    email = 'admin@emcip.local'
    password = 'admin'  # Simple password for development only!

    if User.objects.filter(username=username).exists():
        print(f"[INFO] Superuser '{username}' already exists.")
        print(f"       Username: {username}")
        print(f"       Password: {password}")
    else:
        User.objects.create_superuser(
            username=username,
            email=email,
            password=password
        )
        print(f"[SUCCESS] Superuser created!")
        print(f"          Username: {username}")
        print(f"          Password: {password}")
        print(f"          Email: {email}")

    print("\nYou can now access the admin at:")
    print("  http://localhost:8000/admin/")
    print("\n[WARNING] This is a development password. Change it in production!")

if __name__ == '__main__':
    create_superuser()
