"""Extract GPS and metadata from image bytes using Pillow."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Optional, Tuple

from django.contrib.gis.geos import Point
from PIL import ExifTags, Image, TiffImagePlugin

log = logging.getLogger(__name__)


def _dms_to_dd(dms: Tuple, ref: str) -> float:
    d, m, s = dms[0], dms[1], dms[2]
    dd = float(d) + float(m) / 60.0 + float(s) / 3600.0
    if ref in ("S", "W"):
        dd = -dd
    return dd


def get_exif_data(img: Image.Image) -> dict[str, Any]:
    exif: dict[str, Any] = {}
    try:
        raw = img.getexif() or {}
        for k, v in raw.items():
            name = ExifTags.TAGS.get(k, str(k))
            if isinstance(v, (bytes, memoryview, TiffImagePlugin.IFDRational)):
                try:
                    v = str(v)
                except Exception:
                    v = repr(v)
            exif[str(name)] = v
    except Exception as e:
        log.debug("exif read: %s", e)
    return exif


def extract_gps_from_pillow_image(img: Image.Image) -> Optional[Point]:
    try:
        ex = img.getexif()
        if not ex:
            return None
        try:
            ifd = ExifTags.IFD.GPSInfo
        except AttributeError:
            ifd = 0x8825
        gps = ex.get_ifd(ifd) if hasattr(ex, "get_ifd") else None
        if not gps or not len(gps):
            return None
        lat, lat_ref = gps.get(2), gps.get(1)
        lon, lon_ref = gps.get(4), gps.get(3)
        if not lat or not lon or not lat_ref or not lon_ref:
            return None
        lat_d = _dms_to_dd(lat, str(lat_ref))
        lon_d = _dms_to_dd(lon, str(lon_ref))
        return Point(lon_d, lat_d, srid=4326)
    except Exception as e:
        log.debug("gps extract: %s", e)
        return None


def extract_capture_time(img: Image.Image) -> Optional[datetime]:
    try:
        ex = img.getexif()
        if not ex:
            return None
        for tag, val in ex.items():
            if ExifTags.TAGS.get(tag) == "DateTimeOriginal":
                return datetime.strptime(str(val)[:19], "%Y:%m:%d %H:%M:%S")
    except Exception:
        pass
    return None
