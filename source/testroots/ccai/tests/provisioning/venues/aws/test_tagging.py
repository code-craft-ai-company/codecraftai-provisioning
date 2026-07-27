"""
    .. module:: test_tagging
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Tests for awstagging round-trip identity.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


import pytest

from ccai.testbase.properties import given
from ccai.testbase.properties import strategies as st

from ccai.provisioning.venues.aws.awserrors import AwsValidationError
from ccai.provisioning.venues.aws.awstagging import (
    AWS_TAG_VALUE_MAX, from_aws, to_aws, base_resource_tags
)


def test_to_aws_basic() -> None:
    """
        Convert a small tag dict and inspect the shape.
    """
    out = to_aws(neutral_tags={"a": "1", "b": "2"})
    assert out == [{"Key": "a", "Value": "1"}, {"Key": "b", "Value": "2"}]
    return


def test_from_aws_basic() -> None:
    """
        Reverse direction.
    """
    out = from_aws(aws_tags=[{"Key": "a", "Value": "1"},
                             {"Key": "b", "Value": "2"}])
    assert out == {"a": "1", "b": "2"}
    return


def test_base_resource_tags_contains_owner_run_name_kind() -> None:
    """
        ``base_resource_tags`` includes the required keys.
    """
    flat = base_resource_tags(
        run_id="r1", resource_name="vpc-a", resource_kind="network",
        extra={"team": "ml"}, defaults={"component": "test"},
    )
    assert flat["ccai:owned-by"] == "codecraftai-provisioning"
    assert flat["ccai:owner"] == "r1"
    assert flat["ccai:resource-name"] == "vpc-a"
    assert flat["ccai:resource-kind"] == "network"
    assert flat["team"] == "ml"
    assert flat["component"] == "test"
    return


def test_to_aws_rejects_oversize_value() -> None:
    """
        Tag values longer than 256 chars are rejected at translate time.
    """
    big_value = "x" * (AWS_TAG_VALUE_MAX + 1)
    with pytest.raises(AwsValidationError):
        to_aws(neutral_tags={"k": big_value})
    return


@given(st.dictionaries(
    keys=st.text(min_size=1, max_size=20,
                 alphabet=st.characters(min_codepoint=0x41,
                                        max_codepoint=0x7a)),
    values=st.text(min_size=0, max_size=20,
                   alphabet=st.characters(min_codepoint=0x41,
                                          max_codepoint=0x7a)),
    min_size=0, max_size=8,
), constraints={"max_examples": 25})
def test_round_trip_identity(tag_map) -> None:
    """
        from_aws(to_aws(x)) == x.
    """
    aws_form = to_aws(neutral_tags=tag_map)
    rebuilt = from_aws(aws_tags=aws_form)
    assert rebuilt == tag_map
    return
