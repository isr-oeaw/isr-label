from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('auth', '0012_alter_user_first_name_max_length'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('labeling', '0004_labelschema_single_per_project'),
    ]

    operations = [
        migrations.AddField(
            model_name='labeldataset',
            name='assigned_groups',
            field=models.ManyToManyField(
                blank=True,
                help_text='Site-wide Django groups; members may label this dataset when restrictions apply.',
                related_name='assigned_label_datasets',
                to='auth.group',
                verbose_name='Assigned groups',
            ),
        ),
        migrations.AddField(
            model_name='labeldataset',
            name='assigned_users',
            field=models.ManyToManyField(
                blank=True,
                help_text='If empty along with groups, all project labelers may work on this dataset. Otherwise only listed users (or members of assigned groups) see these tasks.',
                related_name='assigned_label_datasets',
                to=settings.AUTH_USER_MODEL,
                verbose_name='Assigned users',
            ),
        ),
    ]
