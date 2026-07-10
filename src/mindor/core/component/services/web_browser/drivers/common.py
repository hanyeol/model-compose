from __future__ import annotations

from typing import Optional, Dict, List, Any
from collections.abc import AsyncIterator
from abc import ABC, abstractmethod
from dataclasses import dataclass
from mindor.dsl.schema.action import WebBrowserActionConfig, WebBrowserActionMethod, VideoAudioEncodingConfig, VideoEncoderConfig, AudioEncoderConfig
from mindor.core.foundation.streaming.iterators import StreamChunkIterator, StreamIterator
from mindor.core.foundation.streaming.video import VideoStreamResource
from PIL import Image as PILImage
from mindor.core.foundation.variable.time import parse_duration
from mindor.core.foundation.variable.bitrate import parse_bitrate
from ..base import ComponentActionContext


@dataclass
class VideoEncoderParams:
    codec: Optional[str] = None
    bitrate: Optional[int] = None
    resolution: Optional[str] = None
    fps: Optional[float] = None


@dataclass
class AudioEncoderParams:
    codec: Optional[str] = None
    bitrate: Optional[int] = None


@dataclass
class VideoAudioEncodingParams:
    """Rendered encoding parameters ready for the session/recorder layer.

    Values here are already resolved from variable references (${input.foo})
    and normalized (e.g. bitrate parsed to bits per second), so downstream
    consumers don't need to touch the DSL config again.
    """
    format: Optional[str] = None
    video: Optional[VideoEncoderParams] = None
    audio: Optional[AudioEncoderParams] = None


class WebBrowserSession(ABC):
    """Abstract browser session exposing high-level browser actions."""

    @abstractmethod
    async def navigate(self, url: str, wait_until: str, timeout: float) -> Dict[str, Any]:
        pass

    @abstractmethod
    async def wait_for(
        self,
        selector: Optional[str],
        xpath: Optional[str],
        condition: str,
        timeout: float
    ) -> None:
        pass

    @abstractmethod
    async def extract(
        self,
        selector: Optional[str],
        xpath: Optional[str],
        extract_mode: str,
        attribute: Optional[str],
        multiple: bool
    ) -> Any:
        pass

    @abstractmethod
    async def screenshot(
        self,
        full_page: bool,
        selector: Optional[str],
        format: str,
        quality: Optional[int]
    ) -> PILImage.Image:
        pass

    @abstractmethod
    async def capture_video(
        self,
        url: Optional[str],
        selector: Optional[str],
        include_video_track: bool,
        include_audio_track: bool,
        encoding: Optional[VideoAudioEncodingParams],
        duration: Optional[float],
    ) -> VideoStreamResource:
        pass

    @abstractmethod
    async def evaluate(self, expression: str) -> Any:
        pass

    @abstractmethod
    async def click(
        self,
        selector: Optional[str],
        xpath: Optional[str],
        x: Optional[int],
        y: Optional[int],
        timeout: float
    ) -> Dict[str, Any]:
        pass

    @abstractmethod
    async def input(
        self,
        selector: Optional[str],
        xpath: Optional[str],
        text: str,
        clear_first: bool,
        timeout: float
    ) -> Dict[str, Any]:
        pass

    @abstractmethod
    async def scroll(
        self,
        selector: Optional[str],
        xpath: Optional[str],
        x: Optional[int],
        y: Optional[int]
    ) -> Dict[str, Any]:
        pass

    @abstractmethod
    async def get_cookies(self, urls: Optional[List[str]]) -> List[Dict[str, Any]]:
        pass

    @abstractmethod
    async def set_cookies(self, cookies: List[Dict[str, Any]]) -> None:
        pass

    @abstractmethod
    async def close(self) -> None:
        pass

