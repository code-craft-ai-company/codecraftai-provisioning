"""
    Originates the nebius venue test factories into this scope.

    Replaces conftest.py: testbase does not read pytest conftest
    files, so those fixtures were invisible to its runner.
"""

from ccai import testbase

from .factories import (
    create_nebius_client,
    create_nebius_venue,
    create_nebius_aspects,
    create_nebius_confirm_aspects,
)

testbase.originate.parameter(create_nebius_client, identifier="client")
testbase.originate.parameter(create_nebius_venue, identifier="venue")
testbase.originate.parameter(create_nebius_aspects, identifier="aspects")
testbase.originate.parameter(create_nebius_confirm_aspects, identifier="confirm_aspects")
