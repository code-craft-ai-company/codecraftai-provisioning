"""
    .. module:: gcpoperations
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Thin helpers over the real google-cloud SDK call surface —
               long-running-operation waits, not-found normalisation and
               proto label extraction.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


from typing import Any, Callable, Dict, Optional

from ccai.restclient.google.googleapierror import NotFound


def wait_for_operation(*, operation: Any) -> Any:
    """
        Block until a google-cloud long-running operation completes.

        Both the Compute ``ExtendedOperation`` and the TPU ``Operation``
        expose ``result()``, which blocks until the mutation is finished and
        raises a ``GoogleAPICallError`` subclass when the operation failed.
        Mutating GCP calls return immediately with such an operation, so the
        caller must wait here before reading the resource back; otherwise the
        follow-up ``get`` races the create and 404s.

        :param operation: A Compute ``ExtendedOperation`` or TPU ``Operation``.

        :returns: The operation's result value (may be ``None``).
    """
    rtnval = operation.result()
    return rtnval


def resource_or_none(*, fetch: Callable[..., Any], **kwargs: Any) -> Optional[Any]:
    """
        Call a google-cloud ``get``-style method, mapping absence to ``None``.

        The clients raise :class:`ccai.restclient.google.googleapierror.NotFound`
        for a missing resource rather than returning ``None``.  Catching that
        one exception is a deliberate recover-and-continue: the manager's
        read-before-create idempotency needs "does not exist" as a value, not
        an error.  Every other API error is allowed to bubble.

        :param fetch: The bound client ``get`` method to invoke.
        :param kwargs: Keyword arguments forwarded to ``fetch``.

        :returns: The fetched resource object, or ``None`` when not found.
    """
    try:
        fetched = fetch(**kwargs)
    except NotFound:
        rtnval: Optional[Any] = None
        return rtnval

    rtnval = fetched
    return rtnval


def labels_of(*, resource: Any) -> Dict[str, str]:
    """
        Extract a plain ``{key: value}`` dict from a resource's proto labels.

        Proto-plus label maps behave like dicts but are not one; downstream
        ownership helpers expect a real dict.  Resources without a ``labels``
        field yield an empty dict.

        :param resource: A google-cloud resource (proto or storage object).

        :returns: A plain dict of the resource's labels.
    """
    raw = getattr(resource, "labels", None)
    if raw is None:
        rtnval: Dict[str, str] = {}
        return rtnval

    out: Dict[str, str] = {}
    for key in raw:
        out[key] = raw[key]

    rtnval = out
    return rtnval
