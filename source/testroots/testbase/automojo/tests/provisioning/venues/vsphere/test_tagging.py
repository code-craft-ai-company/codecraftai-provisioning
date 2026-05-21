"""
    .. module:: test_tagging
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Category+tag round-trip tests for the VSphere venue.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


import pytest

from hypothesis import given, strategies as st

from automojo.provisioning.venues.vsphere.vserrors import VsValidationError
from automojo.provisioning.venues.vsphere.vstagtranslator import (
    base_resource_tags, belongs_to_run, from_vs, to_vs
)


def test_to_vs_builds_category_tag_pairs() -> None:
    """
        Each neutral key becomes a category; each value becomes a tag.
    """
    refs = to_vs(neutral_tags={"env": "prod", "team": "infra"})
    categories = {ref.category for ref in refs}
    assert categories == {"env", "team"}
    by_cat = {ref.category: ref.tag for ref in refs}
    assert by_cat["env"] == "prod"
    return


def test_to_vs_rejects_non_string_value() -> None:
    """
        A non-string tag value is rejected.
    """
    with pytest.raises(VsValidationError):
        to_vs(neutral_tags={"a": 1})
    return


def test_belongs_to_run_detects_owner_and_run() -> None:
    """
        belongs_to_run is true only for owner+run-id matches.
    """
    tags = base_resource_tags(run_id="r1", resource_name="n1",
                              resource_kind="instance")
    assert belongs_to_run(neutral_tags=tags, run_id="r1") is True
    assert belongs_to_run(neutral_tags=tags, run_id="r2") is False
    return


_TAG_KEYS = st.text(
    alphabet=st.characters(min_codepoint=97, max_codepoint=122),
    min_size=1, max_size=12,
)
_TAG_VALUES = st.text(
    alphabet=st.characters(min_codepoint=33, max_codepoint=126),
    min_size=0, max_size=24,
)


@given(mapping=st.dictionaries(_TAG_KEYS, _TAG_VALUES, max_size=8))
def test_category_tag_round_trip_identity(mapping) -> None:
    """
        Property: from_vs(to_vs(neutral)) is the identity for any input.
    """
    refs = to_vs(neutral_tags=mapping)
    restored = from_vs(refs=refs)
    assert restored == mapping
    return
