# Generated migration for Phase 16 Discovery Architecture
# Adds: SeedRawCapture, DiscoveryRun, extended Seed fields

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('seeds', '0003_add_query_indexes'),
    ]

    operations = [
        # Add new fields to Seed model
        migrations.AddField(
            model_name='seed',
            name='query_used',
            field=models.CharField(blank=True, help_text='Discovery query that found this seed', max_length=500),
        ),
        migrations.AddField(
            model_name='seed',
            name='referrer_url',
            field=models.URLField(blank=True, help_text='URL from which this seed was discovered', max_length=2000),
        ),
        migrations.AddField(
            model_name='seed',
            name='discovery_run_id',
            field=models.UUIDField(blank=True, db_index=True, help_text='Discovery run that found this seed', null=True),
        ),
        migrations.AddField(
            model_name='seed',
            name='relevance_score',
            field=models.IntegerField(default=0, help_text='Topical relevance score 0-100'),
        ),
        migrations.AddField(
            model_name='seed',
            name='utility_score',
            field=models.IntegerField(default=0, help_text='Scrape utility score 0-100'),
        ),
        migrations.AddField(
            model_name='seed',
            name='freshness_score',
            field=models.IntegerField(default=0, help_text='Freshness/activity score 0-100'),
        ),
        migrations.AddField(
            model_name='seed',
            name='authority_score',
            field=models.IntegerField(default=0, help_text='Source authority score 0-100'),
        ),
        migrations.AddField(
            model_name='seed',
            name='overall_score',
            field=models.IntegerField(db_index=True, default=0, help_text='Weighted composite score 0-100'),
        ),
        migrations.AddField(
            model_name='seed',
            name='scrape_plan_hint',
            field=models.CharField(blank=True, choices=[('sitemap', 'Sitemap Crawl'), ('rss_feed', 'RSS Feed'), ('member_list', 'Member List'), ('category_pages', 'Category Pages'), ('api', 'API Endpoint'), ('search', 'Search Interface'), ('manual', 'Manual Extraction')], help_text='Recommended scrape approach', max_length=50),
        ),
        migrations.AddField(
            model_name='seed',
            name='recommended_entrypoints',
            field=models.JSONField(blank=True, default=list, help_text='Discovered entrypoints: sitemaps, feeds, category pages'),
        ),
        migrations.AddField(
            model_name='seed',
            name='expected_fields',
            field=models.JSONField(blank=True, default=list, help_text='Expected extractable fields: name, address, phone, etc.'),
        ),
        migrations.AddField(
            model_name='seed',
            name='review_status',
            field=models.CharField(choices=[('pending', 'Pending Review'), ('reviewed', 'Reviewed'), ('approved', 'Approved'), ('rejected', 'Rejected')], db_index=True, default='pending', help_text='Review workflow status', max_length=20),
        ),
        migrations.AddField(
            model_name='seed',
            name='review_notes',
            field=models.TextField(blank=True, help_text='Notes from review process'),
        ),
        migrations.AddField(
            model_name='seed',
            name='reviewed_at',
            field=models.DateTimeField(blank=True, help_text='When review was completed', null=True),
        ),
        migrations.AddField(
            model_name='seed',
            name='reviewed_by',
            field=models.ForeignKey(blank=True, help_text='User who reviewed this seed', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='reviewed_seeds', to=settings.AUTH_USER_MODEL),
        ),
        
        # Add index for overall_score queries
        migrations.AddIndex(
            model_name='seed',
            index=models.Index(fields=['review_status', '-overall_score'], name='seeds_review_score_idx'),
        ),
        
        # Create SeedRawCapture model
        migrations.CreateModel(
            name='SeedRawCapture',
            fields=[
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('url', models.URLField(help_text='Originally requested URL', max_length=2000)),
                ('final_url', models.URLField(blank=True, help_text='Final URL after redirects', max_length=2000)),
                ('status_code', models.IntegerField(default=0, help_text='HTTP status code')),
                ('headers', models.JSONField(blank=True, default=dict, help_text='HTTP response headers')),
                ('content_type', models.CharField(blank=True, help_text='Content-Type header value', max_length=200)),
                ('body_hash', models.CharField(db_index=True, help_text='SHA-256 hash of raw body', max_length=64)),
                ('body_size', models.IntegerField(default=0, help_text='Original body size in bytes')),
                ('body_compressed', models.BinaryField(blank=True, help_text='Gzipped body if small enough for inline storage', null=True)),
                ('body_path', models.CharField(blank=True, help_text='Path to file storage if body too large for inline', max_length=500)),
                ('fetch_mode', models.CharField(choices=[('static', 'Static HTTP'), ('rendered', 'JS Rendered'), ('api', 'API Response')], default='static', max_length=20)),
                ('fetch_timestamp', models.DateTimeField(auto_now_add=True, help_text='When the fetch was performed')),
                ('fetch_duration_ms', models.IntegerField(default=0, help_text='Fetch duration in milliseconds')),
                ('discovery_run_id', models.UUIDField(blank=True, db_index=True, help_text='Discovery run that created this capture', null=True)),
                ('error', models.TextField(blank=True, help_text='Error message if fetch failed')),
                ('seed', models.ForeignKey(blank=True, help_text='Associated seed if promoted', null=True, on_delete=django.db.models.deletion.CASCADE, related_name='captures', to='seeds.seed')),
            ],
            options={
                'verbose_name': 'Seed Raw Capture',
                'verbose_name_plural': 'Seed Raw Captures',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='seedrawcapture',
            index=models.Index(fields=['body_hash'], name='seeds_capture_hash_idx'),
        ),
        migrations.AddIndex(
            model_name='seedrawcapture',
            index=models.Index(fields=['discovery_run_id'], name='seeds_capture_run_idx'),
        ),
        migrations.AddIndex(
            model_name='seedrawcapture',
            index=models.Index(fields=['fetch_timestamp'], name='seeds_capture_time_idx'),
        ),
        
        # Create DiscoveryRun model
        migrations.CreateModel(
            name='DiscoveryRun',
            fields=[
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('theme', models.CharField(help_text='Discovery theme/topic', max_length=200)),
                ('geography', models.JSONField(blank=True, default=list, help_text='Target countries/regions')),
                ('entity_types', models.JSONField(blank=True, default=list, help_text='Target entity types')),
                ('keywords', models.JSONField(blank=True, default=list, help_text='Additional keywords')),
                ('status', models.CharField(choices=[('pending', 'Pending'), ('running', 'Running'), ('completed', 'Completed'), ('failed', 'Failed'), ('cancelled', 'Cancelled')], db_index=True, default='pending', max_length=20)),
                ('started_at', models.DateTimeField(blank=True, null=True)),
                ('completed_at', models.DateTimeField(blank=True, null=True)),
                ('queries_generated', models.IntegerField(default=0)),
                ('urls_discovered', models.IntegerField(default=0)),
                ('captures_created', models.IntegerField(default=0)),
                ('seeds_created', models.IntegerField(default=0)),
                ('config', models.JSONField(blank=True, default=dict, help_text='Discovery configuration options')),
                ('error_message', models.TextField(blank=True)),
                ('started_by', models.ForeignKey(blank=True, help_text='User who started this discovery run', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='discovery_runs', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Discovery Run',
                'verbose_name_plural': 'Discovery Runs',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='discoveryrun',
            index=models.Index(fields=['status'], name='seeds_discovery_status_idx'),
        ),
        migrations.AddIndex(
            model_name='discoveryrun',
            index=models.Index(fields=['-created_at'], name='seeds_discovery_created_idx'),
        ),
    ]
