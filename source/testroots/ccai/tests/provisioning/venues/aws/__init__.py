"""
    Originates the aws venue test factories into this scope.

    testbase does not read pytest conftest
    files, so those fixtures were invisible to its runner.
"""

from ccai import testbase

from .factories import (
    create_aws__aws_env,
    create_aws_credential,
    create_aws_region_config,
    create_aws_venue,
    create_aws_aspects,
    create_aws_confirm_aspects,
)

testbase.originate.parameter(create_aws__aws_env, identifier="_aws_env")
testbase.originate.parameter(create_aws_credential, identifier="credential")
testbase.originate.parameter(create_aws_region_config, identifier="region_config")
testbase.originate.parameter(create_aws_venue, identifier="venue")
testbase.originate.parameter(create_aws_aspects, identifier="aspects")
testbase.originate.parameter(create_aws_confirm_aspects, identifier="confirm_aspects")
