"""Unit tests for ``mindor.core.foundation.package`` pure helpers.

``install_package`` is a subprocess wrapper and is not unit-tested here.
"""

from unittest.mock import patch

from packaging.requirements import Requirement

from mindor.core.foundation.package import (
    is_requirement_satisfied,
    parse_requirement,
)


class TestParseRequirement:
    def test_simple_name(self):
        req = parse_requirement("torch")
        assert isinstance(req, Requirement)
        assert req.name == "torch"
        assert str(req.specifier) == ""

    def test_with_version_constraint(self):
        req = parse_requirement("torch>=2.0.0")
        assert req.name == "torch"
        assert str(req.specifier) == ">=2.0.0"

    def test_with_compound_constraint(self):
        req = parse_requirement("transformers>=4.0,<5.0")
        assert req.name == "transformers"
        # SpecifierSet renders in canonical order
        assert ">=4.0" in str(req.specifier)
        assert "<5.0" in str(req.specifier)

    def test_with_extras(self):
        req = parse_requirement("uvicorn[standard]")
        assert req.name == "uvicorn"
        assert "standard" in req.extras

    def test_vcs_url_returns_none(self):
        # `pip` accepts `git+https://...` but PEP 508 does not — parse should fail.
        assert parse_requirement("git+https://github.com/foo/bar") is None

    def test_invalid_string_returns_none(self):
        assert parse_requirement("!!!not a requirement!!!") is None

    def test_empty_string_returns_none(self):
        assert parse_requirement("") is None


class TestIsRequirementSatisfied:
    def test_installed_package_without_constraint_satisfies(self):
        # `pytest` itself is installed in the test environment.
        req = Requirement("pytest")
        assert is_requirement_satisfied(req) is True

    def test_missing_package_returns_false(self):
        req = Requirement("definitely-not-a-real-package-xyz")
        assert is_requirement_satisfied(req) is False

    def test_satisfied_version_constraint(self):
        with patch("mindor.core.foundation.package.version", return_value="2.5.0"):
            assert is_requirement_satisfied(Requirement("foo>=2.0.0")) is True

    def test_unsatisfied_version_constraint(self):
        with patch("mindor.core.foundation.package.version", return_value="1.0.0"):
            assert is_requirement_satisfied(Requirement("foo>=2.0.0")) is False

    def test_exact_match(self):
        with patch("mindor.core.foundation.package.version", return_value="2.5.0"):
            assert is_requirement_satisfied(Requirement("foo==2.5.0")) is True
            assert is_requirement_satisfied(Requirement("foo==2.5.1")) is False

    def test_canonicalises_name(self):
        # ``Foo_Bar`` should resolve via the canonical form ``foo-bar``.
        with patch("mindor.core.foundation.package.version") as v:
            v.return_value = "1.0.0"
            assert is_requirement_satisfied(Requirement("Foo_Bar")) is True
            # canonicalize_name normalises hyphens/underscores/dots.
            v.assert_called_once()
            assert v.call_args[0][0] == "foo-bar"

    def test_prerelease_versions_accepted_when_constraint_allows(self):
        with patch("mindor.core.foundation.package.version", return_value="2.0.0a1"):
            # Per the implementation, prereleases are always considered.
            assert is_requirement_satisfied(Requirement("foo>=2.0.0a0")) is True
