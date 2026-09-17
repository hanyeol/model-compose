from typing import Optional, List, Dict, Set
from dataclasses import dataclass, field
from .requirement import PackageRequirement, RuntimeEnvironment, RuntimeIssue, RuntimeIssueCode, RequirementAnalyzer, RequirementVersionResolver

# Turns `runtime: auto` into concrete runtime types by lifting the components
# whose declared requirements collide with the majority into virtualenv.
#
# Given the components sharing the host Python environment and the
# version-conflict issues detected among them, recommends which components to
# isolate so the remaining host group becomes satisfiable. Solves it greedily
# as a minimum hitting set: at each step, pick the component whose removal
# from the host group breaks the largest number of remaining owner-pair
# conflicts, ties broken lexicographically for deterministic output. Greedy
# hitting set gives at most a `ln(m)`-factor over the optimum; results should
# not be treated as minimum.

@dataclass
class RuntimeAssignment:
    """The final `runtime.type` per component after resolving `auto`.

    `reasons` records why each isolated component was moved off the host
    group, one string per contributing conflict, for user-facing logging.
    """
    types:   Dict[str, str]       = field(default_factory=dict)  # component_id -> runtime type
    reasons: Dict[str, List[str]] = field(default_factory=dict)

    def is_isolated(self, component_id: str) -> bool:
        return component_id in self.reasons

    def explain(self, component_id: str) -> Optional[str]:
        reasons = self.reasons.get(component_id)

        if not reasons:
            return None

        return f"isolated to virtualenv: {'; '.join(reasons)}"

class RuntimeResolver:
    def __init__(
        self,
        host_requirements: Dict[str, List[PackageRequirement]],
        issues:            List[RuntimeIssue],
    ):
        self.host_requirements: Dict[str, List[PackageRequirement]] = host_requirements
        self.issues: List[RuntimeIssue] = issues

        # For pair-satisfiability checks during greedy scoring. Rebuilds of
        # the whole host group instantiate a fresh analyzer with the reduced
        # environment instead.
        self._version_resolver: RequirementVersionResolver = RequirementVersionResolver()

    def find_isolated_components(self) -> Dict[str, List[RuntimeIssue]]:
        """Pick components to lift out of the host runtime, greedily.

        Returns `{component_id: [issue, ...]}` in the order components were
        picked, mapping each isolated component to the original host issues it
        was involved in. Non-host issues are ignored.
        """
        host_environment = self._host_environment(self.issues)

        if host_environment is None:
            return {}

        conflicts: List[RuntimeIssue] = []

        for issue in self.issues:
            if issue.code == RuntimeIssueCode.VERSION_CONFLICT and issue.environment == host_environment:
                conflicts.append(issue)

        if not conflicts:
            return {}

        active_requirements: Dict[str, List[PackageRequirement]] = {
            owner: list(requirements) for owner, requirements in self.host_requirements.items()
        }
        isolated_owners: Set[str] = set()
        isolation_issues: Dict[str, List[RuntimeIssue]] = {}

        while conflicts:
            owner = self._pick_isolation_candidate(conflicts, isolated_owners)

            if owner is None:
                break  # unreachable: a version-conflict always has >=2 pinned owners

            isolated_owners.add(owner)
            isolation_issues[owner] = self._collect_isolation_issues(owner)

            conflicts = self._rebuild_conflict_issues(active_requirements, isolated_owners, host_environment)

        return isolation_issues

    def _pick_isolation_candidate(
        self,
        conflicts: List[RuntimeIssue],
        isolated_owners: Set[str]
    ) -> Optional[str]:
        """Owner appearing in the most incompatible owner-pairs; lex tie-break.

        Scoring the issue as a whole undercounts: three owners agreeing on
        torch==2.10 against one holdout on 2.5 would score everyone equally.
        What actually needs breaking is each pair of owners whose specifiers
        cannot be satisfied together — the odd-one-out then dominates the
        score.

        Some conflicts are pairwise-compatible but jointly empty (e.g.
        A: `>=1,<=3,!=2.*`, B: `>=2,<=3`, C: `>=1,<3`). Pair scoring gives
        every owner 0, so as a fallback each owner in a jointly-unsatisfiable
        conflict receives one point, ensuring the loop makes progress.
        """
        scores: Dict[str, int] = {}

        for conflict in conflicts:
            remaining_requirements = [
                requirement for requirement in conflict.requirements if requirement.owner not in isolated_owners
            ]

            pair_scored = False

            for index, left in enumerate(remaining_requirements):
                for right in remaining_requirements[index + 1:]:
                    if left.owner == right.owner:
                        continue

                    if self._version_resolver.resolve_shared_version([ left.specifier, right.specifier ]) is not None:
                        continue

                    scores[left.owner]  = scores.get(left.owner, 0)  + 1
                    scores[right.owner] = scores.get(right.owner, 0) + 1
                    pair_scored = True

            if pair_scored:
                continue

            # Fallback: pair-satisfiable but jointly-empty. Give each remaining
            # owner one point so the greedy loop can still make a pick.
            remaining_specifiers = [requirement.specifier for requirement in remaining_requirements]

            if self._version_resolver.resolve_shared_version(remaining_specifiers) is None:
                for requirement in remaining_requirements:
                    scores[requirement.owner] = scores.get(requirement.owner, 0) + 1

        if not scores:
            return None

        top = max(scores.values())
        winners = sorted(owner for owner, score in scores.items() if score == top)

        return winners[0]

    def _collect_isolation_issues(self, component_id: str) -> List[RuntimeIssue]:
        """The original host issues this component was declared in."""
        issues: List[RuntimeIssue] = []

        for issue in self.issues:
            if issue.code != RuntimeIssueCode.VERSION_CONFLICT:
                continue

            if any(requirement.owner == component_id for requirement in issue.requirements):
                issues.append(issue)

        return issues

    def _rebuild_conflict_issues(
        self,
        active_requirements: Dict[str, List[PackageRequirement]],
        isolated_owners:     Set[str],
        host_environment:    RuntimeEnvironment,
    ) -> List[RuntimeIssue]:
        """Recompute version-conflict on the host group with isolated owners removed.

        Reuses the analyzer so that indeterminate ranges (satisfiable but
        without a witness) are not promoted to conflicts on the second pass.
        """
        remaining_requirements: List[PackageRequirement] = []

        for owner, requirements in active_requirements.items():
            if owner in isolated_owners:
                continue

            remaining_requirements.extend(requirements)

        rebuilt_issues = RequirementAnalyzer({ host_environment: remaining_requirements }).detect_issues()
        issues: List[RuntimeIssue] = []

        for issue in rebuilt_issues:
            if issue.code == RuntimeIssueCode.VERSION_CONFLICT:
                issues.append(issue)

        return issues

    @staticmethod
    def _host_environment(issues: List[RuntimeIssue]) -> Optional[RuntimeEnvironment]:
        for issue in issues:
            if issue.environment.kind == "host":
                return issue.environment

        return None
