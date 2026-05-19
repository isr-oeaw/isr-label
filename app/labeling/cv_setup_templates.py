"""
Computer-vision labeling setup templates (Label Studio–style starters).

Each template maps to ``LabelSchema.config`` JSON (tools, labels, allow_empty,
multi_label). Optional lineage is stored under ``config['_meta']['template_slug']``.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any

from django.utils.translation import gettext_lazy as _

ALL_CV_TOOLS = ('classification', 'rect', 'polygon', 'point')

TOOL_DISPLAY: dict[str, Any] = {
    'classification': _('Image classification (whole image)'),
    'rect': _('Bounding box'),
    'polygon': _('Polygon / region'),
    'point': _('Point / keypoint'),
}

TOOL_CHOICES: list[tuple[str, Any]] = [(t, TOOL_DISPLAY[t]) for t in ALL_CV_TOOLS]


@dataclass(frozen=True)
class CVSetupTemplate:
    slug: str
    title: Any  # lazy translation
    description_any: Any
    category: str  # classification | detection | segmentation | keypoints | mixed
    tools: tuple[str, ...]
    default_labels: tuple[dict[str, str], ...]
    allow_empty: bool = True
    multi_label: bool = False

    @property
    def description(self):
        return self.description_any

    def tool_badges(self) -> list[tuple[str, Any]]:
        """(stored tool id, lazy label) for template cards."""
        return [(t, TOOL_DISPLAY[t]) for t in self.tools]


def _labels_from_defaults(rows: tuple[dict[str, str], ...]) -> list[dict[str, str]]:
    return [copy.deepcopy(dict(r)) for r in rows]


CV_SETUP_TEMPLATES: tuple[CVSetupTemplate, ...] = (
    CVSetupTemplate(
        slug='image_classification',
        title=_('Image classification'),
        description_any=_('Choose classes per image (no regions).'),
        category='classification',
        tools=('classification',),
        default_labels=(
            {'id': 'cat', 'name': 'Cat', 'color': '#3498db', 'hotkey': '1'},
            {'id': 'dog', 'name': 'Dog', 'color': '#e74c3c', 'hotkey': '2'},
        ),
        allow_empty=True,
        multi_label=False,
    ),
    CVSetupTemplate(
        slug='bounding_boxes',
        title=_('Bounding boxes'),
        description_any=_('Draw rectangles around objects.'),
        category='detection',
        tools=('rect',),
        default_labels=(
            {'id': 'obj', 'name': 'Object', 'color': '#e74c3c', 'hotkey': '1'},
        ),
    ),
    CVSetupTemplate(
        slug='bbox_and_class',
        title=_('Bounding boxes + classification'),
        description_any=_('Regions and image-level labels.'),
        category='mixed',
        tools=('classification', 'rect'),
        default_labels=(
            {'id': 'vehicle', 'name': 'Vehicle', 'color': '#2980b9', 'hotkey': '1'},
            {'id': 'person', 'name': 'Person', 'color': '#27ae60', 'hotkey': '2'},
        ),
        multi_label=True,
    ),
    CVSetupTemplate(
        slug='polygons',
        title=_('Polygons / instance masks'),
        description_any=_('Segment regions with polygons.'),
        category='segmentation',
        tools=('polygon',),
        default_labels=(
            {'id': 'region', 'name': 'Region', 'color': '#9b59b6', 'hotkey': '1'},
        ),
    ),
    CVSetupTemplate(
        slug='points_keypoints',
        title=_('Points / keypoints'),
        description_any=_('Mark single-point locations.'),
        category='keypoints',
        tools=('point',),
        default_labels=(
            {'id': 'kp', 'name': 'Keypoint', 'color': '#f39c12', 'hotkey': '1'},
        ),
    ),
    CVSetupTemplate(
        slug='mixed',
        title=_('Mixed tools'),
        description_any=_('Classification, boxes, polygons, and points together.'),
        category='mixed',
        tools=tuple(ALL_CV_TOOLS),
        default_labels=(
            {'id': 'ex1', 'name': 'Example', 'color': '#e74c3c', 'hotkey': '1'},
        ),
    ),
)

_SLUG_MAP = {t.slug: t for t in CV_SETUP_TEMPLATES}


def get_cv_template(slug: str) -> CVSetupTemplate | None:
    return _SLUG_MAP.get(slug)


def iter_cv_setup_templates() -> tuple[CVSetupTemplate, ...]:
    return CV_SETUP_TEMPLATES


def template_bootstrap_icon(t: CVSetupTemplate) -> str:
    """Bootstrap Icon name (without ``bi-`` prefix) for labeling setup cards."""
    by_slug = {
        'image_classification': 'tags',
        'bounding_boxes': 'bounding-box',
        'bbox_and_class': 'diagram-3',
        'polygons': 'pentagon',
        'points_keypoints': 'geo-alt',
        'mixed': 'grid-3x3-gap',
    }
    return by_slug.get(t.slug, 'puzzle')


def build_config_from_template(slug: str) -> dict[str, Any] | None:
    t = get_cv_template(slug)
    if not t:
        return None
    return {
        'tools': list(t.tools),
        'labels': _labels_from_defaults(t.default_labels),
        'allow_empty': t.allow_empty,
        'multi_label': t.multi_label,
        '_meta': {'template_slug': t.slug},
    }

