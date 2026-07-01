"""Unit tests for `ComponentDockerRuntimeBackend` runtime-config injection.

After moving IPC to docker attach (stdin/stdout), the backend no longer
mounts a unix socket, injects env vars, or maps uids. It still owns:
- Image kind classification (STANDARD / DERIVED / CUSTOM).
- Default image tag / container name (used when the user did not supply one).
- Default entrypoint (`python -m mindor.core.component.runtime.docker`),
  applied to the resolved `*RuntimeParams` only when the user hasn't
  supplied one.

The backend never mutates the user-facing DSL config: image kind lives on
the `_image_kind` instance field; the default image tag / container name
come from `_default_image_tag()` / `_default_container_name()`, and the
base's `resolve_runtime()` only fills those in when the user's config
left them unset.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from mindor.core.component.runtime.common import ComponentImageSpec
from mindor.core.component.runtime.docker import ComponentDockerRuntimeBackend
from mindor.core.runtime.common import ContainerImageKind
from mindor.dsl.schema.runtime import DockerRuntimeConfig
from mindor.dsl.schema.runtime.impl.common import RuntimeType


def _runtime(**overrides) -> DockerRuntimeConfig:
    return DockerRuntimeConfig(type=RuntimeType.DOCKER, **overrides)


def _component(runtime: DockerRuntimeConfig) -> SimpleNamespace:
    return SimpleNamespace(runtime=runtime)


def _launcher(runtime: DockerRuntimeConfig) -> ComponentDockerRuntimeBackend:
    config = _component(runtime)
    return ComponentDockerRuntimeBackend(
        worker_id="test-worker",
        config=config,
        image_kind=ComponentImageSpec.resolve_image_kind(config),
    )


class TestEntrypointInjection:
    def test_sets_entrypoint_when_none(self):
        runtime = _runtime(image="test:latest")
        launcher = _launcher(runtime)
        params = launcher._resolve_runtime_params(runtime)
        assert params.entrypoint == [
            "python", "-m", "mindor.core.component.runtime.docker",
        ]
        # The user-facing config must not be mutated.
        assert runtime.entrypoint is None

    def test_preserves_user_provided_entrypoint(self):
        """If the user overrides entrypoint, they own booting the worker."""
        runtime = _runtime(image="test:latest", entrypoint=["/custom/bin"])
        launcher = _launcher(runtime)
        params = launcher._resolve_runtime_params(runtime)
        assert params.entrypoint == ["/custom/bin"]

    def test_preserves_user_provided_command(self):
        """Same opt-out signal — if `command` is set, we don't inject our entrypoint."""
        runtime = _runtime(image="test:latest", command=["something"])
        launcher = _launcher(runtime)
        params = launcher._resolve_runtime_params(runtime)
        assert params.entrypoint is None
        assert params.command == ["something"]


class TestNoIpcMutation:
    """Sanity: the attach-transport launcher must NOT introduce socket
    bind-mounts, `MINDOR_IPC_*` env vars, or uid overrides."""

    def test_does_not_add_volumes_for_ipc(self):
        launcher = _launcher(_runtime(image="test:latest"))
        # Either None or unchanged from the original — never grows for IPC.
        assert not launcher.config.runtime.volumes

    def test_does_not_set_ipc_env_var(self):
        launcher = _launcher(_runtime(image="test:latest"))
        env = launcher.config.runtime.environment or {}
        assert not any(k.startswith("MINDOR_IPC") for k in env)

    def test_does_not_force_user_mapping(self):
        launcher = _launcher(_runtime(image="test:latest"))
        # No uid override — let the image / user's runtime config decide.
        assert launcher.config.runtime.user is None

    def test_preserves_existing_volumes(self):
        from mindor.dsl.schema.containers.docker import DockerVolumeConfig
        existing = DockerVolumeConfig(type="bind", source="/host/data", target="/data")
        launcher = _launcher(_runtime(image="test:latest", volumes=[existing]))
        # The user's volumes still come through untouched.
        assert len(launcher.config.runtime.volumes) == 1
        assert launcher.config.runtime.volumes[0].target == "/data"

    def test_preserves_existing_environment(self):
        launcher = _launcher(_runtime(image="test:latest", environment={"FOO": "bar"}))
        assert launcher.config.runtime.environment == {"FOO": "bar"}


