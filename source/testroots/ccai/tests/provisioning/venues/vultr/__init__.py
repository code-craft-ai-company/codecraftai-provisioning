"""
    Originates the vultr venue test factories into this scope.

    testbase does not read pytest conftest
    files, so those fixtures were invisible to its runner.
"""

from ccai import testbase

from ccai.tests.provisioning.venues.vultr.factories import (
    create_vultr_credential,
    create_vultr_venue,
    create_vultr_aspects,
    create_vultr_confirm_aspects,
    create_vultr_provisioner_factory,
)

testbase.originate.parameter(create_vultr_credential, identifier="credential")
testbase.originate.parameter(create_vultr_venue, identifier="venue")
testbase.originate.parameter(create_vultr_aspects, identifier="aspects")
testbase.originate.parameter(create_vultr_confirm_aspects, identifier="confirm_aspects")
testbase.originate.parameter(create_vultr_provisioner_factory, identifier="provisioner_factory")
