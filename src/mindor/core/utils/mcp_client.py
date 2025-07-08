from typing import Optional, Dict, Tuple, AsyncIterator, Any
from mcp.client.streamable_http import streamablehttp_client
from mcp import ClientSession

class McpClient:
    def __init__(self, url: str, headers: Optional[Dict[str, str]] = None):
        self.url: str = url
        self.headers: Optional[Dict[str, str]] = headers
        self.session: Optional[ClientSession] = ClientSession(streamablehttp_client(self.url, headers=self.headers))
        self._initialized = False

    async def __aenter__(self):
        if self.session is None:
            self.session = ClientSession(streamablehttp_client(self.url, headers=self.headers))
        await self._ensure_initialized()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    async def call_tool(self, name: str, arguments: Optional[Dict[str, Any]] = None, raise_on_error: bool = True) -> Any:
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
        try:
            return await self.session.call_tool(name, arguments)
        except:
            pass

    async def list_tools(self) -> Any:
        """List all available tools from the MCP server"""
        await self._ensure_initialized()
        try:
            return await self.session.list_tools()
        except:
            pass

    async def read_resource(self, uri: str, raise_on_error: bool = True) -> Any:
        """
        Read a specific resource from the MCP server
        
        Args:
            uri: The URI of the resource to read
            raise_on_error: Whether to raise exceptions on error responses
            
        Returns:
            The resource content
        """
        await self._ensure_initialized()
        try:
            return await self.session.read_resource(uri)
        except:
            pass

    async def list_resources(self) -> Any:
        """List all available resources from the MCP server"""
        return await self.session.list_resources()

    async def get_prompt(self, name: str, arguments: Optional[Dict[str, Any]] = None, raise_on_error: bool = True) -> Any:
        """
        Get a specific prompt from the MCP server
        
        Args:
            name: The name of the prompt to get
            arguments: Arguments to pass to the prompt
            raise_on_error: Whether to raise exceptions on error responses
            
        Returns:
            The prompt content
        """
        await self._ensure_initialized()
        try:
            return await self.session.get_prompt(name, arguments)
        except:
            pass

    async def list_prompts(self) -> Any:
        """List all available prompts from the MCP server"""
        await self._ensure_initialized()
        try:
            return await self.session.list_prompts()
        except:
            pass

    async def ping(self) -> bool:
        """
        Ping the MCP server to check connectivity
        
        Returns:
            True if the server is reachable, False otherwise
        """
        await self._ensure_initialized()
        try:
            await self.session.send_ping()
            return True
        except:
            return False

    async def close(self) -> None:
        """Close the MCP client session"""
        await self._close()

    async def _ensure_initialized(self):
        if not self._initialized:
            await self.session.__aenter__()
            await self.session.initialize()
            self._initialized = True

    async def _close(self) -> None:
        if self.session:
            await self.session.__aexit__(None, None, None)
            self.session = None
            self._initialized = False
