---
name: dev/rag-architect
description: >
  Design RAG pipelines with chunking strategies, embedding selection,
  retrieval optimization, and evaluation frameworks.
allowed-tools: [Read, Write, Edit, Bash, Grep, Glob, Agent]
---

# RAG Architect — `/dev rag-architect <system>`

> **Agent:** Paulo (Dev Lead) + Andre (Backend) | **Framework:** RAG Pipeline Design

## RAG Pipeline Stages

```
Documents -> Chunking -> Embedding -> Vector DB -> Retrieval -> Reranking -> Generation
```

## Chunking Strategies

| Strategy | Best For | Tradeoff |
|----------|----------|----------|
| **Fixed-size** (token/char) | Uniform docs, consistent sizes | May break semantic units |
| **Sentence-based** | Narrative text, articles | Variable chunk sizes |
| **Paragraph-based** | Structured docs, technical docs | Highly variable sizes |
| **Semantic** | Long-form, topic shifts | Complex, computationally expensive |
| **Recursive** | Mixed content types | Optimal utilization, complex logic |
| **Document-aware** | Multi-format collections | Format-specific implementation |

Rule of thumb: 10-20% overlap between chunks to maintain context continuity.

## Embedding Model Selection

| Category | Model | Dims | Speed | Use Case |
|----------|-------|------|-------|----------|
| Fast | all-MiniLM-L6-v2 | 384 | ~14K tok/s | Prototyping, low-latency |
| Balanced | all-mpnet-base-v2 | 768 | ~2.8K tok/s | Most applications |
| Quality | text-embedding-ada-002 | 1536 | API | Production, complex domains |
| Code | CodeBERT / GraphCodeBERT | 768 | Varies | Code search |
| Multilingual | LaBSE / multilingual-e5 | 768 | Varies | Multi-language corpora |

## Vector Database Comparison

| DB | Type | Best For | Limitation |
|----|------|----------|-----------|
| **Pinecone** | Managed | Production, auto-scaling | Vendor lock-in, cost |
| **Qdrant** | Self-hosted | High performance, low memory | Smaller community |
| **Weaviate** | Self-hosted/Cloud | Complex data, GraphQL | Learning curve |
| **Chroma** | Embedded | Dev/testing, prototyping | Not production-scale |
| **pgvector** | PostgreSQL ext. | Existing PG infra, ACID | Less specialized |

## Retrieval Strategies

| Strategy | Mechanism | When to Use |
|----------|-----------|------------|
| **Dense** | Embedding cosine similarity | Semantic matching, paraphrasing |
| **Sparse** | BM25, TF-IDF | Exact keyword matching |
| **Hybrid** | Dense + sparse with RRF fusion | Best of both, production default |
| **Reranking** | Cross-encoder second pass | Higher precision needed |

## Query Transformation Techniques

| Technique | How It Works | Benefit |
|-----------|-------------|---------|
| **HyDE** | Generate hypothetical answer, embed that | Matches document style |
| **Multi-Query** | Generate 3-5 query variations, merge results | Increases recall |
| **Step-Back** | Broaden query to general form | Better general context |

## Evaluation Metrics

| Metric | Target | Measures |
|--------|--------|----------|
| **Faithfulness** | > 90% | Answers grounded in retrieved context |
| **Context Relevance** | > 0.80 | Retrieved chunks relevant to query |
| **Answer Relevance** | > 0.85 | Answer addresses the question |
| **Precision@K** | > 0.70 | Top-K results that are relevant |
| **MRR** | > 0.75 | Rank of first relevant result |

Use RAGAS framework for comprehensive end-to-end evaluation.

## Design Checklist

- [ ] Chunking strategy selected and tested on sample docs
- [ ] Embedding model benchmarked for domain
- [ ] Vector DB chosen based on scale and infra constraints
- [ ] Retrieval strategy defined (dense/sparse/hybrid)
- [ ] Reranking layer evaluated for precision gain vs latency
- [ ] Query transformation tested for recall improvement
- [ ] Evaluation pipeline set up with ground-truth dataset
- [ ] Caching strategy defined (query-level, semantic, chunk-level)
- [ ] Fallback mechanisms for retrieval failures
- [ ] Cost per query estimated and budgeted

## Proactive Triggers

Surface these issues WITHOUT being asked:

- Chunk size >2000 tokens with complex data → flag retrieval quality risk
- No evaluation metrics defined → flag unmeasurable quality
- Single retrieval strategy → suggest hybrid (semantic + keyword)

## Output

```markdown
## RAG System Design: <System Name>

### Pipeline
- **Chunking:** <strategy>, <size>, <overlap>
- **Embedding:** <model>, <dimensions>
- **Vector DB:** <database>, <index type>
- **Retrieval:** <strategy>, top-K=<N>
- **Reranking:** <model or none>

### Evaluation Targets
| Metric | Target |
|--------|--------|
| Faithfulness | >X% |
| Context Relevance | >X |
| Answer Relevance | >X |

### Cost Estimate
- Embedding cost: ~$X per 1K docs
- Storage: ~$X/month for <N> vectors
- Query cost: ~$X per 1K queries
```
