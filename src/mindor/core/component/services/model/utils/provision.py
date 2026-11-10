from __future__ import annotations

from typing import Any, Union, Optional, Dict, List
from mindor.dsl.schema.component import ModelConfig, HuggingfaceModelConfig, LocalModelConfig, NamedModelConfig
from mindor.core.foundation.streaming.url import download_to_file
from mindor.core.logger import logging
from pathlib import Path
from urllib.parse import urlparse
import asyncio, os, shutil, tempfile, zipfile, tarfile

class HuggingfaceModelDownloader:
    async def download(
        self,
        repo_id: str,
        filename: Optional[str] = None,
        revision: Optional[str] = None,
        cache_dir: Optional[str] = None,
        allow_patterns: Optional[List[str]] = None,
        local_files_only: Union[bool, str] = False,
        token: Optional[str] = None,
    ) -> str:
        if filename:
            from huggingface_hub import hf_hub_download

            return await asyncio.to_thread(
                hf_hub_download,
                repo_id=repo_id,
                filename=filename,
                revision=revision,
                cache_dir=cache_dir,
                local_files_only=local_files_only,
                token=token,
            )
        else:
            from huggingface_hub import snapshot_download

            return await asyncio.to_thread(
                snapshot_download,
                repo_id=repo_id,
                revision=revision,
                cache_dir=cache_dir,
                allow_patterns=allow_patterns,
                local_files_only=local_files_only,
                token=token,
            )

class LocalModelDownloader:
    async def download(
        self,
        path: str,
        endpoint: str,
        method: str = "GET",
        headers: Optional[Dict[str, str]] = None,
        body: Optional[Any] = None,
        timeout: Optional[float] = None,
        bundled: bool = False,
    ) -> str:
        if bundled:
            await self._download_bundle(endpoint, Path(path), method, headers, body, timeout)
        else:
            await self._download_file(endpoint, Path(path), method, headers, body, timeout)

        return path

    async def _download_file(
        self,
        endpoint: str,
        path: Path,
        method: str,
        headers: Optional[Dict[str, str]],
        body: Optional[Any],
        timeout: Optional[float],
    ) -> None:
        logging.info(f"Downloading model from {endpoint}")

        await download_to_file(
            endpoint,
            path,
            method=method,
            headers=headers,
            body=body,
            timeout=timeout
        )

    async def _download_bundle(
        self,
        endpoint: str,
        path: Path,
        method: str,
        headers: Optional[Dict[str, str]],
        body: Optional[Any],
        timeout: Optional[float],
    ) -> None:
        # Extract into a sibling temp dir first, then atomically swap into place
        # so a partially extracted archive never masquerades as a valid model.
        path.parent.mkdir(parents=True, exist_ok=True)

        staging_dir = Path(tempfile.mkdtemp(prefix=f".{path.name}.", dir=str(path.parent)))
        suffix = self._archive_suffix(endpoint)

        with tempfile.NamedTemporaryFile(suffix=suffix, dir=str(path.parent), delete=False) as tmp:
            archive_path = Path(tmp.name)

        try:
            logging.info(f"Downloading bundled model from {endpoint}")

            await download_to_file(
                endpoint,
                archive_path,
                method=method,
                headers=headers,
                body=body,
                timeout=timeout
            )

            logging.info(f"Extracting bundled model to {path}")

            def _extract_bundle() -> None:
                self._extract_archive(archive_path, staging_dir)

                if path.exists():
                    shutil.rmtree(path)

                os.replace(staging_dir, path)

            await asyncio.to_thread(_extract_bundle)
        except BaseException:
            if staging_dir.exists():
                shutil.rmtree(staging_dir, ignore_errors=True)
            raise
        finally:
            if archive_path.exists():
                archive_path.unlink()

    def _extract_archive(self, archive_path: Path, path: Path) -> None:
        name = archive_path.name.lower()

        if name.endswith(".zip"):
            with zipfile.ZipFile(archive_path) as zf:
                zf.extractall(path)
            return

        if name.endswith((".tar.gz", ".tgz", ".tar")):
            with tarfile.open(archive_path) as tf:
                tf.extractall(path)
            return

        raise ValueError(f"Unsupported archive format: {archive_path.name}")

    def _archive_suffix(self, url: str) -> str:
        path = urlparse(url).path.lower()

        for suffix in (".tar.gz", ".tgz", ".tar", ".zip"):
            if path.endswith(suffix):
                return suffix

        raise ValueError(f"Unsupported archive format for bundled model url: {url}")

class ModelProvisioner:
    async def provision(self, model: ModelConfig, prefetch: bool = False) -> str:
        if isinstance(model, HuggingfaceModelConfig):
            if prefetch:
                return await HuggingfaceModelDownloader().download(
                    repo_id=model.repository,
                    filename=model.filename,
                    revision=model.revision,
                    cache_dir=os.path.expanduser(model.cache_dir) if model.cache_dir else None,
                    allow_patterns=model.allow_patterns,
                    local_files_only=model.local_files_only,
                    token=model.token,
                )

            return model.repository

        if isinstance(model, LocalModelConfig):
            # Resolve ``~`` against the running process's home — the config
            # travels unchanged from host to remote worker, so expansion has
            # to happen here, in the worker's own filesystem context.
            path = os.path.expanduser(model.path) if model.path else self._default_local_path(model)

            if os.path.exists(path):
                return path

            if not model.url:
                raise FileNotFoundError(f"Model not found: {path}")

            return await LocalModelDownloader().download(
                path=path,
                endpoint=model.url.endpoint,
                method=model.url.method,
                headers=model.url.headers,
                body=model.url.body,
                timeout=model.url.timeout,
                bundled=model.bundled,
            )

        if isinstance(model, NamedModelConfig):
            raise ValueError(
                f"NamedModelConfig ('{model.name}') cannot be resolved by the generic model provisioner; "
                "the driver must load it directly (e.g. via its own pretrained loader)."
            )

        raise ValueError(f"Unknown model config type: {type(model).__name__}")

    def _default_local_path(self, model: LocalModelConfig) -> str:
        """Derive a cache path from ``model.url`` when the caller did not set
        ``model.path``. The schema's ``validate_path_or_url`` guarantees a
        ``url`` is present whenever ``path`` is not.

        Bundled archives land in a directory named after the archive with its
        suffix stripped (``antelopev2.zip`` → ``antelopev2/``); plain files
        keep their basename. The cache root is read at call time so it
        follows the current process's home, not whichever filesystem parsed
        the config.
        """
        filename = os.path.basename(model.url.endpoint)

        if model.bundled:
            for suffix in (".tar.gz", ".tgz", ".tar", ".zip"):
                if filename.lower().endswith(suffix):
                    filename = filename[: -len(suffix)]
                    break

        cache_root = os.path.join(os.environ.get("XDG_CACHE_HOME", os.path.expanduser("~/.cache")), "models")
        subdir = model._cache_subdir()

        if subdir:
            return os.path.join(cache_root, subdir, filename)
        
        return os.path.join(cache_root, filename)
