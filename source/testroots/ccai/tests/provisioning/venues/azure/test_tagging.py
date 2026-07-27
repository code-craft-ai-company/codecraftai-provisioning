"""
    .. module:: test_tagging
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Tests for azuretagging round-trip identity.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


from ccai import testbase


from ccai.testbase.properties import given
from ccai.testbase.properties import strategies as st

from ccai.provisioning.venues.azure.azureerrors import (
    AzureValidationError
)
from ccai.provisioning.venues.azure.azuretagging import (
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
    with testbase.raises(AzureValidationError):
        to_azure(neutral_tags={"k": 123})
    return


def test_to_azure_rejects_oversize_value() -> None:
    """
        Tag values longer than 256 chars are rejected at translate time.
    """
    big_value = "x" * (AZURE_TAG_VALUE_MAX + 1)
    with testbase.raises(AzureValidationError):
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
    assert flat["ccai:owned-by"] == "codecraftai-provisioning"
    assert flat["ccai:owner"] == "r1"
    assert flat["ccai:resource-name"] == "vnet-a"
    assert flat["ccai:resource-kind"] == "network"
    assert flat["team"] == "ml"
    assert flat["component"] == "test"
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
def test_tag_round_trip_identity(tag_map) -> None:
    """
        from_azure(to_azure(x)) == x for any tag dict.
    """
    azure_form = to_azure(neutral_tags=tag_map)
    rebuilt = from_azure(azure_tags=azure_form)
    assert rebuilt == tag_map
    return
