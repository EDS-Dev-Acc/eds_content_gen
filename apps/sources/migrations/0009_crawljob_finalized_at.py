# Generated migration for Phase 18 hardening
# Adds finalized_at field for idempotent finalization guard

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sources', '0008_add_composite_indexes'),
    ]

    operations = [
        migrations.AddField(
            model_name='crawljob',
            name='finalized_at',
            field=models.DateTimeField(
                null=True,
                blank=True,
                verbose_name='Finalized At',
                help_text='When aggregation was finalized (idempotency guard)'
            ),
        ),
        migrations.AddIndex(
            model_name='crawljob',
            index=models.Index(fields=['finalized_at'], name='crawl_jobs_finalized_at_idx'),
        ),
    ]
