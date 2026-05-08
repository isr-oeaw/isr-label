# ProjectMembership, migrate from collaborators, remove collaborators

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def migrate_to_membership(apps, schema_editor):
    Project = apps.get_model('projects', 'Project')
    ProjectMembership = apps.get_model('projects', 'ProjectMembership')
    for project in Project.objects.all().only('id', 'owner_id').iterator():
        ProjectMembership.objects.get_or_create(
            project=project,
            user_id=project.owner_id,
            defaults={'role': 'admin'},
        )
        # Historical Project still has M2M collaborators
        for u in project.collaborators.all():
            if u.id == project.owner_id:
                continue
            ProjectMembership.objects.get_or_create(
                project=project,
                user_id=u.id,
                defaults={'role': 'annotator'},
            )


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('projects', '0002_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='ProjectMembership',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                (
                    'role',
                    models.CharField(
                        choices=[
                            ('admin', 'Admin'),
                            ('reviewer', 'Reviewer'),
                            ('annotator', 'Annotator'),
                            ('viewer', 'Viewer'),
                        ],
                        default='annotator',
                        max_length=20,
                        verbose_name='Role',
                    ),
                ),
                ('joined_at', models.DateTimeField(auto_now_add=True, verbose_name='Joined at')),
                (
                    'project',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='memberships',
                        to='projects.project',
                        verbose_name='Project',
                    ),
                ),
                (
                    'user',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='project_memberships',
                        to=settings.AUTH_USER_MODEL,
                        verbose_name='User',
                    ),
                ),
            ],
            options={
                'verbose_name': 'Project membership',
                'verbose_name_plural': 'Project memberships',
                'ordering': ['project', 'user'],
                'unique_together': {('project', 'user')},
            },
        ),
        migrations.AddIndex(
            model_name='projectmembership',
            index=models.Index(fields=['project', 'user'], name='projects_pr_project_usr_idx'),
        ),
        migrations.RunPython(migrate_to_membership, noop_reverse),
        migrations.RemoveField(
            model_name='project',
            name='collaborators',
        ),
    ]
