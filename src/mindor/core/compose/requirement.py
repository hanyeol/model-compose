from typing import Optional, List, Dict, Iterable, Sequence, Set, FrozenSet
from typing_extensions import Self
from enum import Enum
from dataclasses import dataclass, field
from pathlib import Path
from packaging.requirements import Requirement
from packaging.specifiers import SpecifierSet
from packaging.utils import canonicalize_name
from packaging.version import Version, InvalidVersion

# Static analysis of the package requirements declared across all components
# sharing a Python environment. Works on the raw specs returned by
# `_get_setup_requirements()`, not on their post-`torch_requirements()`
# rewrite: the rewrite adds wheel-index URLs or relaxes pins based on host
# state but never introduces new conflicts, so analyzing the originals keeps
# detection host-independent and deterministic.
#
# Spec syntax matches AsyncService._install_packages:
#   "<pep508-requirement>@<source>"
#     torch==2.10.0@https://download.pytorch.org/whl/cu128
#     realesrgan>=1.0@git+https://github.com/sberbank-ai/Real-ESRGAN.git
#
# Version-set emptiness is decided by witness search rather than by
# re-implementing PEP 440 interval arithmetic: candidate versions are
# generated from the boundary versions mentioned across the group and handed
# to `packaging` for the actual containment test. All PEP 440 semantics
# (`~=`, wildcards, epochs, pre/post/dev ordering) stay in the library that
# owns them.

_HOST_RUNTIMES = frozenset({ "native", "process", "embedded" })

class RuntimeIssueSeverity(str, Enum):
    ERROR   = "error"
    WARNING = "warning"

class RuntimeIssueCode(str, Enum):
    VERSION_CONFLICT      = "version-conflict"       # pinned specifiers provably cannot be satisfied simultaneously
    VERSION_INDETERMINATE = "version-indeterminate"  # witness search failed but no proof of conflict
    LOOSE_SHADOWED        = "loose-shadowed"         # unpinned requirement follows a pinned one
    ORDER_DEPENDENT       = "order-dependent"        # compatible but distinct pins; install order decides

    @property
    def severity(self) -> RuntimeIssueSeverity:
        if self in [ RuntimeIssueCode.VERSION_CONFLICT ]:
            return RuntimeIssueSeverity.ERROR

        return RuntimeIssueSeverity.WARNING

class PackageRequirement:
    def __init__(self, spec: str, owner: str):
        self.spec:      str            = spec           # original declaration
        self.owner:     str            = owner          # id of whoever declared it
        self.name:      Optional[str]  = None
        self.specifier: SpecifierSet   = SpecifierSet()
        self.extras:    FrozenSet[str] = frozenset()
        self.source:    Optional[str]  = None

        head, _, source = spec.partition("@")
        self.source = source or None

        try:
            requirement = Requirement(head)
        except Exception:
            return

        self.name      = canonicalize_name(requirement.name)
        self.specifier = requirement.specifier
        self.extras    = frozenset(canonicalize_name(e) for e in requirement.extras)

    @property
    def has_version_constraint(self) -> bool:
        return bool(self.specifier)

