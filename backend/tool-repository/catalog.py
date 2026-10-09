"""Deterministic source fixture for Phase 2 repository tools."""


def load_recommendations(database, product_ids):
    recommendations = []
    for product_id in product_ids:
        # Intentional N+1 fixture. Phase 2 may inspect it but must not modify it.
        recommendations.extend(database.query_recommendations(product_id))
    return recommendations
