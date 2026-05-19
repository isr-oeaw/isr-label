# Export formats

## Internal JSON

- `Annotation.result` as stored; list of region dicts (see [03-data-model](03-data-model.md)).

## YOLO (txt per image)

- For each `rect` in result: one line per box: `class_id cx cy w h` (0-1 or relative to model — we use 0-1, document that training scripts may scale to pixel space using image width/height in sidecar or dataset YAML).
- Class id from ordered `labels` in schema at export time.
- One `.txt` per image filename, matching stem.

## COCO

- `info`, `licenses` (empty), `categories` from label schema, `images` from `ImageAsset` (width, height, file name), `annotations` with `bbox` in **pixels** (converted from normalized using image dimensions).
- **`type: rect`** in `Annotation.result`: `bbox` only (XYWH).
- **`type: polygon`**: `bbox` as tight axis-aligned box around the polygon and **`segmentation`**: list of one ring `[x1,y1,x2,y2,...]` in **absolute pixels** (COCO list-of-polygon-rings). `area` is the polygon area via shoelace (ring not self-crossing).

## Export endpoint

- `POST /api/v1/projects/{id}/export/?format=zip&variants=coco,yolo`
- Returns `application/zip` with a manifest `README.txt`.

## Consensus (Phase 4)

- When `overlap>1`, consensus command writes `consensus.json` in export or a separate `management` command for offline merging.
