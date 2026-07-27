"""
    Originates the crusoe venue test factories into this scope.

    testbase does not read pytest conftest
    files, so those fixtures were invisible to its runner.
"""

from ccai import testbase
from ccai.testbase.factories import create_temporary_directory

from ccai.tests.provisioning.venues.crusoe.factories import (
    create_crusoe_crusoe_aspects,
    create_crusoe_crusoe_confirm_aspects,
    create_crusoe_crusoe_venue,
    create_crusoe_project_config,
)

testbase.originate.parameter(create_crusoe_crusoe_aspects, identifier="crusoe_aspects")
testbase.originate.parameter(create_crusoe_crusoe_confirm_aspects, identifier="crusoe_confirm_aspects")
testbase.originate.parameter(create_crusoe_crusoe_venue, identifier="crusoe_venue")
testbase.originate.parameter(create_crusoe_project_config, identifier="project_config")

# A fresh temporary directory per test.
testbase.originate.parameter(create_temporary_directory,
                             identifier="tmp_path")
