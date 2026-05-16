"""Apply mask files as polygon pre-label annotations on dataset tasks."""

from __future__ import annotations

import logging
import shutil
import tempfile
import zipfile
from collections import Counter
from io import BytesIO
from pathlib import Path
from typing import Any

from django.db import transaction

from labeling.models import Annotation, ImageAsset, LabelDataset, Task
from labeling.services.mask_to_polygons import (
    load_mask_as_class_ids,
    mask_array_to_polygon_regions,
)

log = logging.getLogger(__name__)


def _image_stem(asset: ImageAsset) -> str:
    name = (asset.file.name or '').rsplit('/', 1)[-1]
    if '.' in name:
        return name.rsplit('.', 1)[0]
    return name or str(asset.pk)


def _mask_stem_candidates(asset: ImageAsset) -> list[str]:
    """Possible mask file stems: storage stem, image pk, upload prefix before first '_'."""
    seen: set[str] = set()
    out: list[str] = []

    def add(x: str) -> None:
        if x and x not in seen:
            seen.add(x)
            out.append(x)

    stem = _image_stem(asset)
    add(stem)
    add(str(asset.pk))
    if '_' in stem:
        add(stem.split('_', 1)[0])
    return out


def _find_mask_path(mask_dir: Path, stem: str) -> Path | None:
    for ext in ('.png', '.tif', '.tiff', '.PNG', '.TIF', '.TIFF'):
        p = mask_dir / f'{stem}{ext}'
        if p.is_file():
            return p
    return None


def import_masks_for_dataset(
    dataset: LabelDataset,
    mapping: dict[int, str],
    *,
    mask_dir: Path | None = None,
    mask_paths_by_stem: dict[str, Path] | None = None,
    background_values: frozenset[int] | None = None,
    replace: bool = False,
    completed_by=None,
) -> dict[str, Any]:
    """
    For each image in ``dataset`` with a task and a matching mask file, create one
    ``Annotation`` with polygon ``result`` (or replace existing annotations).

    Either ``mask_dir`` (stem.png) or ``mask_paths_by_stem`` must be set.
    """
    if not mapping:
        raise ValueError('mapping must not be empty')
    if mask_dir is None and not mask_paths_by_stem:
        raise ValueError('mask_dir or mask_paths_by_stem required')

    bg = background_values if background_values is not None else frozenset({0})
    stats: Counter[str] = Counter()

    images = ImageAsset.objects.filter(dataset=dataset).select_related('dataset')
    for img in images:
        mpath: Path | None = None
        if mask_paths_by_stem is not None:
            for cand in _mask_stem_candidates(img):
                mpath = mask_paths_by_stem.get(cand)
                if mpath and mpath.is_file():
                    break
            if not mpath:
                mpath = None
        else:
            for cand in _mask_stem_candidates(img):
                mpath = _find_mask_path(mask_dir, cand)  # type: ignore[arg-type]
                if mpath:
                    break
        if not mpath or not mpath.is_file():
            stats['missing_mask'] += 1
            continue

        task = (
            Task.objects.filter(image=img, project=dataset.project)
            .select_related('schema')
            .order_by('id')
            .first()
        )
        if not task:
            stats['no_task'] += 1
            continue

        try:
            arr, _wh = load_mask_as_class_ids(mpath.read_bytes())
        except Exception as e:
            log.warning('mask read failed %s: %s', mpath, e)
            stats['mask_read_error'] += 1
            continue

        regions = mask_array_to_polygon_regions(
            arr,
            img.width,
            img.height,
            mapping,
            background_values=bg,
        )
        if not regions:
            stats['empty_regions'] += 1
            if replace:
                with transaction.atomic():
                    Annotation.objects.filter(task=task, was_cancelled=False).delete()
            continue

        with transaction.atomic():
            if replace:
                Annotation.objects.filter(task=task, was_cancelled=False).delete()
            Annotation.objects.create(
                task=task,
                completed_by=completed_by,
                result=regions,
                was_cancelled=False,
                ground_truth=False,
                status=Annotation.Status.SUBMITTED,
            )
        stats['imported'] += 1

    return {
        'imported': stats['imported'],
        'missing_mask': stats['missing_mask'],
        'no_task': stats['no_task'],
        'mask_read_error': stats['mask_read_error'],
        'empty_regions': stats['empty_regions'],
    }


def _extract_zip_masks(zip_bytes: bytes) -> tuple[Path, dict[str, Path]]:
    td = Path(tempfile.mkdtemp(prefix='maskzip_'))
    by_stem: dict[str, Path] = {}
    with zipfile.ZipFile(BytesIO(zip_bytes), 'r') as zf:
        for zinfo in zf.infolist():
            if zinfo.is_dir():
                continue
            safe_name = Path(zinfo.filename).name
            if not safe_name:
                continue
            suf = Path(safe_name).suffix.lower()
            if suf not in ('.png', '.tif', '.tiff'):
                continue
            dest = td / safe_name
            with zf.open(zinfo, 'r') as src, dest.open('wb') as dst:
                shutil.copyfileobj(src, dst)
    for p in td.iterdir():
        if not p.is_file():
            continue
        if p.suffix.lower() not in ('.png', '.tif', '.tiff'):
            continue
        by_stem[p.stem] = p
    return td, by_stem


def import_masks_from_zip(
    dataset: LabelDataset,
    zip_bytes: bytes,
    mapping: dict[int, str],
    *,
    background_values: frozenset[int] | None = None,
    replace: bool = False,
    completed_by=None,
) -> dict[str, Any]:
    td, by_stem = _extract_zip_masks(zip_bytes)
    try:
        return import_masks_for_dataset(
            dataset,
            mapping,
            mask_paths_by_stem=by_stem,
            background_values=background_values,
            replace=replace,
            completed_by=completed_by,
        )
    finally:
        shutil.rmtree(td, ignore_errors=True)
