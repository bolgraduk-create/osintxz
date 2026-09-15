"""Normalization helpers for registry lookup keys.

Normalization is for search only. It never proves identity or merges entities.
"""
from __future__ import annotations

import unicodedata


def normalize_ua_edr_name(value: str) -> str:
    text = unicodedata.normalize("NFKC", value or "")
    text = text.replace("’", "'").replace("`", "'").replace("ʼ", "'")
    return " ".join(text.upper().split())
