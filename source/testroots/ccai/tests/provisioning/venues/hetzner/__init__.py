"""
    Originates the hetzner venue test factories into this scope.
"""

from ccai import testbase
from ccai.testbase.factories import create_temporary_directory

from ccai.tests.provisioning.venues.hetzner.factories import (
    create_credential,
    create_location_config,
    create_venue,
    create_aspects,
    create_confirm_aspects,
)

# Only the immutable resources are originated here.  Sharing a
# credential or a region config across the package is free.
#
# The stateful test doubles are attached per test instead, with
# @testbase.attach.parameter.  originate.parameter refuses Test
# lifespan by design, so anything originated here is ONE instance for
# the whole package and one test's writes are visible to the next.
testbase.originate.parameter(create_credential, identifier="credential")
testbase.originate.parameter(create_location_config, identifier="location_config")
testbase.originate.parameter(create_venue, identifier="venue")
testbase.originate.parameter(create_aspects, identifier="aspects")
testbase.originate.parameter(create_confirm_aspects, identifier="confirm_aspects")

# A fresh temporary directory per test.
testbase.originate.parameter(create_temporary_directory,
                             identifier="tmp_path")
