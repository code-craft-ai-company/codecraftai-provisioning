"""
    .. module:: redactforpersistence
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Recursive redactor for sensitive fields prior to persistence.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


from typing import Any, Iterable


REDACTED_PLACEHOLDER: str = "<redacted>"

# Field names whose values must never reach disk.
_SENSITIVE_KEY_FRAGMENTS: tuple = (
    "authkey", "auth_key", "secret", "password",
    "token", "private_key", "client_secret",
)


def _is_sensitive_key(*, key: str) -> bool:
    """
        Return True when ``key`` matches any sensitive fragment.

        :param key: A dict key name.

        :returns: True when the key is considered sensitive.
    """
    lowered = key.lower()
    for fragment in _SENSITIVE_KEY_FRAGMENTS:
        if fragment in lowered:
            rtnval = True
            return rtnval
    rtnval = False
    return rtnval


def redact_for_persistence(*, value: Any) -> Any:
    """
        Walk a JSON-shaped structure and replace sensitive values.

        Dicts: any key whose name contains a sensitive fragment has its
        value replaced with ``REDACTED_PLACEHOLDER``.

        Lists/tuples: each element is recursively redacted.

        :param value: A dict / list / scalar.

        :returns: A new structure with sensitive values redacted.
    """
    if isinstance(value, dict):
        rebuilt: dict = {}
        for k, v in value.items():
            if _is_sensitive_key(key=k):
                rebuilt[k] = REDACTED_PLACEHOLDER
            else:
                rebuilt[k] = redact_for_persistence(value=v)
        rtnval = rebuilt
        return rtnval
    if isinstance(value, list):
        rtnval = [redact_for_persistence(value=item) for item in value]
        return rtnval
    if isinstance(value, tuple):
        rtnval = tuple(
            redact_for_persistence(value=item) for item in value
        )
        return rtnval
    rtnval = value
    return rtnval
