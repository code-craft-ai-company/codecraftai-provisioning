"""
    .. module:: test_vpnjoinspec
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Tests for VPNJoinSpec and hostname template rendering.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


import re
import unittest

from ccai.testbase.properties import given
from ccai.testbase.properties import strategies as st

from ccai.interfaces.schemavalidationerror import SchemaValidationError
from ccai.interfaces.schemasemanticerror import SchemaSemanticError
from ccai.credentials.tailscaleoauthcredential import TailscaleOAuthCredential
from ccai.credentials.tailscaleauthkeycredential import (
    TailscaleAuthKeyCredential
)
from ccai.credentials.twingateserviceaccountcredential import (
    TwingateServiceAccountCredential
)

from ccai.interfaces.vpnjoinspec import VPNJoinSpec
from ccai.provisioning.model.vpn.hostnametemplate import (
    render_hostname, render_hostnames
)
from ccai.provisioning.model.vpn.vpncredentialresolver import (
    resolve_control_plane_credential
)


_DNS_LABEL_RE = re.compile(r"^(?!-)[a-z0-9-]{1,63}(?<!-)$")


class VPNJoinSpecTests(unittest.TestCase):

    def test_roundtrip_tailscale(self) -> None:
        spec = VPNJoinSpec(provider="tailscale",
                           control_plane_credential="ts-oauth",
                           hostname_template="host-{index}",
                           advertise_tags=["tag:agent"])
        rebuilt = VPNJoinSpec.from_dict(spec.to_dict())
        self.assertEqual(spec, rebuilt)
        return

    def test_rejects_unknown_provider(self) -> None:
        with self.assertRaises(SchemaValidationError):
            VPNJoinSpec(provider="zerotier",
                        control_plane_credential="x",
                        hostname_template="h-{index}")
        return

    def test_twingate_requires_connector_only(self) -> None:
        with self.assertRaises(SchemaValidationError):
            VPNJoinSpec(provider="twingate",
                        control_plane_credential="tw",
                        hostname_template="h-{index}")
        return

    def test_twingate_rejects_exit_node(self) -> None:
        with self.assertRaises(SchemaValidationError):
            VPNJoinSpec(provider="twingate",
                        control_plane_credential="tw",
                        hostname_template="h-{index}",
                        connector_only=True, exit_node=True)
        return

    def test_rejects_malformed_advertise_route(self) -> None:
        with self.assertRaises(SchemaValidationError):
            VPNJoinSpec(provider="tailscale",
                        control_plane_credential="ts",
                        hostname_template="h-{index}",
                        advertise_routes=["not-a-cidr"])
        return


class HostnameRendererTests(unittest.TestCase):

    def test_simple_render(self) -> None:
        rendered = render_hostname(template="host-{index}",
                                   context={"index": 3})
        self.assertEqual(rendered, "host-3")
        return

    def test_normalises_underscore_to_dash(self) -> None:
        rendered = render_hostname(template="{name}",
                                   context={"name": "HOST_1"})
        self.assertEqual(rendered, "host-1")
        return

    def test_unknown_variable_raises(self) -> None:
        with self.assertRaises(SchemaSemanticError):
            render_hostname(template="host-{missing}", context={"other": 1})
        return

    def test_duplicate_render_raises(self) -> None:
        with self.assertRaises(SchemaSemanticError):
            render_hostnames(template="static",
                            contexts=[{}, {}])
        return

    def test_determinism(self) -> None:
        a = render_hostname(template="host-{index}", context={"index": 7})
        b = render_hostname(template="host-{index}", context={"index": 7})
        self.assertEqual(a, b)
        return


def _tailscale_oauth() -> TailscaleOAuthCredential:
    rtnval = TailscaleOAuthCredential(identifier="ts-oauth",
                                      categories=["tailscale-oauth"],
                                      client_id="cid", client_secret="secret")
    return rtnval


def _tailscale_authkey() -> TailscaleAuthKeyCredential:
    rtnval = TailscaleAuthKeyCredential(identifier="ts-key",
                                        categories=["tailscale-authkey"],
                                        authkey="tskey-abc")
    return rtnval


def _twingate_service_account() -> TwingateServiceAccountCredential:
    rtnval = TwingateServiceAccountCredential(identifier="tg-svc",
                                              categories=["twingate-service-account"],
                                              api_token="token",
                                              network_slug="net-slug")
    return rtnval


class CredentialResolverTests(unittest.TestCase):

    def test_resolves_tailscale_oauth_credential(self) -> None:
        spec = VPNJoinSpec(provider="tailscale",
                           control_plane_credential="ts-oauth",
                           hostname_template="node-{index}")
        vault = {"ts-oauth": _tailscale_oauth()}
        resolved = resolve_control_plane_credential(
            spec=spec, credential_lookup=lambda ref: vault.get(ref, None)
        )
        self.assertIsInstance(resolved, TailscaleOAuthCredential)
        return

    def test_resolves_tailscale_authkey_credential(self) -> None:
        spec = VPNJoinSpec(provider="tailscale",
                           control_plane_credential="ts-key",
                           hostname_template="node-{index}")
        vault = {"ts-key": _tailscale_authkey()}
        resolved = resolve_control_plane_credential(
            spec=spec, credential_lookup=lambda ref: vault.get(ref, None)
        )
        self.assertIsInstance(resolved, TailscaleAuthKeyCredential)
        return

    def test_resolves_twingate_service_account_credential(self) -> None:
        spec = VPNJoinSpec(provider="twingate",
                           control_plane_credential="tg-svc",
                           hostname_template="conn-{index}",
                           connector_only=True)
        vault = {"tg-svc": _twingate_service_account()}
        resolved = resolve_control_plane_credential(
            spec=spec, credential_lookup=lambda ref: vault.get(ref, None)
        )
        self.assertIsInstance(resolved, TwingateServiceAccountCredential)
        return

    def test_credential_manager_missing_key_propagates_configuration_error(self) -> None:
        # CredentialManager raises ConfigurationError for an unknown key.  It
        # derives from BaseException by design (a wrong configuration must
        # terminate the run); the resolver must let it propagate unchanged.
        from ccai.credentials.credentialmanager import CredentialManager
        from ccai.errors.exceptions import ConfigurationError
        manager = CredentialManager()
        spec = VPNJoinSpec(provider="tailscale",
                           control_plane_credential="ts:missing",
                           hostname_template="{name}")
        with self.assertRaises(ConfigurationError) as caught:
            resolve_control_plane_credential(
                spec=spec, credential_lookup=manager.lookup_credential)
        self.assertIn("ts:missing", str(caught.exception))
        return

    def test_missing_credential_raises_semantic_error(self) -> None:
        spec = VPNJoinSpec(provider="tailscale",
                           control_plane_credential="absent",
                           hostname_template="node-{index}")
        with self.assertRaises(SchemaSemanticError):
            resolve_control_plane_credential(
                spec=spec, credential_lookup=lambda ref: None
            )
        return

    def test_mismatched_credential_class_raises_semantic_error(self) -> None:
        # Tailscale provider but a Twingate credential is resolved.
        spec = VPNJoinSpec(provider="tailscale",
                           control_plane_credential="tg-svc",
                           hostname_template="node-{index}")
        vault = {"tg-svc": _twingate_service_account()}
        with self.assertRaises(SchemaSemanticError):
            resolve_control_plane_credential(
                spec=spec, credential_lookup=lambda ref: vault.get(ref, None)
            )
        return

    def test_twingate_provider_rejects_tailscale_credential(self) -> None:
        spec = VPNJoinSpec(provider="twingate",
                           control_plane_credential="ts-oauth",
                           hostname_template="conn-{index}",
                           connector_only=True)
        vault = {"ts-oauth": _tailscale_oauth()}
        with self.assertRaises(SchemaSemanticError):
            resolve_control_plane_credential(
                spec=spec, credential_lookup=lambda ref: vault.get(ref, None)
            )
        return


# Module-level on purpose: the testbase sequencer collects module-level
# ``test_*`` and drives ``@given`` from the metadata the decorator records.
# A @given-decorated TestCase *method* never receives its generated
# arguments, so it cannot run at all.


@given(n_contexts=st.integers(min_value=2, max_value=20),
       constraints={"max_examples": 50})
def test_property_uniqueness(n_contexts) -> None:
    """
        Distinct contexts render to distinct hostnames, so no two instances
        in one plan can collide on a name.
    """
    contexts = [{"index": i} for i in range(n_contexts)]

    rendered = render_hostnames(template="host-{index}", contexts=contexts)

    assert len(set(rendered)) == n_contexts
    return


@given(index=st.integers(min_value=0, max_value=999),
       constraints={"max_examples": 50})
def test_property_dns_label_compliance(index) -> None:
    """
        A rendered hostname is a legal DNS label, so it can be registered
        as-is.
    """
    rendered = render_hostname(template="host-{index}", context={"index": index})

    assert _DNS_LABEL_RE.match(rendered) is not None
    return


@given(base=st.text(alphabet="abcdefghijklmnopqrstuvwxyz0123456789",
                    min_size=1, max_size=10),
       index=st.integers(min_value=0, max_value=99),
       constraints={"max_examples": 50})
def test_property_determinism(base, index) -> None:
    """
        Rendering is deterministic, so a re-plan does not rename hosts.
    """
    template = base + "-{index}"

    first = render_hostname(template=template, context={"index": index})
    second = render_hostname(template=template, context={"index": index})

    assert first == second
    return


if __name__ == "__main__":
    unittest.main()
