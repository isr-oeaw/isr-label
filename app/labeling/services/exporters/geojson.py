from __future__ import annotations

from typing import Any


def project_images_geojson(project) -> dict[str, Any]:
    """FeatureCollection: one Point per image with location."""
    from labeling.models import ImageAsset
    features = []
    for img in ImageAsset.objects.filter(dataset__project=project).exclude(location__isnull=True).iterator(
        chunk_size=100
    ):
        lon, lat = img.location.coords
        features.append(
            {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [lon, lat],
                },
                "properties": {
                    "id": img.id,
                    "filename": img.file.name if img.file else None,
                },
            }
        )
    return {"type": "FeatureCollection", "features": features}
