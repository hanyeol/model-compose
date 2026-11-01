from typing import Optional, List, Tuple, Union
from abc import ABC
from .package.installer import install_package, parse_requirement, is_requirement_satisfied

class RequirementManager(ABC):
    """Base for anything that declares PEP 508-style package requirements and
    has a setup/teardown lifecycle. Subclasses override `_get_setup_requirements`
    to declare specs and `_setup`/`_teardown` for their own init/cleanup work;
    the base handles lazy install at `setup()` time."""

    def get_declared_requirements(self) -> List[str]:
        specs: List[str] = []

        for item in self._get_setup_requirements() or []:
            specs.append(item[0] if isinstance(item, tuple) else item)

        return specs

    async def setup(self) -> None:
        requirements = self._get_setup_requirements()

        if requirements:
            await self._install_packages(requirements)

        await self._setup()

    async def teardown(self) -> None:
        await self._teardown()

    async def _setup(self) -> None:
        pass

    async def _teardown(self) -> None:
        pass

    def _get_setup_requirements(self) -> Optional[List[Union[str, Tuple[str, List[str]]]]]:
        return None

    async def _install_packages(self, packages: List[Union[str, Tuple[str, List[str]]]]) -> None:
        for package in packages:
            package_spec, canonical_names = package if isinstance(package, tuple) else (package, None)
            package_spec, repository = (package_spec.split("@") + [ None ])[:2]
            requirement = parse_requirement(package_spec)

            if not requirement or not is_requirement_satisfied(requirement, repository, canonical_names):
                await self._install_package(package_spec, repository)

    async def _install_package(self, package_spec: str, repository: Optional[str]) -> None:
        await install_package(package_spec, repository)
