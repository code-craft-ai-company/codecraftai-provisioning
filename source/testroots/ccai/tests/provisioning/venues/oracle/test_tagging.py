"""
    .. module:: test_tagging
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Tests for ocitagging neutral↔freeform round-trip identity.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


from ccai import testbase


from ccai.testbase.properties import given
from ccai.testbase.properties import strategies as st

from ccai.provisioning.venues.oracle.ocierrors import OciValidationError
from ccai.provisioning.venues.oracle.ocitagging import (
    OCI_TAG_VALUE_MAX, base_resource_tags, from_freeform, to_freeform
)


def test_to_freeform_basic() -> None:
    """
        Convert a small neutral tag dict to the OCI freeform-tags shape.
    """
    out = to_freeform(neutral_tags={"a": "1", "b": "2"})
    assert out == {"a": "1", "b": "2"}
    return


def test_from_freeform_basic() -> None:
    """
        Reverse direction — freeform dict to a key-sorted flat tag dict.
    """
    out = from_freeform(freeform_tags={"b": "2", "a": "1"})
    assert out == {"a": "1", "b": "2"}
    return


def test_base_resource_tags_contains_owner_run_name_kind() -> None:
    """
        ``base_resource_tags`` includes the required ownership keys.
    """
    flat = base_resource_tags(
        run_id="r1", resource_name="vcn-a", resource_kind="network",
        extra={"team": "ml"}, defaults={"component": "test"},
    )
    assert flat["ccai_owned-by"] == "codecraftai-provisioning"
    assert flat["ccai_run-id"] == "r1"
    assert flat["ccai_resource-name"] == "vcn-a"
    assert flat["ccai_resource-kind"] == "network"
    assert flat["team"] == "ml"
    assert flat["component"] == "test"
    return


def test_to_freeform_rejects_oversize_value() -> None:
    """
        Tag values longer than 256 chars are rejected at translate time.
    """
    big_value = "x" * (OCI_TAG_VALUE_MAX + 1)
    with testbase.raises(OciValidationError):
        to_freeform(neutral_tags={"k": big_value})
    return


def test_to_freeform_rejects_non_string_value() -> None:
    """
        A non-string tag value is rejected at translate time.
    """
    with testbase.raises(OciValidationError):
        to_freeform(neutral_tags={"k": 123})
    return


@given(st.dictionaries(
    keys=st.text(min_size=1, max_size=20,
                 alphabet=st.characters(min_codepoint=0x41,
                                        max_codepoint=0x7a)),
    values=st.text(min_size=0, max_size=20,
                   alphabet=st.characters(min_codepoint=0x41,
                                          max_codepoint=0x7a)),
    min_size=0, max_size=8,
), constraints={"max_examples": 40})
def test_freeform_tag_round_trip_identity(tag_map) -> None:
    """
        from_freeform(to_freeform(x)) == x — the round trip is the
        identity on the neutral tag set.
    """
    freeform = to_freeform(neutral_tags=tag_map)
    rebuilt = from_freeform(freeform_tags=freeform)
    assert rebuilt == tag_map
    return