class WebBrowserAction:
    def __init__(self, config: WebBrowserActionConfig, timeout: Optional[str]):
        self.config: WebBrowserActionConfig = config
        self.timeout = timeout

    async def run(self, context: ComponentActionContext, session: WebBrowserSession) -> Any:
        timeout = parse_duration((await context.render_variable(self.config.timeout) if self.config.timeout else self.timeout) or 30.0)

        is_direct_output = not self.config.output or self.config.output == "${result}"

        result = await self._dispatch(context, self.config.method, session, timeout)

        if isinstance(result, (StreamIterator, AsyncIterator)):
            async def _stream_chunk_generator(result=result, scope=f"stream:{id(result)}"):
                async for chunk in result:
                    context.register_source("result[]", chunk, scope=scope)
                    yield (await context.render_variable(self.config.output, scope=scope)) if not is_direct_output else chunk

            return StreamChunkIterator(_stream_chunk_generator(), is_fragmented=False)

        context.register_source("result", result)

        return (await context.render_variable(self.config.output)) if not is_direct_output else result

    async def _dispatch(
        self,
        context: ComponentActionContext,
        method: WebBrowserActionMethod,
        session: WebBrowserSession,
        timeout: float,
    ) -> Any:
        # Navigation
        if method == WebBrowserActionMethod.NAVIGATE:
            url        = await context.render_variable(self.config.url)
            wait_until = await context.render_variable(self.config.wait_until)

            if url is None:
                raise ValueError("'url' must be specified for 'navigate' method")

            return await session.navigate(url, wait_until, timeout)

        # Query
        if method == WebBrowserActionMethod.WAIT_FOR:
            selector  = await context.render_variable(self.config.selector) if self.config.selector else None
            xpath     = await context.render_variable(self.config.xpath) if self.config.xpath else None
            condition = await context.render_variable(self.config.condition)

            return await session.wait_for(selector, xpath, condition, timeout)

        if method == WebBrowserActionMethod.EXTRACT:
            selector     = await context.render_variable(self.config.selector) if self.config.selector else None
            xpath        = await context.render_variable(self.config.xpath) if self.config.xpath else None
            extract_mode = await context.render_variable(self.config.extract_mode)
            attribute    = await context.render_variable(self.config.attribute) if self.config.attribute else None
            multiple     = bool(await context.render_variable(self.config.multiple))

            if selector:
                if isinstance(selector, dict):
                    return { key: await session.extract(expr, None, extract_mode, attribute, multiple) for key, expr in selector.items() }
                if isinstance(selector, list):
                    return [ await session.extract(expr, None, extract_mode, attribute, multiple) for expr in selector ]
                return await session.extract(selector, None, extract_mode, attribute, multiple)

            if xpath:
                if isinstance(xpath, dict):
                    return { key: await session.extract(None, expr, extract_mode, attribute, multiple) for key, expr in xpath.items() }
                if isinstance(xpath, list):
                    return [ await session.extract(None, expr, extract_mode, attribute, multiple) for expr in xpath ]
                return await session.extract(None, xpath, extract_mode, attribute, multiple)

            return await session.extract(None, None, extract_mode, attribute, multiple)

        if method == WebBrowserActionMethod.SCREENSHOT:
            selector  = await context.render_variable(self.config.selector) if self.config.selector else None
            full_page = bool(await context.render_variable(self.config.full_page))
            format    = await context.render_variable(self.config.format)
            quality   = await context.render_variable(self.config.quality) if self.config.quality is not None else None

            return await session.screenshot(full_page, selector, format, quality)

        # Media capture
        if method == WebBrowserActionMethod.CAPTURE_VIDEO:
            url                 = await context.render_variable(self.config.url) if self.config.url else None
            selector            = await context.render_variable(self.config.selector) if self.config.selector else None
            include_video_track = bool(await context.render_variable(self.config.include_video_track))
            include_audio_track = bool(await context.render_variable(self.config.include_audio_track))
            encoding            = await self._resolve_encoding_params(context, self.config.encoding) if self.config.encoding else None
            duration            = parse_duration(await context.render_variable(self.config.duration)) if self.config.duration else None

            return await session.capture_video(url, selector, include_video_track, include_audio_track, encoding, duration)

        # Interaction
        if method == WebBrowserActionMethod.CLICK:
            selector = await context.render_variable(self.config.selector) if self.config.selector else None
            xpath    = await context.render_variable(self.config.xpath) if self.config.xpath else None
            x        = await context.render_variable(self.config.x) if self.config.x is not None else None
            y        = await context.render_variable(self.config.y) if self.config.y is not None else None

            return await session.click(selector, xpath, x, y, timeout)

        if method == WebBrowserActionMethod.INPUT_TEXT:
            selector    = await context.render_variable(self.config.selector) if self.config.selector else None
            xpath       = await context.render_variable(self.config.xpath) if self.config.xpath else None
            text        = await context.render_variable(self.config.text)
            clear_first = bool(await context.render_variable(self.config.clear_first))

            if text is None:
                raise ValueError("'text' must be specified for 'input-text' method")

            return await session.input(selector, xpath, text, clear_first, timeout)

        if method == WebBrowserActionMethod.SCROLL:
            selector = await context.render_variable(self.config.selector) if self.config.selector else None
            xpath    = await context.render_variable(self.config.xpath) if self.config.xpath else None
            x        = int(await context.render_variable(self.config.x)) if self.config.x is not None else None
            y        = int(await context.render_variable(self.config.y)) if self.config.y is not None else None

            return await session.scroll(selector, xpath, x, y)

        if method == WebBrowserActionMethod.EVALUATE:
            expression = await context.render_variable(self.config.expression)

            if expression is None:
                raise ValueError("'expression' must be specified for 'evaluate' method")

            return await session.evaluate(expression)

        # State
        if method == WebBrowserActionMethod.GET_COOKIES:
            urls = await context.render_variable(self.config.urls) if self.config.urls else None

            return await session.get_cookies(urls)

        if method == WebBrowserActionMethod.SET_COOKIES:
            cookies = await context.render_variable(self.config.cookies)

            if cookies is None:
                raise ValueError("'cookies' must be specified for 'set-cookies' method")

            return await session.set_cookies(cookies)

        raise ValueError(f"Unsupported web-browser action method: {method}")

    async def _resolve_encoding_params(self, context: ComponentActionContext, config: VideoAudioEncodingConfig) -> VideoAudioEncodingParams:
        format = await context.render_variable(config.format) if config.format else None

        return VideoAudioEncodingParams(
            format=format,
            video=await self._resolve_video_encoder(context, config.video) if config.video else None,
            audio=await self._resolve_audio_encoder(context, config.audio) if config.audio else None,
        )

    async def _resolve_video_encoder(self, context: ComponentActionContext, config: VideoEncoderConfig) -> VideoEncoderParams:
        codec      = await context.render_variable(config.codec)      if config.codec      else None
        bitrate    = await context.render_variable(config.bitrate)    if config.bitrate    else None
        resolution = await context.render_variable(config.resolution) if config.resolution else None
        fps        = await context.render_variable(config.fps)        if config.fps        else None

        return VideoEncoderParams(
            codec=codec,
            bitrate=parse_bitrate(bitrate) if bitrate is not None else None,
            resolution=resolution,
            fps=float(fps) if fps is not None else None,
        )

    async def _resolve_audio_encoder(self, context: ComponentActionContext, config: AudioEncoderConfig) -> AudioEncoderParams:
        codec   = await context.render_variable(config.codec)   if config.codec   else None
        bitrate = await context.render_variable(config.bitrate) if config.bitrate else None

        return AudioEncoderParams(
            codec=codec,
            bitrate=parse_bitrate(bitrate) if bitrate is not None else None,
        )
