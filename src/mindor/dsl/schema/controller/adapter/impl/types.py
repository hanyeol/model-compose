from enum import Enum

class ControllerAdapterType(str, Enum):
    HTTP_SERVER      = "http-server"
    MCP_SERVER       = "mcp-server"
    QUEUE_SUBSCRIBER = "queue-subscriber"
