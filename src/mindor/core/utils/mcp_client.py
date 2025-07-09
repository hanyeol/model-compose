from typing import Union, Optional, Dict, List, Tuple, AsyncIterator, Any
from mcp.client.streamable_http import streamablehttp_client
from mcp.types import ContentBlock, TextContent, ImageContent, AudioContent
from mcp.types import Resource, TextResourceContents, BlobResourceContents, GetPromptResult, Prompt
from mcp import ClientSession, Tool

class McpClient:
    def __init__(self, url: str, headers: Optional[Dict[str, str]] = None):
        self.url: str = url
        self.headers: Optional[Dict[str, str]] = headers
        self.session: Optional[ClientSession] = None
        self.client: Optional[Any] = None

    async def __aenter__(self):
        await self._ensure_initialized()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self._cleanup()

    async def call_tool(self, name: str, arguments: Optional[Dict[str, Any]] = None, raise_on_error: bool = True) -> List[ContentBlock]:
        """
        Call a specific tool on the MCP server
        
        Args:
            name: The name of the tool to call
            arguments: Arguments to pass to the tool
            raise_on_error: Whether to raise exceptions on error responses
            
        Returns:
            The tool execution result
        """
        await self._ensure_initialized()
        result = await self.session.call_tool(name, arguments)
        if result.isError:
            if raise_on_error:
                raise RuntimeError(f"Tool '{name}' failed with: {result.content}")
            else:
                return None
        return result.content

    async def list_tools(self) -> List[Tool]:
        """List all available tools from the MCP server"""
        await self._ensure_initialized()
        result = await self.session.list_tools()
        return result.tools

    async def read_resource(self, uri: str) -> List[Union[TextResourceContents, BlobResourceContents]]:
        """
        Read a specific resource from the MCP server
        
        Args:
            uri: The URI of the resource to read
            
        Returns:
            The resource content
        """
        await self._ensure_initialized()
        result = await self.session.read_resource(uri)
        return result.contents

    async def list_resources(self) -> List[Resource]:
        """List all available resources from the MCP server"""
        await self._ensure_initialized()
        result = await self.session.list_resources()
        return result.resources

    async def get_prompt(self, name: str, arguments: Optional[Dict[str, Any]] = None) -> GetPromptResult:
        """
        Get a specific prompt from the MCP server
        
        Args:
            name: The name of the prompt to get
            arguments: Arguments to pass to the prompt
            
        Returns:
            The prompt content
        """
        await self._ensure_initialized()
        result = await self.session.get_prompt(name, arguments)
        return result

    async def list_prompts(self) -> List[Prompt]:
        """List all available prompts from the MCP server"""
        await self._ensure_initialized()
        result = await self.session.list_prompts()
        return result.prompts

    async def ping(self) -> bool:
        """
        Ping the MCP server to check connectivity
        
        Returns:
            True if the server is reachable, False otherwise
        """
        try:
            await self._ensure_initialized()
            await self.session.send_ping()
            return True
        except:
            return False

    async def close(self) -> None:
        """Close the MCP client session"""
        await self._cleanup()

    async def _ensure_initialized(self):
        if not self.session:
            self.client = streamablehttp_client(self.url, headers=self.headers)
            read_stream, write_stream, _ = await self.client.__aenter__()
            self.session = ClientSession(read_stream, write_stream)
            await self.session.__aenter__()
            await self.session.initialize()

    async def _cleanup(self) -> None:
        if self.session:
            await self.client.__aexit__(None, None, None)
            await self.session.__aexit__(None, None, None)
            self.client = None
            self.session = None