class TestImageKindResolution:
    def test_explicit_image_is_custom_kind(self):
        launcher = _launcher(_runtime(image="my-registry/foo:1.2.3"))
        assert launcher._image_kind == ContainerImageKind.CUSTOM
        # The user's image survives untouched on the DSL config.
        assert launcher.config.runtime.image == "my-registry/foo:1.2.3"

    def test_build_block_is_custom_kind(self):
        from mindor.dsl.schema.containers.docker import DockerBuildConfig
        launcher = _launcher(_runtime(build=DockerBuildConfig(context=".", dockerfile="Dockerfile")))
        assert launcher._image_kind == ContainerImageKind.CUSTOM
        # `build:` case falls back to a `mindor/component-...:latest` default.
        assert launcher._default_image_tag().startswith("mindor/component-")
        # Original `runtime.image` was never set by the user — backend must
        # not have written its derived tag back into the config.
        assert launcher.config.runtime.image is None

    def test_no_image_or_build_falls_through_to_standard_or_derived(self):
        launcher = _launcher(_runtime())
        assert launcher._image_kind in (ContainerImageKind.STANDARD, ContainerImageKind.DERIVED)
        assert launcher._default_image_tag().startswith("mindor/component")
        # Crucially the backend does NOT mutate `runtime.image` — that's
        # what lets a second backend built from the same config classify
        # the same image kind instead of seeing the resolved tag and
        # mis-flagging it as CUSTOM.
        assert launcher.config.runtime.image is None


class TestContainerName:
    def test_default_is_derived_from_worker_id(self):
        launcher = _launcher(_runtime(image="test:latest"))
        assert launcher._default_container_name() == "mindor-component-test-worker"
        # User-facing config keeps the original (None) value.
        assert launcher.config.runtime.container_name is None

    def test_user_provided_is_preserved(self):
        launcher = _launcher(_runtime(image="test:latest", container_name="mine"))
        # User's value stays on the DSL config; the default hook is not consulted.
        assert launcher.config.runtime.container_name == "mine"


class TestConfigImageAndContainerNameUntouched:
    """The user-facing DSL config must keep its original `image` /
    `container_name` so the same config can be reused to build another
    launcher (or be serialized to the worker side) without the launcher's
    decisions leaking out."""

    def test_runtime_image_not_mutated_when_user_did_not_supply(self):
        original = _runtime()
        _ = _launcher(original)
        assert original.image is None

    def test_runtime_image_kept_as_supplied_when_user_did(self):
        original = _runtime(image="my-registry/foo:1.2.3")
        _ = _launcher(original)
        assert original.image == "my-registry/foo:1.2.3"

    def test_runtime_container_name_not_mutated_when_user_did_not_supply(self):
        original = _runtime()
        _ = _launcher(original)
        assert original.container_name is None


class TestImageKindStableAcrossRebuilds:
    """A launcher does not write its resolved tag back into `runtime.image`,
    so reconstructing a launcher from the same config still classifies the
    original STANDARD / DERIVED / CUSTOM case correctly — it would otherwise see
    the tag the first launcher wrote and misclassify STANDARD/DERIVED as CUSTOM."""

    def test_standard_kind_survives_second_launcher_on_same_config(self):
        runtime = _runtime()
        first = _launcher(runtime)
        # The standard/derived split depends on whether a real `requirements.txt`
        # exists in cwd at test time — assert the kind is whichever one the
        # first launcher chose, and require the second to match it.
        second = _launcher(runtime)
        assert second._image_kind == first._image_kind
        assert second._image_kind in (ContainerImageKind.STANDARD, ContainerImageKind.DERIVED)
        assert second._default_image_tag() == first._default_image_tag()

    def test_custom_kind_survives_second_launcher_on_same_config(self):
        runtime = _runtime(image="my-registry/foo:1.2.3")
        first = _launcher(runtime)
        assert first._image_kind == ContainerImageKind.CUSTOM
        second = _launcher(runtime)
        assert second._image_kind == ContainerImageKind.CUSTOM
        # User's image survives; the default hook is not consulted.
        assert second.config.runtime.image == "my-registry/foo:1.2.3"
