"""
    .. module:: test_tagging
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Round-trip identity tests for the DigitalOcean tag translator.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


from hypothesis import given, strategies as st

from automojo.provisioning.venues.digitalocean.dotagtranslator import (
    from_do, to_do
)


def test_tag_round_trip_simple() -> None:
    """
        A simple key/value tag round-trips to identity.
    """
    neutral = [{"team": "ci"}, {"env": "test"}]
    encoded = to_do(neutral_tags=neutral)
    decoded = from_do(do_tags=encoded)
    assert sorted(d for entry in decoded for d in entry.items()) == sorted(
        d for entry in neutral for d in entry.items()
    )
    return


def test_tag_round_trip_with_equals_in_value() -> None:
    """
        A value containing ``=`` round-trips to identity (escaping works).
    """
    neutral = [{"expr": "a=b=c"}, {"plain": "value"}]
    encoded = to_do(neutral_tags=neutral)
    decoded = from_do(do_tags=encoded)
    flat = {}
    for entry in decoded:
        for key, value in entry.items():
            flat[key] = value
    assert flat["expr"] == "a=b=c"
    assert flat["plain"] == "value"
    return


def test_tag_round_trip_with_backslash() -> None:
    """
        A value containing a backslash round-trips to identity.
    """
    neutral = [{"path": "C:\\users\\test=x"}]
    encoded = to_do(neutral_tags=neutral)
    decoded = from_do(do_tags=encoded)
    assert decoded == [{"path": "C:\\users\\test=x"}]
    return


_KEY_ALPHABET = st.text(
    alphabet=st.characters(min_codepoint=33, max_codepoint=126),
    min_size=1, max_size=24,
)
_VALUE_ALPHABET = st.text(
    alphabet=st.characters(min_codepoint=32, max_codepoint=126),
    min_size=0, max_size=64,
)


@given(
    pairs=st.dictionaries(keys=_KEY_ALPHABET, values=_VALUE_ALPHABET,
                          min_size=0, max_size=8)
)
def test_tag_round_trip_identity(pairs) -> None:
    """
        For any key/value dict, ``from_do(to_do(...))`` is the identity.
    """
    neutral = [{key: value} for key, value in pairs.items()]
    encoded = to_do(neutral_tags=neutral)
    decoded = from_do(do_tags=encoded)

    decoded_flat = {}
    for entry in decoded:
        for key, value in entry.items():
            decoded_flat[key] = value

    assert decoded_flat == pairs
    return
