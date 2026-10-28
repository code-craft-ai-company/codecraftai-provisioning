"""
    .. module:: test_venuedrivers
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Tests for the interop driver check the hypervisor venues make
        before importing their drivers.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


from ccai import testbase

from ccai.errors.exceptions import ConfigurationError

from ccai.provisioning.venuedrivers import (
    HYPERVISORS_EXTRA_REQUIREMENT, require_venue_driver
)


def test_installed_driver_passes():
    """
        An installed driver passes the check.  The merge gate installs every
        extra, so the Hyper-V driver is present.
    """
    require_venue_driver(venue="hyperv", driver_module="ccai.interop.hyperv",
                         driver_distribution="codecraftai-interop-hyperv")
    return


def test_missing_driver_names_the_extra():
    """
        A missing driver raises ConfigurationError naming the distribution
        and the 'hypervisors' extra that installs it.
    """
    with testbase.raises(ConfigurationError) as caught:
        require_venue_driver(venue="examplevenue", driver_module="ccai.interop.notadriver",
                             driver_distribution="codecraftai-interop-notadriver")

    message = str(caught.exception)
    assert "'examplevenue' venue" in message
    assert "codecraftai-interop-notadriver" in message
    assert HYPERVISORS_EXTRA_REQUIREMENT in message
    assert "ccai.interop.notadriver" in message
    return


def test_missing_parent_package_names_the_extra():
    """
        A driver whose parent package is missing as well raises the same
        ConfigurationError instead of a ModuleNotFoundError.
    """
    with testbase.raises(ConfigurationError) as caught:
        require_venue_driver(venue="examplevenue", driver_module="ccai.notapackage.driver",
                             driver_distribution="codecraftai-notapackage")

    message = str(caught.exception)
    assert HYPERVISORS_EXTRA_REQUIREMENT in message
    return
