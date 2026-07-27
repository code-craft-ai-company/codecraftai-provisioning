"""
    Originates the azure venue test factories into this scope.

    Replaces conftest.py: testbase does not read pytest conftest
    files, so those fixtures were invisible to its runner.
"""

from ccai import testbase

from .factories import (
    create_azure_credential,
    create_azure_region_config,
    create_azure_venue,
    create_azure_world,
    create_azure_session_factory,
    create_azure_aspects,
    create_azure_confirm_aspects,
)

testbase.originate.parameter(create_azure_credential, identifier="credential")
testbase.originate.parameter(create_azure_region_config, identifier="region_config")
testbase.originate.parameter(create_azure_venue, identifier="venue")
testbase.originate.parameter(create_azure_world, identifier="world")
testbase.originate.parameter(create_azure_session_factory, identifier="session_factory")
testbase.originate.parameter(create_azure_aspects, identifier="aspects")
testbase.originate.parameter(create_azure_confirm_aspects, identifier="confirm_aspects")
