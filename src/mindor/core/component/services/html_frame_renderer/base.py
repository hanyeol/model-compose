from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Type, Dict, Any
from abc import abstractmethod
from pathlib import Path
from mindor.dsl.schema.component import HtmlFrameRendererComponentConfig, HtmlFrameRendererDriver
from mindor.dsl.schema.action import HtmlFrameRendererActionConfig
from mindor.core.foundation import AsyncService
from mindor.core.utils.files import save_string_to_temporary_file
from mindor.core.utils.url import UrlResource, is_http_url
from ...context import ComponentActionContext

if TYPE_CHECKING:
    from .drivers.common import HtmlFrameRendererSession

class HtmlFrameRendererService(AsyncService):
    def __init__(self, id: str, config: HtmlFrameRendererComponentConfig, daemon: bool):
        super().__init__(daemon)

        self.id: str = id
        self.config: HtmlFrameRendererComponentConfig = config

        self._htmls: Dict[str, UrlResource] = {}

    async def run(self, action: HtmlFrameRendererActionConfig, context: ComponentActionContext) -> Any:
        return await self._run(action, context)

    async def _stop(self) -> None:
        await self._close_browser()

        for html in self._htmls.values():
            html.close()
        self._htmls.clear()

        await super()._stop()

    @abstractmethod
    async def _run(self, action: HtmlFrameRendererActionConfig, context: ComponentActionContext) -> Any:
        pass

    @abstractmethod
    async def _create_session(self) -> HtmlFrameRendererSession:
        """Create a fresh session backed by a browser page."""
        pass

    async def _close_browser(self) -> None:
        """Release browser-level resources. Override in drivers that own a
        browser process (e.g. Playwright)."""
        pass

    async def _resolve_html(self, name: str) -> UrlResource:
        if name not in self._htmls:
            html = next(html for html in self.config.htmls if html.name == name)
            self._htmls[name] = await self._build_html_source(html.source)

        return self._htmls[name]

    async def _build_html_source(self, source: str) -> UrlResource:
        """Turn an html source into a page URL.

        Resolution order:
          1. http(s):// URL         → URL as-is
          2. Existing directory     → file://<dir>/index.html
          3. Existing file          → file://<file>
          4. Otherwise (inline HTML) → temp file, file://<tmp>
        """
        if not is_http_url(source):
            html_path = Path(source).expanduser()

            if html_path.is_dir():
                html_path = html_path / "index.html"

            if html_path.is_file():
                return UrlResource(html_path.resolve().as_uri())

            html_path = Path(await save_string_to_temporary_file(source, extension="html"))

            return UrlResource(html_path.as_uri(), cleanup=lambda: html_path.unlink(missing_ok=True))

        return UrlResource(source)

def register_html_frame_renderer_service(driver: HtmlFrameRendererDriver):
    def decorator(cls: Type[HtmlFrameRendererService]) -> Type[HtmlFrameRendererService]:
        HtmlFrameRendererServiceRegistry[driver] = cls
        return cls
    return decorator

HtmlFrameRendererServiceRegistry: Dict[HtmlFrameRendererDriver, Type[HtmlFrameRendererService]] = {}
