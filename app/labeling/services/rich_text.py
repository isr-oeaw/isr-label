"""Sanitized rich text for annotator-facing UI (e.g. labeling instructions)."""

from __future__ import annotations

import bleach

_ALLOWED_TAGS = (
    'p',
    'br',
    'strong',
    'em',
    'b',
    'i',
    'u',
    'a',
    'ul',
    'ol',
    'li',
    'h2',
    'h3',
    'h4',
    'span',
    'div',
    'blockquote',
    'code',
    'pre',
)

_ALLOWED_ATTRS = {
    'a': ['href', 'title', 'rel', 'target'],
    '*': ['class'],
}

_ALLOWED_PROTOCOLS = frozenset(('http', 'https', 'mailto'))


def sanitize_labeling_instructions(raw: str | None) -> str:
    """Return HTML safe to embed; empty string if there is no content."""
    if not raw or not str(raw).strip():
        return ''
    return bleach.clean(
        str(raw).strip(),
        tags=_ALLOWED_TAGS,
        attributes=_ALLOWED_ATTRS,
        protocols=_ALLOWED_PROTOCOLS,
        strip=True,
    )
