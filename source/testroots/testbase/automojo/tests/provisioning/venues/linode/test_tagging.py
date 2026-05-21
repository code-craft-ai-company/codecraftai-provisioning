"""
    .. module:: test_tagging
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Tag round-trip identity tests for the Linode venue.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


from hypothesis import given, settings
from hypothesis import strategies as st

from automojo.provisioning.venues.linode.linoderesolver import LinodeResolver
from automojo.provisioning.venues.linode.linodetagtranslator import (
    LinodeTagTranslator
)


# Tag keys and values that fit the Linode 50-char encoded limit.
_key_strategy = st.text(
    alphabet=st.characters(whitelist_categories=("Ll", "Lu", "Nd"),
                           whitelist_characters=(".", "-", ":", "_")),
    min_size=1, max_size=12,
)
_value_strategy = st.text(
    alphabet=st.characters(whitelist_categories=("Ll", "Lu", "Nd"),
                           whitelist_characters=(".", "-", "_")),
    min_size=0, max_size=12,
)


@settings(max_examples=120, deadline=None)
@given(pairs=st.dictionaries(keys=_key_strategy, values=_value_strategy,
                             min_size=0, max_size=8))
def test_tag_round_trip_identity(pairs) -> None:
    """
        ``from_linode(to_linode(x))`` recovers the original tag set.
    """
    translator = LinodeTagTranslator()

    encoded = translator.to_linode(neutral_tags=pairs)
    decoded = translator.from_linode(strings=encoded)

    assert decoded == pairs
    return


def test_owner_tags_carry_ownership(aspects) -> None:
    """
        ``owner_tags`` emits a tag list flagged as owned by the run.
    """
    translator = LinodeTagTranslator()
    tags = translator.owner_tags(run_id="testrun01", resource_name="vpc-a",
                                 resource_kind="network")
    assert translator.is_owned_by_run(strings=tags, run_id="testrun01")
    assert translator.is_owned_by_run(strings=tags, run_id="other") is False
    assert translator.resource_name_of(strings=tags) == "vpc-a"
    return


def test_resolver_gpu_mapping() -> None:
    """
        Accelerator models resolve to the Linode GPU type slugs.
    """
    resolver = LinodeResolver()
    slug = resolver.size_to_type(size_hint="medium",
                                 accelerators=["RTX6000"])
    assert slug == "g1-gpu-rtx6000-1"
    image = resolver.image_to_id(family="ubuntu", version="24.04",
                                 architecture="x86_64")
    assert image == "linode/ubuntu2404"
    return
