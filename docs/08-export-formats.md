# Export formats

## Internal JSON

- `Annotation.result` as stored; list of region dicts (see [03-data-model](03-data-model.md)).

## YOLO (txt per image)

- For each `rect` in result: one line per box: `class_id cx cy w h` (0-1 or relative to model — we use 0-1, document that training scripts may scale to pixel space using image width/height in sidecar or dataset YAML).
- Class id from ordered `labels` in schema at export time.
- One `.txt` per image filename, matching stem.

## COCO

- `info`, `licenses` (empty), `categories` from label schema, `images` from `ImageAsset` (width, height, file name), `annotations` with `bbox` in **pixels** (converted from normalized using image dimensions) and `category_id`.

## GeoJSON (FeatureCollection)

- `ImageAsset` with `location`: `Point` geometry.
- `properties`: `image_url`, `project_id`, `task_id`, optional summary of class counts.
- Subfolder `annotations/` with optional per-image GeoJSON for GIS workflows.

## Export endpoint

- `POST /api/v1/projects/{id}/export/?format=zip&variants=coco,yolo,geojson`
- Returns `application/zip` with a manifest `README.txt`.

## Consensus (Phase 4)

- When `overlap>1`, consensus command writes `consensus.json` in export or a separate `management` command for offline merging.
