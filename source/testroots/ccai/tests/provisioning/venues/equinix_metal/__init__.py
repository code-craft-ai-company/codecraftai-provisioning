"""
    Originates the equinix_metal venue test factories into this scope.

    Replaces conftest.py: testbase does not read pytest conftest
    files, so those fixtures were invisible to its runner.
"""

from ccai import testbase

from .factories import (
    create_equinix_metal_credential,
    create_equinix_metal_project_config,
    create_equinix_metal_venue,
    create_equinix_metal_aspects,
    create_equinix_metal_confirm_aspects,
    create_equinix_metal_mock_client,
)

testbase.originate.parameter(create_equinix_metal_credential, identifier="credential")
testbase.originate.parameter(create_equinix_metal_project_config, identifier="project_config")
testbase.originate.parameter(create_equinix_metal_venue, identifier="venue")
testbase.originate.parameter(create_equinix_metal_aspects, identifier="aspects")
testbase.originate.parameter(create_equinix_metal_confirm_aspects, identifier="confirm_aspects")
testbase.originate.parameter(create_equinix_metal_mock_client, identifier="mock_client")
