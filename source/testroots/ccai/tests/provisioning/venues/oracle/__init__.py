"""
    Originates the oracle venue test factories into this scope.

    Replaces conftest.py: testbase does not read pytest conftest
    files, so those fixtures were invisible to its runner.
"""

from ccai import testbase

from .factories import (
    create_oracle_credential,
    create_oracle_region_config,
    create_oracle_venue,
    create_oracle_aspects,
    create_oracle_confirm_aspects,
)

testbase.originate.parameter(create_oracle_credential, identifier="credential")
testbase.originate.parameter(create_oracle_region_config, identifier="region_config")
testbase.originate.parameter(create_oracle_venue, identifier="venue")
testbase.originate.parameter(create_oracle_aspects, identifier="aspects")
testbase.originate.parameter(create_oracle_confirm_aspects, identifier="confirm_aspects")
