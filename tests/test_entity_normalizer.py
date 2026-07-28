"""
Tests for EntityNormalizer.
"""

from app.entity_resolution.normalizer import (
    EntityNormalizer,
)


def test_email():

    n = EntityNormalizer()

    assert (
        n.normalize_email(
            " John@Mail.COM "
        )
        ==
        "john@mail.com"
    )


def test_phone():

    n = EntityNormalizer()

    assert (
        n.normalize_phone(
            "+38 (050) 111-22-33"
        )
        ==
        "380501112233"
    )


def test_username():

    n = EntityNormalizer()

    assert (
        n.normalize_username(
            "@John_Smith"
        )
        ==
        "john_smith"
    )


def test_domain():

    n = EntityNormalizer()

    assert (
        n.normalize_domain(
            "https://Example.COM/"
        )
        ==
        "example.com"
    )