class RuntimeEnvironment:
    """Identity of a Python environment shared by one or more components.

    NATIVE / PROCESS / EMBEDDED all resolve to the host interpreter: `process`
    uses multiprocessing spawn, which re-execs `sys.executable` and therefore
    shares site-packages. VIRTUALENV is keyed by resolved path, not by
    component, because `runtime.path` may be shared deliberately. DOCKER and
    APPLE_CONTAINER runtimes always get a per-component container, even when
    they share an image tag, so each such component gets its own environment.
    """
    def __init__(self, kind: str, identity: str):
        self.kind:     str = kind      # "host" | "venv" | "container" | "unknown"
        self.identity: str = identity

    @classmethod
    def from_component(
        cls,
        component_id: str,
        runtime_type: str,
        runtime_path: Optional[str],
        image:        Optional[str],
    ) -> Self:
        """The environment this component's declared runtime resolves to.

        `process` and `embedded` land in the host environment along with
        `native` because they all execute against `sys.executable`'s
        site-packages.
        """
        if runtime_type in _HOST_RUNTIMES:
            return cls("host", "controller")

        if runtime_type == "virtualenv":
            # Mirror the resolution in mindor.core.runtime.virtualenv._resolve_venv_path
            # so ./venv, .venv, and an absolute equivalent all key the same environment.
            if runtime_path:
                resolved = (Path.cwd() / runtime_path).resolve()
            else:
                resolved = (Path.cwd() / ".runtime" / "components" / component_id / "venv").resolve()
            return cls("venv", str(resolved))

        if runtime_type in ("docker", "apple-container"):
            # Each container runtime component runs in its own container, even
            # when two components share an image tag. The environment is
            # therefore the container instance, not the image.
            return cls("container", f"{component_id}@{image}" if image else component_id)

        return cls("unknown", component_id)

    def __str__(self) -> str:
        return f"{self.kind}:{self.identity}"

    def __hash__(self) -> int:
        return hash((self.kind, self.identity))

    def __eq__(self, other: object) -> bool:
        return isinstance(other, RuntimeEnvironment) and (self.kind, self.identity) == (other.kind, other.identity)

@dataclass
class RuntimeIssue:
    code:         RuntimeIssueCode
    environment:  RuntimeEnvironment
    package:      str
    requirements: List[PackageRequirement] = field(default_factory=list)

