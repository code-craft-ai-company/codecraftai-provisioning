"""
    Originates the nutanix venue test factories into this scope.

    Replaces conftest.py: testbase does not read pytest conftest
    files, so those fixtures were invisible to its runner.
"""

from ccai import testbase
from ccai.testbase.factories import create_temporary_directory

from .factories import (
    create_nutanix_venue,
    create_nutanix_aspects,
    create_nutanix_confirm_aspects,
)

testbase.originate.parameter(create_nutanix_venue, identifier="venue")
testbase.originate.parameter(create_nutanix_aspects, identifier="aspects")
testbase.originate.parameter(create_nutanix_confirm_aspects, identifier="confirm_aspects")

# Stands in for pytest tmp_path.
testbase.originate.parameter(create_temporary_directory,
                             identifier="tmp_path")
