"""
    Originates the gcp venue test factories into this scope.

    testbase does not read pytest conftest
    files, so those fixtures were invisible to its runner.
"""

from ccai import testbase

from ccai.tests.provisioning.venues.gcp.factories import (
    create_gcp_credential,
    create_gcp_region_config,
    create_gcp_venue,
    create_gcp_aspects,
    create_gcp_confirm_aspects,
)

testbase.originate.parameter(create_gcp_credential, identifier="credential")
testbase.originate.parameter(create_gcp_region_config, identifier="region_config")
testbase.originate.parameter(create_gcp_venue, identifier="venue")
testbase.originate.parameter(create_gcp_aspects, identifier="aspects")
testbase.originate.parameter(create_gcp_confirm_aspects, identifier="confirm_aspects")
