"""
    .. module:: metalerrors
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Exception types raised by the Equinix Metal venue provisioner.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


class MetalValidationError(ValueError):
    """
        Raised when the Equinix Metal provisioner refuses a spec at
        validate-time.
    """


class MetalConflictError(RuntimeError):
    """
        Raised when the Equinix Metal provisioner finds drifted state that
        cannot be safely reconciled (e.g. an owner-tag collision).
    """


class MetalCapacityError(RuntimeError):
    """
        Raised when Equinix Metal reports that a plan is not available in the
        requested metro, or device provisioning fails to reach an active
        state inside the aspects-controlled timeout.
    """


class ConfirmationRequiredError(RuntimeError):
    """
        Raised when a destroy / DELETE-bearing apply is invoked without
        ``aspects.confirm=True``.
    """


class MetalApiRequestError(RuntimeError):
    """
        Raised when the Equinix Metal API answers a request with a
        non-success status.

        This is the transport's error, carrying the HTTP status, the reason
        the API gave and the raw body.  It stays distinct from
        :class:`MetalConflictError` and :class:`MetalCapacityError` because
        those describe provisioning decisions the venue made, not a failed
        call.

        :ivar status: The HTTP status code.
        :ivar reason: The reason extracted from the API's error body, or the
            HTTP reason phrase.
        :ivar body: The raw response body text.
    """

    def __init__(self, message: str, *, status: int = 0,
                 reason: str = "", body: str = "") -> None:
        """
            Construct a MetalApiRequestError.

            :param message: The human-readable error message.
            :param status: The HTTP status code.
            :param reason: The extracted reason.
            :param body: The raw response body.
        """
        super().__init__(message)
        self.status: int = status
        self.reason: str = reason
        self.body: str = body
        return
