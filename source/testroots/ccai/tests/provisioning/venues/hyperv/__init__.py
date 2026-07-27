"""
    Originates the hyperv venue test factories into this scope.

    Replaces conftest.py: testbase does not read pytest conftest
    files, so those fixtures were invisible to its runner.
"""

from ccai import testbase
from ccai.testbase.factories import create_temporary_directory

from .factories import (
    create_hyperv_venue,
    create_hyperv_host_config,
    create_hyperv_client,
    create_hyperv_vpn_control_plane,
    create_hyperv_aspects,
    create_hyperv_confirm_aspects,
)

testbase.originate.parameter(create_hyperv_venue, identifier="venue")
testbase.originate.parameter(create_hyperv_host_config, identifier="host_config")
testbase.originate.parameter(create_hyperv_client, identifier="client")
testbase.originate.parameter(create_hyperv_vpn_control_plane, identifier="vpn_control_plane")
testbase.originate.parameter(create_hyperv_aspects, identifier="aspects")
testbase.originate.parameter(create_hyperv_confirm_aspects, identifier="confirm_aspects")

# Stands in for pytest tmp_path.
testbase.originate.parameter(create_temporary_directory,
                             identifier="tmp_path")
