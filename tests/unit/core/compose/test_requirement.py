"""Unit tests for ``mindor.core.compose.requirement``.

Covers PEP 440 witness-search edge cases and the three detection rules.
"""

from typing import List

import pytest
from packaging.specifiers import SpecifierSet

from mindor.core.compose.requirement import (
    PackageRequirement,
    RequirementAnalyzer,
    RequirementVersionResolver,
    RuntimeEnvironment,
    RuntimeIssueCode,
    RuntimeIssueSeverity,
)


@pytest.fixture
def resolver() -> RequirementVersionResolver:
    return RequirementVersionResolver()


def _specs(*strings: str) -> List[SpecifierSet]:
    return [SpecifierSet(s) for s in strings]


# --- resolve_shared_version --------------------------------------------------


def test_resolve_shared_version_returns_witness_for_compatible_pins(resolver):
    version = resolver.resolve_shared_version(_specs("==2.10.0", ">=2.0"))
    assert str(version) == "2.10.0"


def test_resolve_shared_version_returns_none_for_disjoint_pins(resolver):
    assert resolver.resolve_shared_version(_specs("==2.5.1", "==2.10.0")) is None


def test_resolve_shared_version_honors_wildcard_upper_bound(resolver):
    assert resolver.resolve_shared_version(_specs("==2.8.*", ">=2.9")) is None


def test_resolve_shared_version_honors_wildcard_lower_bound(resolver):
    assert resolver.resolve_shared_version(_specs("==2.8.*", "<2.8")) is None


def test_resolve_shared_version_honors_compatible_release(resolver):
    assert resolver.resolve_shared_version(_specs("~=2.10.0", ">=2.11")) is None
    assert resolver.resolve_shared_version(_specs("~=2.10.0", ">=2.10.5")) is not None


# --- P1 #1: witness-search completeness for open ranges ----------------------


def test_resolve_shared_version_finds_witness_inside_open_range(resolver):
    """`>1, <1.1` is satisfied by e.g. 1.0.1 — a version that lies strictly
    between two mentioned points and is neither a `.dev0`/`.post0` neighbor nor
    a wildcard boundary. The witness generator must not miss it.
    """
    assert resolver.resolve_shared_version(_specs(">1", "<1.1")) is not None


def test_resolve_shared_version_finds_witness_between_prereleases(resolver):
    """`>1.0rc1, <1.0rc3` is satisfied by 1.0rc2. Pre-release neighborhoods
    are dense and the generator has to cover them.
    """
    assert resolver.resolve_shared_version(_specs(">1.0rc1", "<1.0rc3")) is not None


def test_resolve_shared_version_handles_post_release_anchor(resolver):
    """Anchors that already have a post-release segment must not blow up
    when the candidate generator tries to attach another ``.post0``.
    """
    assert resolver.resolve_shared_version(_specs("==1.0.post1", ">=1")) is not None


def test_resolve_shared_version_handles_dev_release_anchor(resolver):
    """Anchors that already have a dev-release segment must not produce
    invalid versions like ``1.0.dev1.post0``.
    """
    assert resolver.resolve_shared_version(_specs("==1.0.dev1", "<2")) is not None


# --- P1 #2: three-state resolution -------------------------------------------


def test_indeterminate_range_is_not_flagged_as_conflict():
    """`>1, <1.0.0.1` is satisfied by `1.0.0.0.1`. Our witness generator
    does not emit that value, so ``resolve_shared_version`` returns None —
    but the detector must not treat this as a proven version-conflict.
    """
    envs = {HOST: _requirements(("a", "pkg>1"), ("b", "pkg<1.0.0.1"))}
    codes = {i.code for i in RequirementAnalyzer(envs).detect_issues()}
    assert RuntimeIssueCode.VERSION_CONFLICT not in codes


