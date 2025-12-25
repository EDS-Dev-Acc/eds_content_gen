from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('seeds', '0005_add_capture_metadata_fields'),
    ]

    operations = [
        # SeedRawCapture fields
        migrations.AddField(
            model_name='seedrawcapture',
            name='capture_version',
            field=models.CharField(blank=True, help_text='Version of capture/classification pipeline', max_length=20),
        ),
        migrations.AddField(
            model_name='seedrawcapture',
            name='charset_detected',
            field=models.CharField(blank=True, help_text='Detected character set for decoding', max_length=50),
        ),
        migrations.AddField(
            model_name='seedrawcapture',
            name='external_links_count',
            field=models.IntegerField(default=0, help_text='Count of external links on the page'),
        ),
        migrations.AddField(
            model_name='seedrawcapture',
            name='has_feeds',
            field=models.BooleanField(default=False, help_text='True if RSS/Atom feeds were detected'),
        ),
        migrations.AddField(
            model_name='seedrawcapture',
            name='has_sitemap',
            field=models.BooleanField(default=False, help_text='True if sitemap links were detected'),
        ),
        migrations.AddField(
            model_name='seedrawcapture',
            name='internal_links_count',
            field=models.IntegerField(default=0, help_text='Count of internal links on the page'),
        ),
        migrations.AddField(
            model_name='seedrawcapture',
            name='language_detected',
            field=models.CharField(blank=True, db_index=True, help_text='Detected language code', max_length=10),
        ),
        migrations.AddField(
            model_name='seedrawcapture',
            name='page_type',
            field=models.CharField(blank=True, choices=[('', 'Unknown'), ('article', 'Article'), ('list', 'List/Directory'), ('homepage', 'Homepage'), ('api', 'API')], help_text='Heuristic page type classification', max_length=20),
        ),
        migrations.AddField(
            model_name='seedrawcapture',
            name='schema_types',
            field=models.JSONField(blank=True, default=list, help_text='Schema.org types detected on the page'),
        ),
        migrations.AddField(
            model_name='seedrawcapture',
            name='storage_location',
            field=models.CharField(blank=True, help_text='Where the body is stored (inline/file/object)', max_length=50),
        ),
        migrations.AddField(
            model_name='seedrawcapture',
            name='title_length',
            field=models.IntegerField(default=0, help_text='Length of extracted title in characters'),
        ),
        migrations.AddField(
            model_name='seedrawcapture',
            name='validation_flags',
            field=models.JSONField(blank=True, default=list, help_text='Flags set during validation/classification'),
        ),
        migrations.AddField(
            model_name='seedrawcapture',
            name='word_count_estimate',
            field=models.IntegerField(default=0, help_text='Estimated word count of page body'),
        ),
        # Seed fields
        migrations.AddField(
            model_name='seed',
            name='approval_rationale',
            field=models.TextField(blank=True, help_text='Rationale recorded when approving seed'),
        ),
        migrations.AddField(
            model_name='seed',
            name='auto_promoted',
            field=models.BooleanField(default=False, help_text='True if seed was auto-promoted by threshold'),
        ),
        migrations.AddField(
            model_name='seed',
            name='etag',
            field=models.CharField(blank=True, help_text='ETag header value if present', max_length=100),
        ),
        migrations.AddField(
            model_name='seed',
            name='http_status_history',
            field=models.JSONField(blank=True, default=list, help_text='List of status codes observed across validations/fetches'),
        ),
        migrations.AddField(
            model_name='seed',
            name='js_required',
            field=models.BooleanField(default=False, help_text='Heuristic flag if JS is likely required'),
        ),
        migrations.AddField(
            model_name='seed',
            name='last_modified',
            field=models.CharField(blank=True, help_text='Last-Modified header value if present', max_length=100),
        ),
        migrations.AddField(
            model_name='seed',
            name='latency_ms',
            field=models.IntegerField(default=0, help_text='Last observed fetch latency in milliseconds'),
        ),
        migrations.AddField(
            model_name='seed',
            name='robots_result',
            field=models.CharField(blank=True, help_text='robots.txt evaluation result', max_length=50),
        ),
        migrations.AddField(
            model_name='seed',
            name='scoring_model_version',
            field=models.CharField(blank=True, help_text='Version identifier for scoring weights', max_length=50),
        ),
        # DiscoveryRun fields
        migrations.AddField(
            model_name='discoveryrun',
            name='failure_buckets',
            field=models.JSONField(blank=True, default=dict, help_text='Grouped failures (e.g., ssrf/tls/timeout/blocked)'),
        ),
        migrations.AddField(
            model_name='discoveryrun',
            name='fetch_failed',
            field=models.IntegerField(default=0, help_text='Number of capture attempts that failed'),
        ),
        migrations.AddField(
            model_name='discoveryrun',
            name='top_domains',
            field=models.JSONField(blank=True, default=list, help_text='Top domains encountered in this run'),
        ),
        migrations.AddField(
            model_name='discoveryrun',
            name='truncated_count',
            field=models.IntegerField(default=0, help_text='Number of captures truncated by size limits'),
        ),
    ]
