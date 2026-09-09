from typing import Optional, Tuple
from pathlib import Path
from urllib.parse import urlparse
from mindor.core.utils.tarball import extract_tarball
import asyncio, urllib.request

async def download_github_tarball(repo_url: str, revision: Optional[str], dest_dir: Path) -> None:
    owner, repo = parse_github_url(repo_url)
    ref = revision or "HEAD"

    # GitHub's codeload endpoint returns a gzipped tar of the repo at any ref.
    # Unlike the raw archive redirect, it does not require following redirects.
    archive_url = f"https://codeload.github.com/{owner}/{repo}/tar.gz/{ref}"

    # GitHub tarballs wrap the tree in a top-level `<repo>-<sha>/` directory;
    # strip_top_level=True removes it so callers get the repository root at
    # `dest_dir/`. The response is streamed directly into the extractor to
    # avoid buffering the whole archive in memory.
    def _fetch_and_extract() -> None:
        request = urllib.request.Request(archive_url, headers={ "User-Agent": "model-compose" })

        try:
            with urllib.request.urlopen(request) as response:
                extract_tarball(response, dest_dir, strip_top_level=True)
        except Exception as e:
            raise RuntimeError(f"Failed to download {archive_url}: {e}") from e

    await asyncio.get_running_loop().run_in_executor(None, _fetch_and_extract)

def parse_github_url(repo_url: str) -> Tuple[str, str]:
    parsed_url = urlparse(repo_url)

    if parsed_url.netloc.lower() != "github.com":
        raise ValueError(f"Only GitHub repositories are supported, got: {repo_url}")

    parts = [ part for part in parsed_url.path.split("/") if part ]

    if len(parts) < 2:
        raise ValueError(f"Cannot parse owner/repo from GitHub URL: {repo_url}")

    owner, repo = parts[0], parts[1]

    if repo.endswith(".git"):
        repo = repo[:-4]

    return owner, repo
