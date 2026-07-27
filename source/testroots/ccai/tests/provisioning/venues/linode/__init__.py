"""
    Originates the linode venue test factories into this scope.

    testbase does not read pytest conftest
    files, so those fixtures were invisible to its runner.
"""

from ccai import testbase
from ccai.testbase.factories import create_temporary_directory

from .factories import (
    create_linode_credential,
    create_linode_region_config,
    create_linode_venue,
    create_linode_aspects,
    create_linode_confirm_aspects,
)

testbase.originate.parameter(create_linode_credential, identifier="credential")
testbase.originate.parameter(create_linode_region_config, identifier="region_config")
testbase.originate.parameter(create_linode_venue, identifier="venue")
testbase.originate.parameter(create_linode_aspects, identifier="aspects")
testbase.originate.parameter(create_linode_confirm_aspects, identifier="confirm_aspects")

# A fresh temporary directory per test.
testbase.originate.parameter(create_temporary_directory,
                             identifier="tmp_path")
