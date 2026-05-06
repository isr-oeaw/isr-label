# Initial labeling models (PostGIS + GeoDjango)

import django.contrib.gis.db.models.fields
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('projects', '0003_project_membership'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.RunSQL(
            sql="CREATE EXTENSION IF NOT EXISTS postgis;",
            reverse_sql=migrations.RunSQL.noop,
        ),
        migrations.CreateModel(
            name='LabelDataset',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=200, verbose_name='Name')),
                ('description', models.TextField(blank=True, verbose_name='Description')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                (
                    'project',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='labeling_datasets',
                        to='projects.project',
                        verbose_name='Project',
                    ),
                ),
            ],
            options={
                'verbose_name': 'Label dataset',
                'verbose_name_plural': 'Label datasets',
                'ordering': ['name'],
            },
        ),
        migrations.CreateModel(
            name='LabelSchema',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('version', models.PositiveIntegerField(default=1, verbose_name='Version')),
                ('config', models.JSONField(blank=True, default=dict, verbose_name='Configuration')),
                ('is_active', models.BooleanField(db_index=True, default=True, verbose_name='Active')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                (
                    'project',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='label_schemata',
                        to='projects.project',
                        verbose_name='Project',
                    ),
                ),
            ],
            options={
                'verbose_name': 'Label schema',
                'verbose_name_plural': 'Label schemata',
                'ordering': ['-version', '-id'],
            },
        ),
        migrations.CreateModel(
            name='ImageAsset',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                (
                    'file',
                    models.ImageField(max_length=512, upload_to='labeling/images/%Y/%m/', verbose_name='File'),
                ),
                ('width', models.PositiveIntegerField(default=0)),
                ('height', models.PositiveIntegerField(default=0)),
                (
                    'location',
                    django.contrib.gis.db.models.fields.PointField(
                        blank=True, geography=False, null=True, spatial_index=True, srid=4326, verbose_name='Location (WGS84)'
                    ),
                ),
                ('captured_at', models.DateTimeField(blank=True, null=True, verbose_name='Captured at')),
                ('exif', models.JSONField(blank=True, default=dict)),
                ('checksum', models.CharField(blank=True, db_index=True, max_length=64)),
                (
                    'thumbnail',
                    models.ImageField(blank=True, max_length=512, null=True, upload_to='labeling/thumbs/%Y/%m/'),
                ),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                (
                    'dataset',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='images',
                        to='labeling.labeldataset',
                        verbose_name='Dataset',
                    ),
                ),
            ],
            options={
                'verbose_name': 'Image',
                'verbose_name_plural': 'Images',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='Task',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('inner_id', models.BigIntegerField(db_index=True, verbose_name='Inner id')),
                ('overlap', models.PositiveSmallIntegerField(default=1, verbose_name='Required annotations')),
                ('is_labeled', models.BooleanField(db_index=True, default=False, verbose_name='Is done')),
                ('total_annotations', models.PositiveIntegerField(default=0)),
                ('cancelled_annotations', models.PositiveIntegerField(default=0)),
                ('data', models.JSONField(blank=True, default=dict, verbose_name='Extra data')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                (
                    'image',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name='tasks',
                        to='labeling.imageasset',
                        verbose_name='Image',
                    ),
                ),
                (
                    'project',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='label_tasks',
                        to='projects.project',
                        verbose_name='Project',
                    ),
                ),
                (
                    'schema',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name='tasks',
                        to='labeling.labelschema',
                        verbose_name='Schema',
                    ),
                ),
            ],
            options={
                'verbose_name': 'Label task',
                'verbose_name_plural': 'Label tasks',
                'ordering': ['project', 'inner_id'],
            },
        ),
        migrations.CreateModel(
            name='Annotation',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('result', models.JSONField(default=list, verbose_name='Result')),
                ('was_cancelled', models.BooleanField(db_index=True, default=False)),
                ('ground_truth', models.BooleanField(default=False)),
                (
                    'lead_time',
                    models.FloatField(
                        blank=True, help_text='Seconds from open to submit', null=True, verbose_name='Lead time'
                    ),
                ),
                (
                    'status',
                    models.CharField(
                        choices=[
                            ('submitted', 'Submitted'),
                            ('approved', 'Approved'),
                            ('rejected', 'Rejected'),
                            ('needs_revision', 'Needs revision'),
                        ],
                        db_index=True,
                        default='submitted',
                        max_length=20,
                    ),
                ),
                ('schema_version', models.PositiveIntegerField(default=1)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                (
                    'completed_by',
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='label_annotations',
                        to=settings.AUTH_USER_MODEL,
                        verbose_name='Completed by',
                    ),
                ),
                (
                    'parent_annotation',
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='revisions',
                        to='labeling.annotation',
                    ),
                ),
                (
                    'task',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='annotations',
                        to='labeling.task',
                        verbose_name='Task',
                    ),
                ),
            ],
            options={
                'verbose_name': 'Annotation',
                'verbose_name_plural': 'Annotations',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='AnnotationDraft',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('result', models.JSONField(default=list)),
                ('lead_time', models.FloatField(default=0)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                (
                    'task',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, related_name='drafts', to='labeling.task'
                    ),
                ),
                (
                    'user',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='label_drafts',
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                'verbose_name': 'Annotation draft',
                'verbose_name_plural': 'Annotation drafts',
            },
        ),
        migrations.CreateModel(
            name='TaskLock',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('expire_at', models.DateTimeField(db_index=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                (
                    'task',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, related_name='locks', to='labeling.task'
                    ),
                ),
                (
                    'user',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL
                    ),
                ),
            ],
            options={
                'verbose_name': 'Task lock',
                'verbose_name_plural': 'Task locks',
            },
        ),
        migrations.AddConstraint(
            model_name='labeldataset',
            constraint=models.UniqueConstraint(fields=('project', 'name'), name='labeling_lbl_dataset_uniq'),
        ),
        migrations.AddConstraint(
            model_name='labelschema',
            constraint=models.UniqueConstraint(fields=('project', 'version'), name='labeling_lbl_schema_uniq'),
        ),
        migrations.AddIndex(
            model_name='imageasset',
            index=models.Index(fields=['dataset', 'created_at'], name='labeling_im_ds_created_idx'),
        ),
        migrations.AddIndex(
            model_name='task',
            index=models.Index(fields=['project', 'is_labeled'], name='labeling_task_prj_lbl_idx'),
        ),
        migrations.AddIndex(
            model_name='annotation',
            index=models.Index(fields=['task', 'status'], name='labeling_ann_task_st_idx'),
        ),
        migrations.AddConstraint(
            model_name='task',
            constraint=models.UniqueConstraint(
                fields=('project', 'inner_id'), name='labeling_task_project_inner_id_uniq'
            ),
        ),
        migrations.AddConstraint(
            model_name='annotationdraft',
            constraint=models.UniqueConstraint(
                fields=('task', 'user'), name='labeling_draft_task_user_uniq'
            ),
        ),
        migrations.AddConstraint(
            model_name='tasklock',
            constraint=models.UniqueConstraint(
                fields=('task', 'user'), name='labeling_lock_task_user_uniq'
            ),
        ),
    ]
