"""
    Originates the digitalocean venue test factories into this scope.

    Replaces conftest.py: testbase does not read pytest conftest
    files, so those fixtures were invisible to its runner.
"""

from ccai import testbase
from ccai.testbase.factories import create_temporary_directory

from .factories import (
    create_digitalocean_credential,
    create_digitalocean_region_config,
    create_digitalocean_venue,
    create_digitalocean_raw_client,
    create_digitalocean_do_client,
    create_digitalocean_aspects,
    create_digitalocean_confirm_aspects,
)

testbase.originate.parameter(create_digitalocean_credential, identifier="credential")
testbase.originate.parameter(create_digitalocean_region_config, identifier="region_config")
testbase.originate.parameter(create_digitalocean_venue, identifier="venue")
testbase.originate.parameter(create_digitalocean_raw_client, identifier="raw_client")
testbase.originate.parameter(create_digitalocean_do_client, identifier="do_client")
testbase.originate.parameter(create_digitalocean_aspects, identifier="aspects")
testbase.originate.parameter(create_digitalocean_confirm_aspects, identifier="confirm_aspects")

# Stands in for pytest tmp_path.
testbase.originate.parameter(create_temporary_directory,
                             identifier="tmp_path")
