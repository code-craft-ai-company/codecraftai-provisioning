"""
    Originates the xcpng venue test factories into this scope.

    Replaces conftest.py: testbase does not read pytest conftest
    files, so those fixtures were invisible to its runner.
"""

from ccai import testbase

from .factories import (
    create_xcpng_venue,
    create_xcpng_aspects,
    create_xcpng_confirm_aspects,
)

testbase.originate.parameter(create_xcpng_venue, identifier="venue")
testbase.originate.parameter(create_xcpng_aspects, identifier="aspects")
testbase.originate.parameter(create_xcpng_confirm_aspects, identifier="confirm_aspects")
