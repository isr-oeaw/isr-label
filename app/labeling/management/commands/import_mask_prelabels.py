"""Import PNG/TIF masks as polygon annotations (stem-matched to dataset images)."""

import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from labeling.models import LabelDataset
from labeling.services.mask_import import import_masks_for_dataset
from labeling.services.mask_to_polygons import parse_mapping_json


class Command(BaseCommand):
    help = (
        'Convert segmentation masks to polygon annotations. '
        'Requires a task per image; match mask files by image basename stem in --mask-dir.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--dataset-id', type=int, required=True)
        parser.add_argument(
            '--mask-dir',
            type=str,
            required=True,
            help='Directory containing <stem>.png (or .tif) per image basename',
        )
        parser.add_argument(
            '--map',
            type=str,
            required=True,
            help='JSON object: pixel class id (string keys) -> label_id, e.g. \'{"1":"car","2":"person"}\'',
        )
        parser.add_argument(
            '--background',
            type=str,
            default='0',
            help='Comma-separated pixel values to ignore (default: 0)',
        )
        parser.add_argument(
            '--replace',
            action='store_true',
            help='Delete existing non-cancelled annotations on matched tasks before import',
        )

    def handle(self, *args, **options):
        try:
            raw_map = json.loads(options['map'])
        except json.JSONDecodeError as e:
            raise CommandError(f'Invalid --map JSON: {e}') from e
        if not isinstance(raw_map, dict):
            raise CommandError('--map must be a JSON object')
        mapping = parse_mapping_json(raw_map)
        if not mapping:
            raise CommandError('--map produced no pixel class → label_id entries')

        bg_parts = [s.strip() for s in options['background'].split(',') if s.strip() != '']
        try:
            bg = frozenset(int(x) for x in bg_parts)
        except ValueError as e:
            raise CommandError(f'Invalid --background: {e}') from e

        ds = LabelDataset.objects.filter(pk=options['dataset_id']).select_related('project').first()
        if not ds:
            raise CommandError(f'LabelDataset {options["dataset_id"]} not found')

        mask_dir = Path(options['mask_dir'])
        if not mask_dir.is_dir():
            raise CommandError(f'Not a directory: {mask_dir}')

        stats = import_masks_for_dataset(
            ds,
            mapping,
            mask_dir=mask_dir,
            background_values=bg,
            replace=options['replace'],
            completed_by=None,
        )
        self.stdout.write(
            self.style.SUCCESS(
                'imported=%(imported)d missing_mask=%(missing_mask)d no_task=%(no_task)d '
                'mask_read_error=%(mask_read_error)d empty_regions=%(empty_regions)d'
                % stats
            )
        )
