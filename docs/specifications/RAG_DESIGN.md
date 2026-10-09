# RAG Design

## 1. RAG Use Cases

RAG is used for:

- runbooks,
- architecture documentation,
- service ownership metadata,
- previous incident reports,
- troubleshooting guides,
- API/service documentation.

RAG should not be used as a substitute for direct code search or live telemetry.

## 2. Retrieval Pipeline

```text
User/Agent Query
      |
      v
Query Classification
      |
      v
Query Rewrite
      |
      +----> BM25 / lexical
      |
      +----> pgvector semantic search
      |
      v
Candidate Merge
      |
      v
Metadata Filters
      |
      v
Reranker
      |
      v
Context Builder
      |
      v
LLM
```

## 3. Chunking

Recommended initial settings:

- 500–900 token chunks
- 80–150 token overlap
- retain heading hierarchy
- store repository/service metadata
- keep document version/hash

## 4. Metadata

Each chunk should include:

```json
{
  "service": "checkout-api",
  "doc_type": "runbook",
  "environment": "production",
  "version": "git-sha",
  "section": "Database saturation",
  "source_path": "docs/runbooks/checkout.md"
}
```

## 5. Retrieval Modes

### Semantic
Good for conceptual matching.

### Lexical
Good for:
- exact error codes,
- class names,
- environment variable names,
- stack traces.

### Hybrid
Default mode for OpsPilot.

## 6. Reranking

Post-MVP:
- cross-encoder,
- provider reranking API,
- lightweight local reranker.

## 7. Citation

The final answer must reference evidence/document chunk IDs.

Do not generate "citation-looking" text without actual database records.

## 8. RAG Evaluation

Metrics:

- Recall@K
- Precision@K
- MRR
- nDCG
- citation correctness
- answer groundedness

Create a labeled set of incident questions and expected relevant chunks.

## 9. Prompt Injection

Retrieved documents are untrusted.

The model must be told that instructions inside retrieved content are non-authoritative.
