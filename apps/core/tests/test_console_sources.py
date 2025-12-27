"""
Tests for SourceCreateView validation and normalization.
"""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.sources.models import Source

User = get_user_model()


class SourceCreateViewTests(TestCase):
    """Ensure console source creation validates input and normalizes domains."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='tester',
            email='tester@example.com',
            password='pass1234',
        )
        self.client.force_login(self.user)
        self.url = reverse('console:source_create')

    def test_normalizes_url_and_domain(self):
        """URL and domain should be normalized before saving."""
        response = self.client.post(
            self.url,
            {
                'name': 'Example Source',
                'url': 'HTTPS://WWW.Example.COM/Path/?utm_source=test#section',
                'source_type': 'news_site',
            },
        )

        assert response.status_code == 200
        source = Source.objects.get()
        assert source.domain == 'example.com'
        assert source.url == 'https://example.com/Path'

    def test_rejects_invalid_url_and_shows_errors(self):
        """Malformed URLs should be rejected with an error response."""
        response = self.client.post(
            self.url,
            {
                'name': 'Bad URL',
                'url': 'notaurl',
                'source_type': 'news_site',
            },
        )

        assert response.status_code == 400
        assert '#add-source-errors' == response.headers.get('HX-Retarget')
        assert 'valid URL' in response.content.decode()
        assert Source.objects.count() == 0

    def test_enforces_uniqueness_on_normalized_domain(self):
        """Domains are checked after normalization to prevent duplicates."""
        Source.objects.create(
            name='Existing',
            domain='example.com',
            url='https://example.com',
            source_type='news_site',
            status='active',
        )

        response = self.client.post(
            self.url,
            {
                'name': 'Duplicate',
                'url': 'https://WWW.EXAMPLE.com/',
                'source_type': 'news_site',
            },
        )

        assert response.status_code == 400
        assert 'already exists' in response.content.decode()
        assert Source.objects.count() == 1
