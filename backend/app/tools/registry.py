from app.tools.contracts import ToolAdapter, ToolDefinition
from app.tools.errors import UnknownToolError


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, ToolAdapter] = {}

    def register(self, tool: ToolAdapter) -> None:
        name = tool.definition.name
        if name in self._tools:
            raise ValueError(f"Tool already registered: {name}")
        self._tools[name] = tool

    def get(self, name: str) -> ToolAdapter:
        try:
            return self._tools[name]
        except KeyError:
            raise UnknownToolError("Tool is not registered") from None

    @property
    def names(self) -> frozenset[str]:
        return frozenset(self._tools)

    def definitions(self) -> list[ToolDefinition]:
        return [self._tools[name].definition for name in sorted(self._tools)]