class RequirementVersionResolver:
    """Stateless PEP 440 version arithmetic. Decides intersection membership
    for a set of specifiers by generating candidate versions and delegating
    the containment check to ``packaging``.
    """

    def resolve_shared_version(self, specifiers: Sequence[SpecifierSet]) -> Optional[Version]:
        """Return a version satisfying every specifier, or None when no
        witness is found.

        `prereleases=True` matches `is_requirement_satisfied` in the installer.
        A ``None`` return does not certify non-satisfiability — see
        ``is_provably_conflicting`` for the one case that does.
        """
        specifiers = [ specifier for specifier in specifiers if specifier ]

        if not specifiers:
            return None

        for version in self._witness_candidates(specifiers):
            if all(specifier.contains(version, prereleases=True) for specifier in specifiers):
                return version

        return None

    def is_provably_conflicting(self, specifiers: Sequence[SpecifierSet]) -> bool:
        """True when the intersection can be shown empty without a witness search.

        Only case covered today: two or more exact-version pins whose named
        versions cannot all be satisfied simultaneously. Parsing each pin
        into a ``Version`` and asking packaging whether one of them satisfies
        every specifier respects PEP 440's normalization (``==1`` and
        ``==1.0``) and local-version matching (``==2.5.1`` accepts
        ``2.5.1+cu121``). Every other case where witness search returns None
        is treated as indeterminate, since the search is incomplete and
        cannot certify non-satisfiability.
        """
        exact_versions: Set[Version] = set()

        for specifier_set in specifiers:
            for specifier in specifier_set:
                if specifier.operator == "==" and "*" not in specifier.version:
                    try:
                        exact_versions.add(Version(specifier.version))
                    except InvalidVersion:
                        continue

        if len(exact_versions) < 2:
            return False

        # If any of the named versions satisfies every specifier, the pins
        # are compatible via normalization or local-version matching.
        for version in exact_versions:
            if all(specifier.contains(version, prereleases=True) for specifier in specifiers):
                return False

        return True

    def _witness_candidates(self, specifiers: Sequence[SpecifierSet]) -> List[Version]:
        """Candidate versions used to search for a value in the intersection.

        Every non-empty allowed set is a union of intervals whose endpoints are
        the mentioned versions or wildcard boundaries derived from them.
        Testing endpoints alone misses witnesses strictly inside open
        intervals; each anchor is therefore paired with denser neighbors:

          - `anchor.dev0` and `anchor.post0` cover post/dev neighborhoods and
            pre-release ranges like `>1.0rc1, <1.0rc3` (witnessed by
            `1.0rc3.dev0`)
          - extended release tuples cover open ranges between adjacent
            mentioned versions: `>1, <1.1` is witnessed by `1.0.0.1.dev0`

        Failing to find a witness here is not a proof that the intersection
        is empty; callers should treat `None` from ``resolve_shared_version``
        as "no witness found" rather than "unsatisfiable".
        """
        anchors: Set[Version] = set()

        for version in self._mentioned_versions(specifiers):
            anchors.add(version)
            anchors |= self._release_variants(version)

        candidates: Set[Version] = { Version("0.dev0"), Version("99999") }
        candidates.update(anchors)

        for anchor in anchors:
            # PEP 440 forbids stacking the same suffix (`.post0.post0`) and
            # forbids `.post` after `.dev`; skip variants that would produce an
            # invalid Version string.
            if anchor.post is None and anchor.dev is None:
                candidates.add(Version(f"{anchor}.post0"))

            if anchor.dev is None:
                candidates.add(Version(f"{anchor}.dev0"))

            candidates.add(self._next_release_version(anchor))

        return sorted(candidates)

    def _next_release_version(self, anchor: Version) -> Version:
        """A witness strictly above ``anchor`` in the same release-tuple
        neighborhood, since `>anchor` excludes ``anchor``, ``anchor.post0``,
        and other same-release variants. Extending the release tuple (`1`
        becomes `1.0.0.1.dev0`) yields a value packaging orders strictly
        above ``anchor`` but below the next mentioned version.

        Pre-release neighborhoods (`>1.0rc1, <1.0rc3`) are already covered by
        the ``.dev0`` suffix applied in ``_witness_candidates``.
        """
        release_str = ".".join(str(part) for part in anchor.release)
        epoch = f"{anchor.epoch}!" if anchor.epoch else ""

        return Version(f"{epoch}{release_str}.0.0.1.dev0")

    def _mentioned_versions(self, specifiers: Iterable[SpecifierSet]) -> Set[Version]:
        versions: Set[Version] = set()

        for specifier_set in specifiers:
            for specifier in specifier_set:
                operand = specifier.version.rstrip(".*")

                try:
                    versions.add(Version(operand))
                except InvalidVersion:
                    continue  # `===` arbitrary equality

        return versions

    def _release_variants(self, version: Version) -> Set[Version]:
        """Prefix truncations and increments of a version's release tuple.

        Wildcard specifiers (`==2.8.*`) put their upper boundary at a version
        that is never written down anywhere (2.9), so boundaries have to be
        synthesized from the release tuple rather than read off the literals.
        """
        variants: Set[Version] = set()
        release = version.release
        epoch = f"{version.epoch}!" if version.epoch else ""

        for prefix_length in range(1, len(release) + 1):
            prefix      = release[:prefix_length]
            next_prefix = prefix[:-1] + (prefix[-1] + 1,)
            variants.add(Version(epoch + ".".join(str(part) for part in prefix)))
            variants.add(Version(epoch + ".".join(str(part) for part in next_prefix)))

        return variants

