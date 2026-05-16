# Geospatial (EXIF + PostGIS)

## PostGIS

- Docker image: `postgis/postgis:16-3.4` (dev), align with `docker-compose.prod.yml`.
- Django: `django.contrib.gis` + engine `django.contrib.gis.db.backends.postgis`.
- On fresh DB, run: `python manage.py migrate` (includes PostGIS extension if using standard PostGIS image — system usually has `postgis` template).
- `ImageAsset.location`: `PointField(srid=4326, geography=True, null=True, blank=True)` for distance queries, or `PointField(4326)` with GiST index.

**Note:** For simplest deployment, we use `PointField(srid=4326)` with `spatial_index=True` (default in GeoDjango for PostGIS).

## EXIF (Pillow)

- On save, read `Image.open` and `getexif()`.
- GPS IFD → convert DMS to decimal degrees, build `Point(lon, lat, srid=4326)`.
- Store full raw EXIF subset in `exif` JSON (optional) for audit.

## Coordinates and ZIP export

- **`ImageAsset.location`** stores WGS84 points when EXIF/GPS is present; annotation JSON stays normalized in image space.
- **ZIP export** (`project_export` / download) includes **COCO** and **YOLO** only—no GeoJSON bundle.

- Not in scope; optional `altitude` from EXIF if present.

## Coordinate normalization

- **Image annotation JSON** is always **normalized 0-1 in image space**, independent of map coordinates on the asset.
