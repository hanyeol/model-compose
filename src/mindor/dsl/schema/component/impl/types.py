from enum import Enum

class ComponentType(str, Enum):
    HTTP_SERVER   = "http-server"
    HTTP_CLIENT   = "http-client"
    MCP_SERVER    = "mcp-server"
    MCP_CLIENT    = "mcp-client"
    MODEL         = "model"
    VECTOR_STORE  = "vector-store"
    WORKFLOW      = "workflow"
    SHELL         = "shell"
    TEXT_SPLITTER = "text-splitter"
