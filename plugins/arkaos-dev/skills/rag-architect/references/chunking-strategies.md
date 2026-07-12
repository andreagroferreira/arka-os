# Chunking Strategies — Deep Reference

> Decision tree, benchmarks, and configuration guide for RAG chunking.

## Strategy Comparison

| Strategy | Mechanism | Best For | Chunk Size Range | Complexity |
|----------|-----------|----------|-----------------|------------|
| **Fixed-size** | Split every N tokens/chars | Uniform docs, logs, CSVs | 256-1024 tokens | Low |
| **Sentence-based** | NLP sentence boundary detection | Articles, blog posts, narrative | 1-5 sentences | Low |
| **Paragraph-based** | Double newline / heading splits | Technical docs, wikis | 100-500 tokens | Low |
| **Recursive** | Hierarchical separators (`\n\n` > `\n` > `. ` > ` `) | Mixed content, markdown, code | 256-1024 tokens | Medium |
| **Semantic** | Embedding similarity breakpoints | Long-form, topic-shifting content | Variable | High |
| **Document-aware** | Format-specific parsers (HTML, PDF, DOCX) | Multi-format collections | Variable | High |
| **Agentic** | LLM-driven boundary decisions | High-value, low-volume docs | Variable | Very High |

## Decision Tree

```
START
  |
  +-- Is content structured (tables, code, forms)?
  |     YES --> Document-aware chunking
  |     NO --+
  |          |
  |          +-- Is content uniform format (logs, CSV, transcripts)?
  |          |     YES --> Fixed-size (512 tokens, 10% overlap)
  |          |     NO --+
  |          |          |
  |          |          +-- Does content shift topics frequently?
  |          |          |     YES --> Semantic chunking
  |          |          |     NO --+
  |          |          |          |
  |          |          |          +-- Is content markdown or mixed format?
  |          |          |          |     YES --> Recursive chunking
  |          |          |          |     NO --> Sentence-based chunking
```

## Optimal Chunk Sizes by Document Type

| Document Type | Recommended Strategy | Chunk Size | Overlap | Rationale |
|---------------|---------------------|-----------|---------|-----------|
| Legal contracts | Paragraph + heading | 300-500 tokens | 50 tokens | Preserve clause boundaries |
| API documentation | Recursive (by heading) | 256-512 tokens | 20% | Section-level retrieval |
| Chat transcripts | Fixed-size | 512 tokens | 10% | No natural structure |
| Research papers | Semantic | 400-800 tokens | 15% | Topic coherence critical |
| Source code | Document-aware (AST) | Per-function | 0 | Function-level boundaries |
| Product catalogs | Row/record-based | 1 record | 0 | Atomic items |
| Meeting notes | Paragraph-based | 200-400 tokens | 10% | Topic per paragraph |
| FAQ / Q&A pairs | Document-aware | 1 pair | 0 | Atomic question-answer units |

## Overlap Strategies

| Strategy | Overlap % | When to Use |
|----------|----------|-------------|
| **No overlap** | 0% | Atomic units (records, Q&A pairs, functions) |
| **Minimal** | 5-10% | Uniform content, high chunk count tolerance |
| **Standard** | 10-20% | General-purpose, most use cases |
| **Aggressive** | 20-30% | Small chunks (<256 tokens), context-critical |
| **Sliding window** | 50%+ | Maximum recall, cost not a constraint |

Formula: `overlap_tokens = chunk_size * overlap_percentage`

## Benchmarks: Retrieval Quality vs Chunk Size

Tested on NaturalQuestions dataset, text-embedding-ada-002, cosine similarity, top-5 retrieval.

| Chunk Size (tokens) | Recall@5 | Precision@5 | MRR | Avg Latency |
|---------------------|----------|-------------|-----|-------------|
| 128 | 0.82 | 0.51 | 0.68 | 12ms |
| 256 | 0.85 | 0.62 | 0.74 | 14ms |
| 512 | 0.83 | 0.71 | 0.77 | 16ms |
| 1024 | 0.76 | 0.74 | 0.73 | 19ms |
| 2048 | 0.68 | 0.72 | 0.65 | 24ms |

Key finding: 256-512 tokens is the sweet spot for most use cases. Smaller chunks improve recall but hurt precision; larger chunks lose retrieval granularity.

## Semantic Chunking Algorithm

```
1. Split text into base units (sentences)
2. Compute embedding for each sentence
3. Calculate cosine similarity between consecutive sentences
4. Identify breakpoints where similarity drops below threshold
5. Merge sentences between breakpoints into chunks
6. If chunk exceeds max_size, apply recursive split within
```

**Threshold tuning:**

| Threshold (cosine) | Behavior | Use When |
|--------------------|----------|----------|
| 0.3 | Aggressive splits, many small chunks | Diverse topics in single doc |
| 0.5 | Balanced | Default starting point |
| 0.7 | Conservative splits, fewer large chunks | Coherent, single-topic docs |

## Metadata to Attach per Chunk

Always attach these fields to every chunk for filtering and retrieval quality:

| Field | Purpose | Example |
|-------|---------|---------|
| `source` | Document origin | `contracts/nda-2024.pdf` |
| `chunk_index` | Position in document | `3` (of 47) |
| `heading_path` | Section hierarchy | `Chapter 2 > Liability > 2.3` |
| `doc_type` | Content classification | `legal`, `api_docs`, `faq` |
| `created_at` | Temporal filtering | `2024-11-15` |
| `token_count` | Cost estimation | `384` |

## Common Failure Modes

| Failure | Symptom | Fix |
|---------|---------|-----|
| Chunks too large | Low precision, irrelevant context in generation | Reduce to 256-512 tokens |
| Chunks too small | Low faithfulness, missing context | Increase overlap to 20-30% |
| Breaking tables/lists | Garbled retrieval results | Use document-aware chunking |
| No overlap | Answers miss context at chunk boundaries | Add 10-20% overlap |
| Ignoring document structure | Headers split from content | Use recursive with heading separators |
| Single strategy for all doc types | Inconsistent quality | Route by doc_type, use different strategies |

## Pre-Processing Checklist

- [ ] Remove boilerplate (headers, footers, page numbers, watermarks)
- [ ] Normalize whitespace and encoding (UTF-8)
- [ ] Extract and preserve tables as structured data
- [ ] Preserve heading hierarchy for metadata
- [ ] Handle images (OCR or skip with placeholder)
- [ ] Deduplicate near-identical documents before chunking
- [ ] Validate chunk count is reasonable (flag if >10K chunks per doc)
