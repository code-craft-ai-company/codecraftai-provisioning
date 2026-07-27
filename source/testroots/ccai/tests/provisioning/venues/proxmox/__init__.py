"""
    Originates the proxmox venue test factories into this scope.

    testbase does not read pytest conftest
    files, so those fixtures were invisible to its runner.
"""

from ccai import testbase
from ccai.testbase.factories import create_temporary_directory

from .factories import (
    create_proxmox_venue,
    create_proxmox_aspects,
    create_proxmox_confirm_aspects,
)

testbase.originate.parameter(create_proxmox_venue, identifier="venue")
testbase.originate.parameter(create_proxmox_aspects, identifier="aspects")
testbase.originate.parameter(create_proxmox_confirm_aspects, identifier="confirm_aspects")

# A fresh temporary directory per test.
testbase.originate.parameter(create_temporary_directory,
                             identifier="tmp_path")
