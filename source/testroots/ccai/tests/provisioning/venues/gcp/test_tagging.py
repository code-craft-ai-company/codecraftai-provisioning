"""
    .. module:: test_tagging
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Tests for gcptagging neutral-tags ↔ GCP-labels round-trip.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


import pytest

from ccai.testbase.properties import given
from ccai.testbase.properties import strategies as st

from ccai.provisioning.venues.google.gcperrors import GcpValidationError
from ccai.provisioning.venues.google.gcptagging import (
    base_resource_labels, from_labels, is_label_conformant,
    sanitise_label_component, to_labels
)


def test_to_labels_basic() -> None:
    """
        Convert a small tag dict and inspect the shape.
    """
    out = to_labels(neutral_tags={"a": "1", "b": "2"})
    assert out == {"a": "1", "b": "2"}
    return


def test_from_labels_basic() -> None:
    """
        Reverse direction yields a key-sorted flat tag dict.
    """
    out = from_labels(labels={"b": "2", "a": "1"})
    assert out == {"a": "1", "b": "2"}
    return


def test_to_labels_sanitises_uppercase_and_warns() -> None:
    """
        Uppercase keys are lowercased and a warning is emitted.
    """
    warnings: list = []
    out = to_labels(neutral_tags={"Team": "ML-Group"}, warnings=warnings)
    assert out == {"team": "ml-group"}
    assert len(warnings) >= 1
    return


def test_to_labels_replaces_illegal_characters() -> None:
    """
        Illegal characters (':', '.') are replaced with underscores.
    """
    out = to_labels(neutral_tags={"ccai:component": "web.tier"})
    assert out == {"ccai_component": "web_tier"}
    return


def test_base_resource_labels_contains_owner_keys() -> None:
    """
        ``base_resource_labels`` includes the required ccai keys.
    """
    labels = base_resource_labels(
        run_id="r1", resource_name="vpc-a", resource_kind="network",
        extra={"team": "ml"}, defaults={"component": "test"},
    )
    assert labels["ccai_owned-by"] == "codecraftai-provisioning"
    assert labels["ccai_owner"] == "r1"
    assert labels["ccai_resource-name"] == "vpc-a"
    assert labels["ccai_resource-kind"] == "network"
    assert labels["team"] == "ml"
    assert labels["component"] == "test"
    return


def test_to_labels_rejects_non_string_value() -> None:
    """
        A non-string tag value is rejected.
    """
    with pytest.raises(GcpValidationError):
        to_labels(neutral_tags={"k": 123})
    return


@given(st.dictionaries(
    keys=st.text(min_size=1, max_size=20,
                 alphabet=st.characters(min_codepoint=0x61,
                                        max_codepoint=0x7a)),
    values=st.text(min_size=0, max_size=20,
                   alphabet=st.characters(min_codepoint=0x61,
                                          max_codepoint=0x7a)),
    min_size=0, max_size=8,
), constraints={"max_examples": 50})
def test_label_round_trip_identity_for_conformant_inputs(tag_map) -> None:
    """
        from_labels(to_labels(x)) == x for GCP-conformant inputs.

        Inputs drawn from lowercase letters are already conformant, so the
        round-trip is the identity.
    """
    for key, value in tag_map.items():
        assert is_label_conformant(key=key, value=value) is True
    labels = to_labels(neutral_tags=tag_map)
    rebuilt = from_labels(labels=labels)
    assert rebuilt == tag_map
    return


@given(st.text(min_size=1, max_size=30), constraints={"max_examples": 50})
def test_sanitise_label_component_always_conformant(raw) -> None:
    """
        Sanitised components always satisfy the GCP value rules.
    """
    sanitised = sanitise_label_component(value=raw)
    assert is_label_conformant(key="a", value=sanitised) is True
    return
