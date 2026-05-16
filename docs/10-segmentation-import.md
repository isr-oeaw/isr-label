# Segmentation import (polygon-first)

## Decision

ISR-label uses **polygon-first** representation for imported segmentation:

- Raster masks (PNG, semantic or indexed) are converted to **vector polygons** in `Annotation.result` (normalized coordinates, see [03-data-model.md](03-data-model.md)).
- **Native dense masks** (brush, COCO RLE as stored format) are **out of scope** for this iteration; they would require new result types, UI, and exporters.

**Labeling setup:** Use a schema with the **`polygon`** tool and define **`labels`** whose `id` values match the import mapping (pixel class → `label_id`). No schema JSON changes beyond the usual polygon template.

## Supported mask files

- **Grayscale (`L`)**: pixel value = class id (integer). Example: `0` = background, `1` = building.
- **Palette (`P`)**: palette index = class id (same mapping semantics).

Mask width/height must match the target **image** (after any EXIF transpose applied to the image asset), or import resizes the mask with nearest-neighbor to fit.

## Import methods

1. **Management command** (bulk, filesystem):

   ```bash
   python manage.py import_mask_prelabels \
     --dataset-id <id> \
     --mask-dir /path/to/masks \
     --map '{"1":"car","2":"person"}' \
     --background 0
   ```

   - For each `ImageAsset` in the dataset, looks for `<image_stem>.png` (or `.tif`) in `mask-dir` matching the image file basename (stem).
- If Django storage renames uploads (e.g. `s_Xk9q.png`), the importer also tries the **prefix before the first underscore** (e.g. `s.png`) and `{image_pk}.png`.
   - Requires a **task** per image; run “create label tasks” from the project UI/API first if needed.
   - `--replace`: delete existing non-cancelled annotations on those tasks before importing.

2. **REST API** (zip upload):

   `POST /api/v1/projects/{project_pk}/datasets/{dataset_pk}/import_masks/`

   - `multipart/form-data`: field `file` = ZIP of mask images (`stem.png`), field `mapping` = JSON object string mapping **string** keys for pixel values to `label_id` (e.g. `{"1":"car","255":"road"}`), optional `background`, `replace`.

## Operational notes

- **Filename matching** is by **stem** of the stored image file, or the part **before the first `_`** when the storage name includes a random suffix (e.g. mask `s.png` matches image `s_Ab12.png`), or `{image_primary_key}.png`.
- Unmapped pixel values are **skipped** (logged in command output).
- Very small contours are dropped (`min_area` / simplified threshold in code).
