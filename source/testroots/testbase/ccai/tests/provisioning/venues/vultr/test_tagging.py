"""
    .. module:: test_tagging
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Tag round-trip identity tests for the Vultr tag translator.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


from hypothesis import given, settings
from hypothesis import strategies as st

from ccai.provisioning.venues.vultr.vultrtagtranslator import (
    VultrTagTranslator
)


_KEY_CHARS = st.text(
    alphabet=st.characters(whitelist_categories=("Ll", "Lu", "Nd"),
                           whitelist_characters=("-", ":", ".", "_")),
    min_size=1, max_size=12,
)
_VALUE_CHARS = st.text(
    alphabet=st.characters(whitelist_categories=("Ll", "Lu", "Nd"),
                           whitelist_characters=("-", ":", ".", "_", " ")),
    min_size=0, max_size=16,
)


@given(pairs=st.dictionaries(keys=_KEY_CHARS, values=_VALUE_CHARS,
                             min_size=0, max_size=8))
@settings(max_examples=80, deadline=None)
def test_tag_round_trip_identity(pairs) -> None:
    """
        from_vultr(to_vultr(tags)) is the identity over the key/value set.
    """
    vultr_tags = VultrTagTranslator.to_vultr(neutral_tags=pairs)
    recovered = VultrTagTranslator.from_vultr(strings=vultr_tags)
    assert recovered == pairs
    return


def test_tag_pair_encoded_as_single_string() -> None:
    """
        Each key=value pair encodes to exactly one string tag.
    """
    neutral = {"env": "prod", "team": "automation"}
    vultr_tags = VultrTagTranslator.to_vultr(neutral_tags=neutral)
    assert vultr_tags == ["env=prod", "team=automation"]
    return


def test_none_round_trips_to_empty() -> None:
    """
        None tag inputs translate to empty containers both ways.
    """
    assert VultrTagTranslator.to_vultr(neutral_tags=None) == []
    assert VultrTagTranslator.from_vultr(strings=None) == {}
    return
