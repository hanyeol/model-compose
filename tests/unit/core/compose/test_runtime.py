"""Unit tests for ``mindor.core.compose.runtime.RuntimeResolver``.

Exercises the greedy isolation picker and the interaction with the analyzer's
conflict findings.
"""

from typing import Dict, List, Tuple

import pytest

from mindor.core.compose.requirement import (
    PackageRequirement,
    RequirementAnalyzer,
    RuntimeEnvironment,
)
from mindor.core.compose.runtime import RuntimeResolver


HOST = RuntimeEnvironment("host", "controller")


def _requirements(*owner_and_spec: Tuple[str, str]) -> List[PackageRequirement]:
    return [PackageRequirement(spec, owner) for owner, spec in owner_and_spec]


def _host(*owner_and_spec: Tuple[str, str]) -> Dict[str, List[PackageRequirement]]:
    grouped: Dict[str, List[PackageRequirement]] = {}
    for owner, spec in owner_and_spec:
        grouped.setdefault(owner, []).append(PackageRequirement(spec, owner))
    return grouped


def _run(*owner_and_spec: Tuple[str, str]) -> Dict[str, list]:
    envs = {HOST: _requirements(*owner_and_spec)}
    issues = RequirementAnalyzer(envs).detect_issues()
    host_requirements = _host(*owner_and_spec)
    return RuntimeResolver(host_requirements, issues).find_isolated_components()


# --- happy paths -------------------------------------------------------------


def test_two_way_conflict_isolates_one_owner():
    picks = _run(("a", "torch==2.5.1"), ("b", "torch==2.10.0"))
    assert list(picks.keys()) == ["a"]  # lex tie-break


def test_odd_one_out_across_three_agreeing_pins():
    picks = _run(
        ("a", "torch==2.10.0"),
        ("b", "torch==2.10.0"),
        ("c", "torch==2.10.0"),
        ("d", "torch==2.5.1"),
    )
    assert list(picks.keys()) == ["d"]


def test_three_way_conflict_isolates_two():
    picks = _run(
        ("ace_step", "torch==2.10.0"),
        ("float",    "torch==2.5.1"),
        ("yue2",     "torch==2.9.0"),
    )
    assert len(picks) == 2


def test_cross_package_owner_isolated_once():
    picks = _run(
        ("bad",     "torch==2.5.1"),
        ("bad",     "transformers==4.30"),
        ("normal1", "torch==2.10.0"),
        ("normal1", "transformers==4.50"),
        ("normal2", "torch==2.10.0"),
        ("normal2", "transformers==4.50"),
    )
    assert list(picks.keys()) == ["bad"]
    assert len(picks["bad"]) == 2  # torch and transformers issues


def test_no_conflicts_returns_empty_picks():
    picks = _run(("a", "torch==2.10.0"), ("b", "torch==2.10.0"))
    assert picks == {}


# --- P1 #2: multi-way pairwise-compatible conflict ---------------------------


def test_multi_way_disjoint_exact_pins_all_isolated_but_one():
    """Four owners whose exact pins are all disjoint. The analyzer flags a
    version-conflict on the whole set (provably empty), and the resolver's
    fallback scoring must isolate enough owners to leave a satisfiable rest.
    """
    picks = _run(
        ("a", "pkg==1"),
        ("b", "pkg==2"),
        ("c", "pkg==3"),
        ("d", "pkg==4"),
    )
    # Three of four must be isolated to leave a single owner (which is trivially
    # satisfiable). Which three depend on lex tie-breaks; only the count matters.
    assert len(picks) == 3


def test_rebuild_does_not_promote_indeterminate_to_conflict():
    """After isolating an owner from a real conflict, the resolver re-checks
    the remaining owners. Two owners that are indeterminate (satisfiable but
    without a witness) must not be reported as a residual conflict — and their
    owners must not be isolated.

    Setup:
      foo: a==1, b==2 (provably conflicting; one of them must be isolated)
      bar: c>1, d<1.0.0.1 (satisfiable by 1.0.0.0.1; witness search returns
           None, so a naive rebuild would flag this as a conflict too)

    Only one owner (from foo) should be isolated. bar owners must stay put.
    """
    picks = _run(
        ("a", "foo==1"),
        ("b", "foo==2"),
        ("c", "bar>1"),
        ("d", "bar<1.0.0.1"),
    )
    assert set(picks.keys()).issubset({"a", "b"})
    assert len(picks) == 1
