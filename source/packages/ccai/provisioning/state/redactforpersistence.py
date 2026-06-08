"""
    .. module:: redactforpersistence
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Recursive redactor for sensitive fields prior to persistence.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


from typing import Any


REDACTED_PLACEHOLDER: str = "<redacted>"

# Field names whose values must never reach disk.
_SENSITIVE_KEY_FRAGMENTS: tuple = (
    "authkey", "auth_key", "secret", "password",
    "token", "private_key", "client_secret",
)


# Path fragments that mark a cloud-init ``write_files`` entry as carrying a
# secret in its (innocuously-named) ``content`` field. The auth key or
# connector token is written to one of these files on the target host.
_SENSITIVE_PATH_FRAGMENTS: tuple = (
    "authkey", "auth_key", "tailscale/authkey",
    "twingate/connector", "connector.conf",
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


def _is_sensitive_path(*, path_value: Any) -> bool:
    """
        Return True when a ``write_files`` entry path names a secret file.

        :param path_value: The ``path`` value of a write_files-style dict.

        :returns: True when the path is a known secret-bearing file.
    """
    if not isinstance(path_value, str):
        rtnval = False
        return rtnval
    lowered = path_value.lower()
    for fragment in _SENSITIVE_PATH_FRAGMENTS:
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

        Value-context: a cloud-init ``write_files`` entry carries the secret
        under an innocuously-named ``content`` key.  When a dict declares a
        ``path`` naming a known secret-bearing file (an auth-key or Twingate
        connector file), its ``content`` value is redacted even though the
        key name ``content`` is not itself sensitive.

        Lists/tuples: each element is recursively redacted.

        :param value: A dict / list / scalar.

        :returns: A new structure with sensitive values redacted.
    """
    if isinstance(value, dict):
        content_is_sensitive = False
        if "content" in value and "path" in value:
            content_is_sensitive = _is_sensitive_path(
                path_value=value.get("path"))
        rebuilt: dict = {}
        for k, v in value.items():
            if _is_sensitive_key(key=k):
                rebuilt[k] = REDACTED_PLACEHOLDER
            elif k == "content" and content_is_sensitive is True:
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
