# Generated migration for pages_crawled field

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sources', '0002_crawljob'),
    ]

    operations = [
        migrations.AddField(
            model_name='crawljob',
            name='pages_crawled',
            field=models.IntegerField(default=0, help_text='Number of pages crawled (for pagination)', verbose_name='Pages Crawled'),
        ),
    ]
