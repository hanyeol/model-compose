from __future__ import annotations

from typing import Any, Union, Optional, Dict, List
from mindor.dsl.schema.component import ModelConfig, HuggingfaceModelConfig, LocalModelConfig, NamedModelConfig
from mindor.core.foundation.streaming.url import download_to_file
from mindor.core.logger import logging
from pathlib import Path
from urllib.parse import urlparse
import os, shutil, tempfile, zipfile, tarfile

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

            return hf_hub_download(
                repo_id=repo_id,
                filename=filename,
                revision=revision,
                cache_dir=cache_dir,
                local_files_only=local_files_only,
                token=token,
            )
        else:
            from huggingface_hub import snapshot_download

            return snapshot_download(
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

            self._extract_archive(archive_path, staging_dir)

            if path.exists():
                shutil.rmtree(path)
            os.replace(staging_dir, path)
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
                    cache_dir=model.cache_dir,
                    allow_patterns=model.allow_patterns,
                    local_files_only=model.local_files_only,
                    token=model.token,
                )

            return model.repository

        if isinstance(model, LocalModelConfig):
            if model.path and os.path.exists(model.path):
                return model.path

            if not model.url:
                raise FileNotFoundError(f"Model not found: {model.path}")

            return await LocalModelDownloader().download(
                path=model.path,
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
