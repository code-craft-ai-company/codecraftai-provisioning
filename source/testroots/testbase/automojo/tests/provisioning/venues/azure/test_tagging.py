"""
    .. module:: test_tagging
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Tests for azuretagging round-trip identity.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


import pytest

from hypothesis import given, settings
from hypothesis import strategies as st

from automojo.provisioning.venues.azure.azureerrors import (
    AzureValidationError
)
from automojo.provisioning.venues.azure.azuretagging import (
    AZURE_TAG_VALUE_MAX, base_resource_tags, from_azure, to_azure
)


def test_to_azure_basic() -> None:
    """
        Convert a small neutral tag dict into the Azure tags dict.
    """
    out = to_azure(neutral_tags={"a": "1", "b": "2"})
    assert out == {"a": "1", "b": "2"}
    return


def test_from_azure_basic() -> None:
    """
        Reverse direction: Azure tags dict back to a flat neutral tag dict.
    """
    out = from_azure(azure_tags={"b": "2", "a": "1"})
    assert out == {"a": "1", "b": "2"}
    return


def test_to_azure_rejects_non_string_value() -> None:
    """
        A non-string tag value is rejected.
    """
    with pytest.raises(AzureValidationError):
        to_azure(neutral_tags={"k": 123})
    return


def test_to_azure_rejects_oversize_value() -> None:
    """
        Tag values longer than 256 chars are rejected at translate time.
    """
    big_value = "x" * (AZURE_TAG_VALUE_MAX + 1)
    with pytest.raises(AzureValidationError):
        to_azure(neutral_tags={"k": big_value})
    return


def test_base_resource_tags_contains_owner_run_name_kind() -> None:
    """
        ``base_resource_tags`` includes the required keys.
    """
    flat = base_resource_tags(
        run_id="r1", resource_name="vnet-a", resource_kind="network",
        extra={"team": "ml"}, defaults={"component": "test"},
    )
    assert flat["automojo:owned-by"] == "automojo-provisioning"
    assert flat["automojo:owner"] == "r1"
    assert flat["automojo:resource-name"] == "vnet-a"
    assert flat["automojo:resource-kind"] == "network"
    assert flat["team"] == "ml"
    assert flat["component"] == "test"
    return


@settings(max_examples=40, deadline=None)
@given(st.dictionaries(
    keys=st.text(min_size=1, max_size=20,
                 alphabet=st.characters(min_codepoint=0x41,
                                        max_codepoint=0x7a)),
    values=st.text(min_size=0, max_size=20,
                   alphabet=st.characters(min_codepoint=0x41,
                                          max_codepoint=0x7a)),
    min_size=0, max_size=8,
))
def test_tag_round_trip_identity(tag_map) -> None:
    """
        from_azure(to_azure(x)) == x for any tag dict.
    """
    azure_form = to_azure(neutral_tags=tag_map)
    rebuilt = from_azure(azure_tags=azure_form)
    assert rebuilt == tag_map
    return
