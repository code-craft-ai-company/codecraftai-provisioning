"""
    Originates the vsphere venue test factories into this scope.

    testbase does not read pytest conftest
    files, so those fixtures were invisible to its runner.
"""

from ccai import testbase

from .factories import (
    create_vsphere_credential,
    create_vsphere_venue,
    create_vsphere_config,
    create_vsphere_aspects,
    create_vsphere_confirm_aspects,
)

testbase.originate.parameter(create_vsphere_credential, identifier="credential")
testbase.originate.parameter(create_vsphere_venue, identifier="venue")
testbase.originate.parameter(create_vsphere_config, identifier="config")
testbase.originate.parameter(create_vsphere_aspects, identifier="aspects")
testbase.originate.parameter(create_vsphere_confirm_aspects, identifier="confirm_aspects")
