---
tags:
  - arkaos
  - embeddings
---
# Embedder Setup

Uses fastembed with BAAI bge-small-en-v1.5 model (384 dims).
Graceful degradation: if fastembed unavailable, vector store falls back to keyword matching.

Related: [[Vector Store]], [[KB Architecture]].
