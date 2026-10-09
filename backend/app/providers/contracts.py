import enum
from dataclasses import dataclass
from typing import Any, Protocol


class ModelTask(enum.StrEnum):
    classification = "classification"
    extraction = "extraction"
    planning = "planning"
    reasoning = "reasoning"
    patch_generation = "patch_generation"


@dataclass(frozen=True)
class ProviderResult:
    data: dict[str, Any]
    prompt_tokens: int = 0
    completion_tokens: int = 0
    estimated_cost_usd: float = 0


class StructuredModelProvider(Protocol):
    name: str
    model: str

    async def generate(
        self,
        task: ModelTask,
        *,
        operation: str,
        input_data: dict[str, Any],
        output_schema: dict[str, Any],
        system_rules: tuple[str, ...],
    ) -> ProviderResult: ...
