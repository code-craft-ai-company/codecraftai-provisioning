"""
    Originates the hetzner venue test factories into this scope.
"""

from ccai import testbase
from ccai.testbase.factories import create_temporary_directory

from .factories import (
    create_credential,
    create_location_config,
    create_venue,
    create_aspects,
    create_confirm_aspects,
    create_client,
    create_dns_client,
    create_vpn_control_plane,
)

# Test lifespan: a fresh instance per test, matching what the pytest
# fixtures these replace did by default.  A wider lifespan shares mutated
# state between tests — a volume grown by one test stays grown for the next.
testbase.originate.parameter(create_credential, identifier="credential")
testbase.originate.parameter(create_location_config, identifier="location_config")
testbase.originate.parameter(create_venue, identifier="venue")
testbase.originate.parameter(create_aspects, identifier="aspects")
testbase.originate.parameter(create_confirm_aspects, identifier="confirm_aspects")
testbase.originate.parameter(create_client, identifier="client")
testbase.originate.parameter(create_dns_client, identifier="dns_client")
testbase.originate.parameter(create_vpn_control_plane, identifier="vpn_control_plane")

# Stands in for pytest tmp_path.
testbase.originate.parameter(create_temporary_directory,
                             identifier="tmp_path")
