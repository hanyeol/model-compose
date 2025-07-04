from enum import Enum

class ComponentType(str, Enum):
    HTTP_SERVER = "http-server"
    HTTP_CLIENT = "http-client"
    MCP_SERVER  = "mcp-server"
    MCP_CLIENT  = "mcp-client"
    SHELL       = "shell"