def test_disjoint_exact_pins_are_flagged_as_conflict():
    """Two different `==X` pins provably cannot be satisfied together.
    This is the one case the detector can confirm without a witness search.
    """
    envs = {HOST: _requirements(("a", "torch==2.5.1"), ("b", "torch==2.10.0"))}
    codes = {i.code for i in RequirementAnalyzer(envs).detect_issues()}
    assert RuntimeIssueCode.VERSION_CONFLICT in codes


def test_provably_conflicting_normalizes_exact_pin_strings(resolver):
    """``==1`` and ``==1.0`` refer to the same release; ``is_provably_conflicting``
    must not flag them as disjoint just because their strings differ.
    """
    assert resolver.is_provably_conflicting(_specs("==1", "==1.0")) is False


def test_provably_conflicting_matches_local_version_against_bare_pin(resolver):
    """PEP 440 lets a bare ``==2.5.1`` match local versions like
    ``2.5.1+cu121``; the disjoint-exact check must respect that.
    """
    assert resolver.is_provably_conflicting(_specs("==2.5.1", "==2.5.1+cu121")) is False


# --- detect_issues -----------------------------------------------------------


HOST = RuntimeEnvironment("host", "controller")


def _requirements(*owner_and_spec: tuple) -> List[PackageRequirement]:
    return [PackageRequirement(spec, owner) for owner, spec in owner_and_spec]


def test_detect_issues_flags_version_conflict():
    envs = {HOST: _requirements(("a", "torch==2.5.1"), ("b", "torch==2.10.0"))}
    issues = RequirementAnalyzer(envs).detect_issues()

    assert [i.code for i in issues] == [RuntimeIssueCode.VERSION_CONFLICT]
    assert issues[0].code.severity is RuntimeIssueSeverity.ERROR


def test_detect_issues_flags_loose_shadowed():
    envs = {HOST: _requirements(("a", "transformers"), ("b", "transformers==4.50"))}
    issues = RequirementAnalyzer(envs).detect_issues()

    assert [i.code for i in issues] == [RuntimeIssueCode.LOOSE_SHADOWED]
    assert issues[0].code.severity is RuntimeIssueSeverity.WARNING


def test_detect_issues_flags_order_dependent():
    envs = {HOST: _requirements(("a", "transformers>=4.40"), ("b", "transformers==4.50"))}
    issues = RequirementAnalyzer(envs).detect_issues()

    assert [i.code for i in issues] == [RuntimeIssueCode.ORDER_DEPENDENT]


def test_detect_issues_returns_empty_for_compatible_identical_pins():
    envs = {HOST: _requirements(("a", "torch==2.10.0"), ("b", "torch==2.10.0"))}
    assert RequirementAnalyzer(envs).detect_issues() == []


def test_detect_issues_reports_both_conflict_and_shadow_when_present():
    envs = {HOST: _requirements(("a", "torch==2.5.1"), ("b", "torch==2.10.0"), ("c", "torch"))}
    codes = {i.code for i in RequirementAnalyzer(envs).detect_issues()}
    assert RuntimeIssueCode.VERSION_CONFLICT in codes
    assert RuntimeIssueCode.LOOSE_SHADOWED in codes


# --- P2 #3: venv paths that resolve to the same directory share an environment


def test_virtualenv_path_normalization_treats_relative_forms_as_one_env():
    env_a = RuntimeEnvironment.from_component("c", "virtualenv", ".venv", None)
    env_b = RuntimeEnvironment.from_component("c", "virtualenv", "./.venv", None)
    assert env_a == env_b


# --- P2 #4: container components never share an environment


def test_container_components_get_per_component_environments_even_when_sharing_image():
    env_a = RuntimeEnvironment.from_component("a", "docker", None, "pytorch:2.10")
    env_b = RuntimeEnvironment.from_component("b", "docker", None, "pytorch:2.10")
    assert env_a != env_b


def test_apple_container_components_get_per_component_environments():
    env_a = RuntimeEnvironment.from_component("a", "apple-container", None, "shared:1")
    env_b = RuntimeEnvironment.from_component("b", "apple-container", None, "shared:1")
    assert env_a != env_b
