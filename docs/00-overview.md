# Overview

## Goals

- **Projects**: Create and manage research projects; scope labeling work and membership.
- **Geolocated images**: Upload images, extract EXIF/GPS when present, store optional coordinates in PostGIS (`ImageAsset.location`).
- **Label tasks**: One task per (project, image, schema) with overlap, locks, and drafts.
- **Annotation UI**: Label Studio–like workflow: tools (classification, box, polygon, point), keyboard shortcuts, zoom/pan, submit/skip.
- **Users & groups**: Per-project roles (admin, reviewer, annotator, viewer) via `ProjectMembership`.
- **Export**: COCO and YOLO ZIP bundles for downstream ML.

## Non-goals (current phase)

- Video or audio annotation
- Real-time co-editing (WebSockets); soft DB locks only
- ML pre-annotation / active learning backends
- Mobile-first UI

## Glossary

| Term | Meaning |
|------|---------|
| **Project** | Top-level container; `projects.Project` |
| **Membership** | User + project + role; `ProjectMembership` |
| **Dataset** | Logical group of images within a project; `labeling.Dataset` |
| **Image asset** | Stored file + dimensions + optional Geo + EXIF; `labeling.ImageAsset` |
| **Label schema** | JSON config (tools, labels, colors); `labeling.LabelSchema` |
| **Task** | One labeling job for an image; `labeling.Task` |
| **Annotation** | Submitted result (JSON) by one user; `labeling.Annotation` |
| **Draft** | Autosaved work in progress; `labeling.AnnotationDraft` |
| **Lock** | Soft lock to reduce duplicate work; `labeling.TaskLock` |
