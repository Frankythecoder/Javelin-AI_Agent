import threading
from typing import Dict, Any, Callable, Optional
from langchain_core.tools import StructuredTool
from pydantic import create_model, Field


class AgentControlState:
    def __init__(self):
        self.stopped = False
        self.tools_enabled = True
        self.lock = threading.Lock()

    def stop(self):
        with self.lock:
            self.stopped = True

    def disable_tools(self):
        with self.lock:
            self.tools_enabled = False

    def enable_tools(self):
        with self.lock:
            self.tools_enabled = True


class ToolDefinition:
    def __init__(self, name: str, description: str, parameters: Dict[str, Any], function: Callable[[Dict[str, Any]], str], requires_approval: bool = False):
        self.name = name
        self.description = description
        self.parameters = parameters
        self.function = function
        self.requires_approval = requires_approval


class ApprovalAwareTool(StructuredTool):
    """StructuredTool subclass that preserves the requires_approval flag."""
    requires_approval: bool = False


def _json_type_to_python(json_type: str):
    """Map JSON Schema types to Python types."""
    mapping = {
        "string": str,
        "integer": int,
        "number": float,
        "boolean": bool,
        "array": list,
        "object": dict,
    }
    return mapping.get(json_type, str)


def tool_definition_to_langchain(td: ToolDefinition) -> ApprovalAwareTool:
    """Convert a legacy ToolDefinition into a LangChain ApprovalAwareTool."""
    properties = td.parameters.get("properties", {})
    required_fields = set(td.parameters.get("required", []))

    field_definitions = {}
    for field_name, field_schema in properties.items():
        field_type = _json_type_to_python(field_schema.get("type", "string"))
        description = field_schema.get("description", "")
        if field_name in required_fields:
            field_definitions[field_name] = (field_type, Field(description=description))
        else:
            field_definitions[field_name] = (
                Optional[field_type],
                Field(default=None, description=description),
            )

    ArgsModel = create_model(f"{td.name}_args", **field_definitions)

    original_func = td.function

    def wrapper_func(**kwargs) -> str:
        # Strip None values so the original function only sees provided args
        cleaned = {k: v for k, v in kwargs.items() if v is not None}
        return original_func(cleaned)

    return ApprovalAwareTool(
        name=td.name,
        description=td.description,
        func=wrapper_func,
        args_schema=ArgsModel,
        requires_approval=td.requires_approval,
    )
