"""
    .. module:: test_tagging
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Tests for gcptagging neutral-tags ↔ GCP-labels round-trip.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


import pytest

from hypothesis import given, settings
from hypothesis import strategies as st

from automojo.provisioning.venues.google.gcperrors import GcpValidationError
from automojo.provisioning.venues.google.gcptagging import (
    base_resource_labels, from_labels, is_label_conformant,
    sanitise_label_component, to_labels
)


def test_to_labels_basic() -> None:
    """
        Convert a small tag list and inspect the shape.
    """
    out = to_labels(neutral_tags=[{"a": "1"}, {"b": "2"}])
    assert out == {"a": "1", "b": "2"}
    return


def test_from_labels_basic() -> None:
    """
        Reverse direction yields key-sorted single-entry dicts.
    """
    out = from_labels(labels={"b": "2", "a": "1"})
    assert out == [{"a": "1"}, {"b": "2"}]
    return


def test_to_labels_sanitises_uppercase_and_warns() -> None:
    """
        Uppercase keys are lowercased and a warning is emitted.
    """
    warnings: list = []
    out = to_labels(neutral_tags=[{"Team": "ML-Group"}], warnings=warnings)
    assert out == {"team": "ml-group"}
    assert len(warnings) >= 1
    return


def test_to_labels_replaces_illegal_characters() -> None:
    """
        Illegal characters (':', '.') are replaced with underscores.
    """
    out = to_labels(neutral_tags=[{"automojo:component": "web.tier"}])
    assert out == {"automojo_component": "web_tier"}
    return


def test_base_resource_labels_contains_owner_keys() -> None:
    """
        ``base_resource_labels`` includes the required automojo keys.
    """
    labels = base_resource_labels(
        run_id="r1", resource_name="vpc-a", resource_kind="network",
        extra=[{"team": "ml"}], defaults=[{"component": "test"}],
    )
    assert labels["automojo_owned-by"] == "automojo-provisioning"
    assert labels["automojo_owner"] == "r1"
    assert labels["automojo_resource-name"] == "vpc-a"
    assert labels["automojo_resource-kind"] == "network"
    assert labels["team"] == "ml"
    assert labels["component"] == "test"
    return


def test_to_labels_rejects_non_dict_entry() -> None:
    """
        A non-dict tag entry is rejected.
    """
    with pytest.raises(GcpValidationError):
        to_labels(neutral_tags=["not-a-dict"])
    return


@settings(max_examples=50, deadline=None)
@given(st.dictionaries(
    keys=st.text(min_size=1, max_size=20,
                 alphabet=st.characters(min_codepoint=0x61,
                                        max_codepoint=0x7a)),
    values=st.text(min_size=0, max_size=20,
                   alphabet=st.characters(min_codepoint=0x61,
                                          max_codepoint=0x7a)),
    min_size=0, max_size=8,
))
def test_label_round_trip_identity_for_conformant_inputs(tag_map) -> None:
    """
        from_labels(to_labels(x)) == sorted(x) for GCP-conformant inputs.

        Inputs drawn from lowercase letters are already conformant, so the
        round-trip is the identity.
    """
    neutral = [{k: v} for k, v in tag_map.items()]
    for key, value in tag_map.items():
        assert is_label_conformant(key=key, value=value) is True
    labels = to_labels(neutral_tags=neutral)
    rebuilt = from_labels(labels=labels)
    expected = sorted(neutral, key=lambda d: list(d.keys())[0])
    assert rebuilt == expected
    return


@settings(max_examples=50, deadline=None)
@given(st.text(min_size=1, max_size=30))
def test_sanitise_label_component_always_conformant(raw) -> None:
    """
        Sanitised components always satisfy the GCP value rules.
    """
    sanitised = sanitise_label_component(value=raw)
    assert is_label_conformant(key="a", value=sanitised) is True
    return
