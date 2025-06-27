from enum import Enum

class ControllerType(str, Enum):
    HTTP_SERVER = "http-server"
    MCP_SERVER  = "mcp-server"
