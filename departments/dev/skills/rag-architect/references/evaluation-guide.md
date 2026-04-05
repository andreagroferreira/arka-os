# RAG Evaluation Guide — Deep Reference

> RAGAS framework, ground truth datasets, failure mode diagnosis, and continuous evaluation.

## RAGAS Framework Overview

RAGAS (Retrieval Augmented Generation Assessment) evaluates RAG pipelines across 4 dimensions:

| Metric | What It Measures | Range | Target | Calculation |
|--------|-----------------|-------|--------|-------------|
| **Faithfulness** | Is the answer grounded in retrieved context? | 0-1 | > 0.90 | Claims in answer supported by context / total claims |
| **Answer Relevance** | Does the answer address the question? | 0-1 | > 0.85 | Semantic similarity of answer to question |
| **Context Precision** | Are relevant chunks ranked higher? | 0-1 | > 0.80 | Weighted precision of relevant chunks by rank position |
| **Context Recall** | Are all needed facts retrieved? | 0-1 | > 0.75 | Ground truth sentences covered by context / total GT sentences |

## Metric Calculation Details

### Faithfulness

```
1. Extract all factual claims from the generated answer
2. For each claim, check if it is supported by the retrieved context
3. faithfulness = supported_claims / total_claims
```

**Example:**
- Answer: "Python was created by Guido van Rossum in 1991. It is compiled."
- Context mentions Guido and 1991, but Python is interpreted.
- Claims: 3 total, 2 supported -> faithfulness = 0.67

### Answer Relevance

```
1. Generate N hypothetical questions from the answer (reverse QA)
2. Compute cosine similarity between original question and each generated question
3. answer_relevance = mean(similarities)
```

Low score = answer is off-topic or includes excessive irrelevant information.

### Context Precision

```
1. For each retrieved chunk at rank k, determine if it is relevant
2. precision@k = relevant_chunks_in_top_k / k
3. context_precision = mean(precision@k for all k where chunk is relevant)
```

Low score = irrelevant chunks ranked higher than relevant ones. Fix with reranking.

### Context Recall

```
1. Decompose ground truth answer into individual sentences/facts
2. For each fact, check if any retrieved chunk contains supporting information
3. context_recall = facts_with_support / total_facts
```

Low score = retrieval is missing key information. Fix with chunking, embedding, or query expansion.

## Ground Truth Dataset Creation

### Minimum Dataset Size

| Purpose | Minimum Samples | Recommended |
|---------|----------------|-------------|
| Quick sanity check | 20 | 50 |
| Development iteration | 50 | 100 |
| Production baseline | 100 | 250+ |
| Statistical significance | 250+ | 500+ |

### Dataset Schema

```json
{
  "question": "What is the refund policy for digital products?",
  "ground_truth": "Digital products can be refunded within 14 days if not downloaded.",
  "contexts": ["Section 4.2 of Terms: Digital products are eligible for..."],
  "metadata": {
    "category": "policy",
    "difficulty": "easy",
    "source_doc": "terms-of-service-v3.pdf"
  }
}
```

### Creation Methods

| Method | Quality | Cost | Speed | When to Use |
|--------|---------|------|-------|-------------|
| **Manual expert** | Highest | High | Slow | Production baselines, domain-critical |
| **LLM-generated + human review** | High | Medium | Medium | Development iteration, scaling |
| **LLM-generated (no review)** | Medium | Low | Fast | Quick sanity checks, prototyping |
| **User query logs** | High (real) | Low | Ongoing | Production monitoring, continuous eval |
| **Adversarial** | Critical | Medium | Slow | Edge case coverage, robustness |

### Quality Checklist for Ground Truth

- [ ] Questions are natural (not keyword-stuffed)
- [ ] Ground truth answers are factually verified against source docs
- [ ] Dataset covers all document types and topics proportionally
- [ ] Includes edge cases: multi-hop, no-answer, ambiguous queries
- [ ] No data leakage between eval set and training/fine-tuning data

## Failure Mode Diagnosis

| Symptom | Likely Cause | Metric Impact | Fix |
|---------|-------------|---------------|-----|
| Hallucinated facts | Generator ignores context | Low faithfulness | Lower temperature, add "based on context only" prompt |
| Correct but incomplete | Missing relevant chunks | Low context recall | Increase top-K, use HyDE/multi-query |
| Irrelevant chunks retrieved | Poor embedding match | Low context precision | Better chunking, add reranker, fine-tune embeddings |
| Answer ignores question | Prompt drift or context overload | Low answer relevance | Reduce context window, improve system prompt |
| Good metrics, bad user experience | Dataset does not reflect real queries | All metrics misleading | Rebuild eval set from production query logs |
| Inconsistent results | Non-deterministic generation | High variance | Set temperature=0, fix seed, increase eval samples |

## Evaluation Pipeline Setup

```
1. Create ground truth dataset (50+ samples minimum)
2. Run RAG pipeline on all questions
3. Compute RAGAS metrics
4. Log results with pipeline config (chunk_size, model, top_k, etc.)
5. Compare against baseline
6. Identify worst-performing samples
7. Diagnose using failure mode table
8. Fix and re-evaluate
```

## Beyond RAGAS: Additional Metrics

| Metric | What It Measures | When to Add |
|--------|-----------------|-------------|
| **Latency (p50/p95/p99)** | End-to-end response time | Always |
| **Cost per query** | Embedding + LLM tokens + infra | Production |
| **Answer correctness** | Exact/fuzzy match against ground truth | QA-style systems |
| **Noise robustness** | Performance with irrelevant chunks injected | High-noise corpora |
| **Information density** | Useful tokens in context / total context tokens | Cost optimization |
| **Refusal accuracy** | Correctly refuses unanswerable questions | Safety-critical |

## Continuous Evaluation Checklist

- [ ] Automated eval runs on every pipeline config change
- [ ] Metrics tracked over time with dashboards (not just point-in-time)
- [ ] Production query sampling feeds back into eval dataset
- [ ] Regression alerts: any metric drops > 5% triggers investigation
- [ ] Monthly review of ground truth dataset for staleness
- [ ] A/B testing framework for comparing pipeline variants

## Common Mistakes

| Mistake | Why It Hurts | Fix |
|---------|-------------|-----|
| Evaluating only on "happy path" queries | Misses real-world edge cases | Add adversarial, no-answer, and multi-hop samples |
| Using LLM to judge LLM without ground truth | Circular evaluation, inflated scores | Always include human-verified ground truth |
| Optimizing one metric in isolation | Faithfulness vs relevance tradeoff | Track all 4 RAGAS metrics together |
| Eval dataset too small (<20) | High variance, unreliable conclusions | Minimum 50, target 250+ |
| Never updating eval dataset | Drift from real user queries | Refresh quarterly from production logs |
| Ignoring latency and cost | Great quality but unusable in production | Include SLA-relevant metrics from day one |
