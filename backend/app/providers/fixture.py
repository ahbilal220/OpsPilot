from typing import Any

from app.providers.contracts import ModelTask, ProviderResult


class FixtureModelProvider:
    """Deterministic, offline provider for the first N+1 vertical slice."""

    name = "fixture"
    model = "opspilot-n-plus-one-v1"

    async def generate(
        self,
        task: ModelTask,
        *,
        operation: str,
        input_data: dict[str, Any],
        output_schema: dict[str, Any],
        system_rules: tuple[str, ...],
    ) -> ProviderResult:
        del output_schema, system_rules
        if task == ModelTask.classification and operation == "triage":
            summary = str(input_data.get("incident_summary", "")).casefold()
            service = str(input_data.get("service_name") or "")
            signals = sum(
                term in summary
                for term in ("checkout", "recommendation", "latency", "query", "n+1")
            )
            supported = signals >= 2 or (
                service.casefold() == "checkout-api" and "latency" in summary
            )
            return ProviderResult(
                data={
                    "severity": input_data.get("severity", "high"),
                    "affected_services": [service or "checkout-api"] if supported else [],
                    "symptoms": [
                        "request latency increased",
                        "database queries per request increased",
                    ]
                    if supported
                    else ["incident is outside the Phase 3 fixture scope"],
                    "initial_categories": ["metrics", "database", "deployment", "code"]
                    if supported
                    else [],
                    "scope_supported": supported,
                    "scope_reason": (
                        "Matches the checkout recommendation N+1 fixture."
                        if supported
                        else "Phase 3 currently supports the checkout N+1 fixture only."
                    ),
                }
            )
        if task == ModelTask.planning and operation == "evidence_plan":
            if not input_data.get("scope_supported"):
                return ProviderResult(data={"calls": []})
            return ProviderResult(
                data={
                    "calls": [
                        {
                            "tool_name": "metrics.query",
                            "arguments": {"query": "demo_checkout_p95_latency_seconds"},
                            "purpose": "Confirm the reported latency increase.",
                        },
                        {
                            "tool_name": "logs.search",
                            "arguments": {
                                "service": "checkout-api",
                                "contains": "db_queries",
                                "limit": 20,
                            },
                            "purpose": "Inspect per-request latency and query counts.",
                        },
                        {
                            "tool_name": "database.diagnostics",
                            "arguments": {"diagnostic": "request_query_profile"},
                            "purpose": "Compare observed and expected queries per request.",
                        },
                        {
                            "tool_name": "deployments.history",
                            "arguments": {
                                "service": "checkout-api",
                                "environment": "demo",
                                "limit": 20,
                            },
                            "purpose": "Correlate onset with recent deployments.",
                        },
                        {
                            "tool_name": "repository.history",
                            "arguments": {"path": "catalog.py", "limit": 10},
                            "purpose": "Inspect recent changes to the affected module.",
                        },
                        {
                            "tool_name": "repository.search",
                            "arguments": {
                                "query": "for product_id in product_ids",
                                "path": "catalog.py",
                                "limit": 20,
                            },
                            "purpose": "Find the request-time loop in the recommendation loader.",
                        },
                    ]
                }
            )
        if task == ModelTask.reasoning and operation == "hypothesis":
            return ProviderResult(
                data={
                    "title": "N+1 query in the recommendation loader",
                    "description": (
                        "The recommendation loader performs one database lookup per product, "
                        "causing query count and request latency to grow with cart size."
                    ),
                    "supporting_evidence_ids": input_data.get("evidence_ids", []),
                    "contradicting_evidence_ids": [],
                    "validation_plan": [
                        "Confirm latency is elevated.",
                        "Confirm queries per request exceed the expected baseline.",
                        "Confirm a database lookup occurs inside the product loop.",
                        "Correlate the code with the recent deployment and commit.",
                    ],
                }
            )
        if task == ModelTask.reasoning and operation == "diagnosis":
            return ProviderResult(
                data={
                    "root_cause": "N+1 database queries in the recommendation loader",
                    "summary": (
                        "The checkout recommendation path loops over product IDs and performs "
                        "a database lookup for each item. The observed query count rose to 41–43 "
                        "per request alongside roughly 1.9 second request latency, and the recent "
                        "deployment contains the related loader change."
                    ),
                    "evidence_ids": input_data.get("evidence_ids", []),
                    "limitations": [
                        "This diagnosis uses the deterministic Phase 3 demo scenario.",
                        "No remediation or production change has been attempted.",
                    ],
                }
            )
        raise ValueError(f"Fixture provider does not support {task.value}/{operation}")
