"""
    .. module:: test_index_credential_integration
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: End-to-end proof that a private-index credential travels from
               a real CredentialManager, through the engine's validate and
               apply stages, into a venue's rendered user data — and lands
               only inside the root-only pip configuration.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


import unittest

from typing import Any, Dict, List, Optional

import yaml

from ccai.credentials.credentialmanager import CredentialManager
from ccai.interfaces.schemasemanticerror import SchemaSemanticError

from ccai.provisioning.aspects.provisioningaspects import ProvisioningAspects
from ccai.provisioning.cloudinit.bootstraprenderer import render_instance_user_data
from ccai.provisioning.cloudprovisionerregistry import CloudProvisionerRegistry
from ccai.provisioning.model.cloud.cloudinstance import CloudInstance
from ccai.provisioning.model.cloud.provisioningresult import ProvisioningResult
from ccai.provisioning.provisioningengine import ProvisioningEngine

from ccai.tests.provisioning.engine.test_engine_pipeline import (
    MockCloudProvisioner, _venue,
)


_BASIC_SECRET = "p@ss w0rd/1"
_TOKEN_SECRET = "pypi-AgEIcHlwaS5vcmc-token"


def _instance_payload(credential: str) -> Dict[str, Any]:
    rtnval = {
        "name": "web-01", "profile_ref": "profile",
        "image": {"family": "ubuntu", "version": "24.04", "architecture": "x86_64"},
        "size": "general.small", "subnet": "sub-east",
        "python_environments": [{
            "path": "/opt/venvs/app", "packages": ["rich"],
            "index_url": "https://pypi.internal/simple",
            "extra_index_urls": ["https://pypi.internal/extra/simple",
                                 "https://pypi.org/simple"],
            "index_credential": credential,
        }],
    }
    return rtnval


class _RenderingProvisioner(MockCloudProvisioner):
    """
        A venue that renders user data for its instance the way real venue
        apply stages do — from inside apply_subset, with no secrets passed
        explicitly — and keeps the document for inspection.
    """

    def __init__(self, *, instance_payload: Dict[str, Any], **kwargs) -> None:
        super().__init__(**kwargs)
        self._instance_payload = instance_payload
        self.rendered: Optional[str] = None
        return

    def apply_subset(self, *, kinds: List[str], aspects: Any) -> ProvisioningResult:
        if "instance" in kinds:
            instance = CloudInstance.from_dict(self._instance_payload)
            self.rendered = render_instance_user_data(instance=instance)
        rtnval = super().apply_subset(kinds=kinds, aspects=aspects)
        return rtnval


def _manager() -> CredentialManager:
    manager = CredentialManager()
    manager.load_credentials({"credentials": [
        {"identifier": "pypi:basic", "category": "basic",
         "username": "svc", "password": _BASIC_SECRET},
        {"identifier": "pypi:token", "category": "api-token",
         "token": _TOKEN_SECRET},
    ]})
    return manager


def _run(credential: str, manager: Optional[CredentialManager]):
    payload = _instance_payload(credential)
    registry = CloudProvisionerRegistry()
    provisioner = _RenderingProvisioner(
        instance_payload=payload, venue=_venue("mock-east"),
        venue_spec={"instances": [{"name": "web-01"}], "networks": [{"name": "vpc-east"}]})
    registry.register(name="mock-east", provisioner=provisioner)
    spec = {
        "networks": [{"name": "vpc-east"}],
        "subnets": [{"name": "sub-east", "network": "vpc-east"}],
        "instances": [payload],
    }
    lookup = manager.lookup_credential if manager is not None else None
    engine = ProvisioningEngine(spec=spec, registry=registry, credential_lookup=lookup)
    return engine, provisioner


class IndexCredentialIntegrationTests(unittest.TestCase):

    def test_basic_credential_reaches_only_the_pip_conf(self) -> None:
        engine, provisioner = _run("pypi:basic", _manager())
        engine.validate(aspects=ProvisioningAspects())
        engine.apply(aspects=ProvisioningAspects())

        document = provisioner.rendered
        self.assertIsNotNone(document)
        parsed = yaml.safe_load(document)
        conf = [w for w in parsed["write_files"] if w["path"].endswith(".pip.conf")][0]
        self.assertEqual(conf["permissions"], "0400")
        self.assertIn("index-url = https://svc:p%40ss%20w0rd%2F1@pypi.internal/simple", conf["content"])
        self.assertIn("    https://svc:p%40ss%20w0rd%2F1@pypi.internal/extra/simple", conf["content"])
        self.assertIn("    https://pypi.org/simple\n", conf["content"])
        # The (encoded) secret occurs exactly twice in the whole document:
        # once per same-host URL inside the pip.conf, and nowhere else.
        self.assertEqual(document.count("p%40ss%20w0rd%2F1"), 2)
        self.assertNotIn(_BASIC_SECRET, document)
        script = [w for w in parsed["write_files"] if w["path"].endswith(".sh")][0]
        self.assertNotIn("p%40ss", script["content"])
        self.assertNotIn("p%40ss", str(parsed["runcmd"]))
        return

    def test_token_credential_uses_token_username(self) -> None:
        engine, provisioner = _run("pypi:token", _manager())
        engine.apply(aspects=ProvisioningAspects())
        self.assertIn("https://__token__:{}@pypi.internal/simple".format(_TOKEN_SECRET),
                      provisioner.rendered)
        return

    def test_unknown_reference_fails_at_validate_with_manager_detail(self) -> None:
        engine, _ = _run("pypi:missing", _manager())
        with self.assertRaises(SchemaSemanticError) as caught:
            engine.validate(aspects=ProvisioningAspects())
        self.assertIn("pypi:missing", str(caught.exception))
        return

    def test_no_manager_fails_at_validate_before_any_render(self) -> None:
        engine, provisioner = _run("pypi:basic", None)
        with self.assertRaises(SchemaSemanticError):
            engine.validate(aspects=ProvisioningAspects())
        self.assertIsNone(provisioner.rendered)
        return


if __name__ == "__main__":
    unittest.main()
