"""
    .. module:: test_tagging
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: MetalTagTranslator tests — string-list encoding round trip.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


import pytest

from ccai.provisioning.venues.equinix_metal.metalerrors import (
    MetalValidationError
)
from ccai.provisioning.venues.equinix_metal.metaltagtranslator import (
    MetalTagTranslator, base_resource_tags, OWNER_TAG_KEY, RUN_ID_TAG_KEY
)


def test_to_metal_encodes_key_value_strings() -> None:
    """
        Each neutral pair becomes one ``key=value`` string, key-sorted.
    """
    neutral = {"b": "2", "a": "1"}
    encoded = MetalTagTranslator.to_metal(neutral_tags=neutral)
    assert encoded == ["a=1", "b=2"]
    return


def test_to_metal_none_returns_empty() -> None:
    """
        A None neutral dict encodes to an empty list.
    """
    encoded = MetalTagTranslator.to_metal(neutral_tags=None)
    assert encoded == []
    return


def test_from_metal_recovers_neutral_dict() -> None:
    """
        from_metal recovers a key-sorted flat neutral tag dict.
    """
    decoded = MetalTagTranslator.from_metal(strings=["x=9", "a=1"])
    assert decoded == {"a": "1", "x": "9"}
    return


def test_to_metal_rejects_non_string_value() -> None:
    """
        A non-string tag value is rejected at encode time.
    """
    with pytest.raises(MetalValidationError):
        MetalTagTranslator.to_metal(neutral_tags={"a": 1})
    return


def test_to_metal_rejects_equals_in_key() -> None:
    """
        A key containing '=' is rejected — it would corrupt the round trip.
    """
    with pytest.raises(MetalValidationError):
        MetalTagTranslator.to_metal(neutral_tags={"a=b": "1"})
    return


def test_flat_dict_round_trips() -> None:
    """
        flat_dict yields a plain {key: value} dict from the string list.
    """
    flat = MetalTagTranslator.flat_dict(strings=["a=1", "b=2"])
    assert flat == {"a": "1", "b": "2"}
    return


def test_base_resource_tags_carries_owner_and_run_id() -> None:
    """
        base_resource_tags stamps owner and run-id tags onto a resource.
    """
    tags = base_resource_tags(run_id="run-7", resource_name="dev-a",
                              resource_kind="instance")
    encoded = MetalTagTranslator.to_metal(neutral_tags=tags)
    flat = MetalTagTranslator.flat_dict(strings=encoded)
    assert flat.get(OWNER_TAG_KEY) == "codecraftai-provisioning"
    assert flat.get(RUN_ID_TAG_KEY) == "run-7"
    return
