# Generated migration for adding robots_unknown field

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('seeds', '0006_capture_metadata_enhancements'),
    ]

    operations = [
        migrations.AddField(
            model_name='seed',
            name='robots_unknown',
            field=models.BooleanField(
                default=False,
                help_text='True if robots.txt could not be fetched or parsed during validation'
            ),
        ),
    ]
