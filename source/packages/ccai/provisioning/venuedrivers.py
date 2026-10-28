"""
    .. module:: venuedrivers
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: The check the hypervisor venues make before importing their
        interop drivers, which ship in the 'hypervisors' extra.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


import importlib.util
import os

from ccai.errors.exceptions import ConfigurationError


HYPERVISORS_EXTRA_REQUIREMENT = "codecraftai-provisioning[hypervisors]"


def require_venue_driver(*, venue: str, driver_module: str, driver_distribution: str) -> None:
    """
        Check that the interop driver package a venue imports is installed.

        The coreweave, hyperv, libvirt and xcpng venues import their interop
        drivers from the 'hypervisors' extra, which a plain install of
        ``codecraftai-provisioning`` does not include.  Each of those venue
        modules calls this before importing its driver, so an install without
        the extra fails with a :class:`ConfigurationError` that names the
        extra instead of a bare ``ModuleNotFoundError``.

        :param venue: The venue name to show in the error message.
        :param driver_module: The top-level module of the interop driver, for
            example ``ccai.interop.hyperv``.
        :param driver_distribution: The distribution that ships the driver,
            for example ``codecraftai-interop-hyperv``.

        :raises: ConfigurationError
    """
    driver_spec = None
    try:
        driver_spec = importlib.util.find_spec(driver_module)
    except ModuleNotFoundError:
        # A parent package of the driver module is not installed either,
        # which means the driver is not installed.
        driver_spec = None

    if driver_spec is None:
        err_msg_lines = [
            "The '{}' venue needs the '{}' package, which is not installed.".format(venue, driver_distribution)
        ]
        err_msg_lines.append("The hypervisor venue drivers ship in the 'hypervisors' extra.")
        err_msg_lines.append("INSTALL: pip install \"{}\"".format(HYPERVISORS_EXTRA_REQUIREMENT))
        err_msg_lines.append("MISSING MODULE: {}".format(driver_module))

        err_msg = os.linesep.join(err_msg_lines)
        raise ConfigurationError(err_msg)

    return
