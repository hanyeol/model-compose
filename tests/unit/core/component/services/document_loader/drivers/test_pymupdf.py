import asyncio
import pytest
from unittest.mock import MagicMock, patch
from mindor.dsl.schema.component import ComponentType, DocumentLoaderDriverType
from mindor.dsl.schema.component.impl.document_loader.impl.pymupdf import PymupdfDocumentLoaderComponentConfig
from mindor.dsl.schema.action.impl.document_loader.impl.pymupdf import PymupdfDocumentLoaderActionConfig
from mindor.core.component.services.document_loader.base import DocumentLoaderDriverRegistry
from mindor.core.component.services.document_loader.document_loader import DocumentLoaderComponent
from mindor.core.component.services.document_loader.drivers.pymupdf import (
    PymupdfDocumentLoaderService,
    PymupdfDocumentLoaderAction,
)



def test_pymupdf_driver_registration():
    """Verify PymupdfDocumentLoaderService is registered in DocumentLoaderDriverRegistry."""
    assert DocumentLoaderDriverType.PYMUPDF in DocumentLoaderDriverRegistry
    assert DocumentLoaderDriverRegistry[DocumentLoaderDriverType.PYMUPDF] is PymupdfDocumentLoaderService


def test_document_loader_component_loads_pymupdf():
    """Verify DocumentLoaderComponent creates PymupdfDocumentLoaderService driver successfully."""
    config = PymupdfDocumentLoaderComponentConfig(
        type=ComponentType.DOCUMENT_LOADER,
        driver=DocumentLoaderDriverType.PYMUPDF,
    )
    global_configs = MagicMock()
    comp = DocumentLoaderComponent(id="pymupdf_comp", config=config, global_configs=global_configs, daemon=False)

    assert isinstance(comp.driver, PymupdfDocumentLoaderService)


def test_pymupdf_page_range_parsing():
    """Verify page range string parsing (e.g. '1-3,5')."""
    indices = PymupdfDocumentLoaderAction._resolve_page_indices("1-3, 5", 10)
    assert indices == [0, 1, 2, 4]

    all_indices = PymupdfDocumentLoaderAction._resolve_page_indices(None, 4)
    assert all_indices == [0, 1, 2, 3]


def test_pymupdf_action_extract_text():
    """Verify PymupdfDocumentLoaderAction text extraction with mocked PDF document."""
    async def _run():
        mock_rect = MagicMock()
        mock_rect.x0, mock_rect.y0, mock_rect.x1, mock_rect.y1 = 0.0, 0.0, 600.0, 800.0

        mock_page1 = MagicMock()
        mock_page1.get_text.return_value = "Page 1 Content"
        mock_page1.rotation = 0
        mock_page1.rect = mock_rect

        mock_doc = MagicMock()
        mock_doc.__len__.return_value = 1
        mock_doc.__getitem__.return_value = mock_page1

        action_config = PymupdfDocumentLoaderActionConfig(
            source="test.pdf",
            extraction_mode="text",
        )
        context = MagicMock()

        async def _mock_render(var, scope=None):
            return var

        context.render_variable.side_effect = _mock_render

        action = PymupdfDocumentLoaderAction(config=action_config, context=context)

        with patch.object(action, "_resolve_source_path", return_value=("test.pdf", False)):
            with patch.object(action, "_open_pdf", return_value=mock_doc):
                res = await action._load_document("test.pdf", {"password": None, "extraction_mode": "text", "page_range": None})

        assert "pages" in res
        assert len(res["pages"]) == 1
        assert res["pages"][0]["text"] == "Page 1 Content"
        assert res["pages"][0]["index"] == 0
        assert res["pages"][0]["meta"]["number"] == 1

    asyncio.run(_run())


def test_pymupdf_action_streaming():
    """Verify PymupdfDocumentLoaderAction streaming page yield."""
    async def _run():
        mock_rect = MagicMock()
        mock_rect.x0, mock_rect.y0, mock_rect.x1, mock_rect.y1 = 0.0, 0.0, 600.0, 800.0

        mock_page1 = MagicMock()
        mock_page1.get_text.return_value = "Page 1 Text"
        mock_page1.rotation = 0
        mock_page1.rect = mock_rect

        mock_doc = MagicMock()
        mock_doc.__len__.return_value = 1
        mock_doc.__getitem__.return_value = mock_page1

        action_config = PymupdfDocumentLoaderActionConfig(
            source="test.pdf",
            streaming=True,
        )
        context = MagicMock()

        async def _mock_render(var, scope=None):
            return var

        context.render_variable.side_effect = _mock_render

        action = PymupdfDocumentLoaderAction(config=action_config, context=context)

        pages = []
        with patch.object(action, "_resolve_source_path", return_value=("test.pdf", False)):
            with patch.object(action, "_open_pdf", return_value=mock_doc):
                async for page in action._stream_document("test.pdf", {"password": None, "extraction_mode": "text", "page_range": None}):
                    pages.append(page)

        assert len(pages) == 1
        assert pages[0]["text"] == "Page 1 Text"

    asyncio.run(_run())