class RequirementAnalyzer:
    def __init__(self, environments: Dict[RuntimeEnvironment, List[PackageRequirement]]):
        self.environments: Dict[RuntimeEnvironment, List[PackageRequirement]] = environments

        self._version_resolver: RequirementVersionResolver = RequirementVersionResolver()

    def detect_issues(self) -> List[RuntimeIssue]:
        """Run every rule against every runtime environment and collect issues."""
        issues: List[RuntimeIssue] = []

        for environment, requirements in sorted(self.environments.items(), key=lambda kv: str(kv[0])):
            requirements_by_package: Dict[str, List[PackageRequirement]] = {}

            for requirement in requirements:
                if requirement.name is None:
                    continue

                requirements_by_package.setdefault(requirement.name, []).append(requirement)

            for package, requirements in sorted(requirements_by_package.items()):
                issues.extend(self._find_package_issues(environment, package, requirements))

        return issues

    def _find_package_issues(
        self,
        environment:  RuntimeEnvironment,
        package:      str,
        requirements: List[PackageRequirement],
    ) -> List[RuntimeIssue]:
        issues: List[RuntimeIssue] = []
        pinned_requirements = [ requirement for requirement in requirements if requirement.has_version_constraint ]
        loose_requirements  = [ requirement for requirement in requirements if not requirement.has_version_constraint ]

        if len(pinned_requirements) > 1:
            specifiers = [ requirement.specifier for requirement in pinned_requirements ]
            witness    = self._version_resolver.resolve_shared_version(specifiers)

            if witness is None:
                # No witness found. Distinguish provable conflicts (which
                # justify isolation) from indeterminate ones (which don't).
                if self._version_resolver.is_provably_conflicting(specifiers):
                    issues.append(RuntimeIssue(RuntimeIssueCode.VERSION_CONFLICT, environment, package, pinned_requirements))
                else:
                    issues.append(RuntimeIssue(RuntimeIssueCode.VERSION_INDETERMINATE, environment, package, pinned_requirements))

        # loose-shadowed — loose requirement beside a pinned one; the pin decides the version
        if loose_requirements and pinned_requirements:
            issues.append(RuntimeIssue(RuntimeIssueCode.LOOSE_SHADOWED, environment, package, loose_requirements + pinned_requirements))

        # order-dependent — distinct but compatible pins from multiple owners
        if len(pinned_requirements) > 1 and len({ str(requirement.specifier) for requirement in pinned_requirements }) > 1:
            if len({ requirement.owner for requirement in pinned_requirements }) > 1:
                if self._version_resolver.resolve_shared_version([ requirement.specifier for requirement in pinned_requirements ]) is not None:
                    issues.append(RuntimeIssue(RuntimeIssueCode.ORDER_DEPENDENT, environment, package, pinned_requirements))

        return issues

class RequirementCollector:
    """Group each component's declared package requirements by the Python
    environment they will share at runtime.

    Instantiates each component service (with `cache=False` so the throwaway
    instance does not pollute `ComponentInstances`) and reads what it declares
    via `_get_setup_requirements`. `ModelComponent` delegates its requirements
    to a task service exposed as `self.service`, so the collector reads both.
    """
    def __init__(self, config):  # ComposeConfig
        self.config = config

    def collect(self) -> Dict[RuntimeEnvironment, List[PackageRequirement]]:
        from mindor.core.component.component import create_component
        from mindor.core.component.base import ComponentGlobalConfigs

        global_configs = ComponentGlobalConfigs.create(
            components=self.config.components,
            listeners=self.config.listeners,
            gateways=self.config.gateways,
            workflows=self.config.workflows,
        )

        environments: Dict[RuntimeEnvironment, List[PackageRequirement]] = {}

        for component_config in self.config.components:
            try:
                component = create_component(
                    component_config.id, component_config, global_configs, daemon=False, cache=False,
                )
            except ValueError:
                continue  # unresolvable component type

            specs = self._collect_specs(component)

            if not specs:
                continue

            runtime = component_config.runtime
            environment = RuntimeEnvironment.from_component(
                component_id = component_config.id,
                runtime_type = runtime.type.value,
                runtime_path = getattr(runtime, "path", None),
                image        = getattr(runtime, "image", None),
            )

            environments.setdefault(environment, []).extend(PackageRequirement(spec, component_config.id) for spec in specs)

        return environments

    @staticmethod
    def _collect_specs(component) -> List[str]:
        specs = list(component._get_setup_requirements() or [])
        inner = getattr(component, "service", None)

        if inner is not None:
            specs.extend(inner._get_setup_requirements() or [])

        return specs
