from pydantic import BaseModel

from app.tools.contracts import ToolContext, ToolDefinition, ToolRisk


class PolicyDecision(BaseModel):
    allowed: bool
    reason: str


class ToolPolicy:
    def evaluate(self, definition: ToolDefinition, context: ToolContext) -> PolicyDecision:
        if definition.name not in context.allowed_tools:
            return PolicyDecision(
                allowed=False, reason="Tool is not allowed in this workflow state"
            )
        if definition.risk not in {ToolRisk.pure, ToolRisk.read} or not definition.read_only:
            return PolicyDecision(
                allowed=False,
                reason="Mutating tools require an approval subsystem and are disabled in Phase 2",
            )
        return PolicyDecision(allowed=True, reason="Read-only tool allowed")
