from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sources', '0011_network_options'),
    ]

    operations = [
        migrations.AddField(
            model_name='crawljob',
            name='selection_snapshot',
            field=models.JSONField(blank=True, default=dict, help_text='Snapshot of sources, seeds, and overrides captured at launch/clone time', verbose_name='Selection Snapshot'),
        ),
    ]
