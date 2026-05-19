# Generated manually for LabelSchema.selected_for_labeling

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('labeling', '0002_remove_annotationdraft_labeling_draft_task_user_uniq_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='labelschema',
            name='selected_for_labeling',
            field=models.BooleanField(
                db_index=True,
                default=True,
                help_text='If enabled, this schema appears in the project labeling list and sidebar.',
                verbose_name='Show in labeling sidebar',
            ),
        ),
    ]
