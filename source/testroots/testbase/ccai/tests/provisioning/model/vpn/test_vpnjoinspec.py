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

from hypothesis import assume, given, settings, strategies as st

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


class HostnameRendererPropertyTests(unittest.TestCase):

    @settings(max_examples=50, deadline=None)
    @given(st.integers(min_value=2, max_value=20))
    def test_property_uniqueness(self, n_contexts) -> None:
        contexts = [{"index": i} for i in range(n_contexts)]
        rendered = render_hostnames(template="host-{index}",
                                    contexts=contexts)
        self.assertEqual(len(set(rendered)), n_contexts)
        return

    @settings(max_examples=50, deadline=None)
    @given(st.integers(min_value=0, max_value=999))
    def test_property_dns_label_compliance(self, index) -> None:
        rendered = render_hostname(template="host-{index}",
                                   context={"index": index})
        self.assertIsNotNone(_DNS_LABEL_RE.match(rendered))
        return

    @settings(max_examples=50, deadline=None)
    @given(st.text(alphabet="abcdefghijklmnopqrstuvwxyz0123456789",
                   min_size=1, max_size=10),
           st.integers(min_value=0, max_value=99))
    def test_property_determinism(self, base, index) -> None:
        template = base + "-{index}"
        a = render_hostname(template=template, context={"index": index})
        b = render_hostname(template=template, context={"index": index})
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


if __name__ == "__main__":
    unittest.main()
