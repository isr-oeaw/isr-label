"""Thumbnail and metadata population for ImageAsset."""

from __future__ import annotations

import io
import logging
from io import BytesIO
from typing import TYPE_CHECKING

from django.core.files.base import ContentFile
from django.utils import timezone
from PIL import Image, ImageOps

from .exif import extract_capture_time, extract_gps_from_pillow_image, get_exif_data

if TYPE_CHECKING:
    from labeling.models import ImageAsset

log = logging.getLogger(__name__)
TH_SIZE = (320, 240)


def populate_from_upload(instance: "ImageAsset", save: bool = True) -> None:
    """Set dimensions, checksum, exif, location, captured_at, checksum."""
    f = instance.file
    f.open("rb")
    data = f.read()
    f.close()
    import hashlib

    instance.checksum = hashlib.sha256(data).hexdigest()

    with Image.open(BytesIO(data)) as im:
        im = ImageOps.exif_transpose(im)
        instance.width, instance.height = im.size
        instance.exif = get_exif_data(im) or {}
        pt = extract_gps_from_pillow_image(im)
        if pt:
            instance.location = pt
        ct = extract_capture_time(im)
        if ct and timezone.is_naive(ct):
            ct = timezone.make_aware(ct, timezone.get_current_timezone())
        if ct:
            instance.captured_at = ct

    if save:
        instance.save(
            update_fields=["checksum", "width", "height", "exif", "location", "captured_at"]
        )


def generate_thumbnail(instance: "ImageAsset", save: bool = True) -> None:
    if not instance.file:
        return
    try:
        instance.file.open("rb")
        raw = instance.file.read()
        instance.file.close()
        with Image.open(BytesIO(raw)) as im:
            im = ImageOps.exif_transpose(im)
            im.thumbnail(TH_SIZE, Image.Resampling.LANCZOS)
            if im.mode in ("RGBA", "P"):
                im = im.convert("RGB")
            out = io.BytesIO()
            im.save(out, format="JPEG", quality=85)
            out.seek(0)
            name = f"thumb_{instance.pk or 'new'}.jpg"
            instance.thumbnail.save(name, ContentFile(out.read()), save=save)
    except Exception as e:
        log.warning("thumbnail: %s", e)
