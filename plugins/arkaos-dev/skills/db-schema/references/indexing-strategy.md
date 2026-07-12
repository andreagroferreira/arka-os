# Database Indexing Strategy — Deep Reference

> Companion to `db-schema/SKILL.md`. Index types, ordering rules, anti-patterns, and EXPLAIN interpretation.

## Index Types Comparison

| Type | Engine | Best For | Not For | Supports |
|------|--------|----------|---------|----------|
| **B-tree** | All | Range queries, sorting, equality, LIKE 'prefix%' | Full-text, array containment | `<, <=, =, >=, >, BETWEEN, IN, IS NULL, LIKE 'x%'` |
| **Hash** | PostgreSQL | Exact equality only | Range, sorting, partial match | `=` only |
| **GIN** | PostgreSQL | JSONB containment, arrays, full-text | Single-value equality, range | `@>, ?, ?&, ?|, @@, to_tsvector` |
| **GiST** | PostgreSQL | Geometric, range types, full-text (ranking) | Exact equality at scale | `&&, @>, <@, <<, >>`, nearest-neighbor |
| **BRIN** | PostgreSQL | Physically ordered data (timestamps, sequences) | Random access, updates | `<, <=, =, >=, >` (block-level) |
| **Clustered** | MySQL (InnoDB) | Primary key lookups, range scans | Only one per table | Table data physically ordered by PK |
| **Full-text** | MySQL/PostgreSQL | Natural language search | Exact match, sorting | `MATCH AGAINST` / `@@` |

## B-tree: The Default Workhorse

### When B-tree Wins
- WHERE with `=, <, >, <=, >=, BETWEEN, IN, IS NULL`
- ORDER BY (avoids sort operation)
- LIKE with fixed prefix (`LIKE 'abc%'`)
- GROUP BY on indexed columns

### When B-tree Loses
- LIKE with leading wildcard (`LIKE '%abc'`) -- cannot use index
- Array containment (`@>`) -- use GIN
- JSON path queries -- use GIN on JSONB
- Full-text search -- use GIN/GiST with tsvector

## Composite Index Ordering Rules

**The Left-Prefix Rule:** A composite index on `(A, B, C)` can serve queries on `(A)`, `(A, B)`, or `(A, B, C)` -- but NOT `(B)`, `(C)`, or `(B, C)`.

### Column Order Decision Tree

```
1. Put equality columns FIRST (WHERE status = 'active')
2. Put range/inequality column NEXT (WHERE created_at > '2024-01-01')
3. Put ORDER BY columns LAST (ORDER BY created_at DESC)
4. Only ONE range column benefits from the index
```

### Worked Example

```sql
-- Query:
SELECT * FROM orders
WHERE org_id = 5 AND status = 'shipped' AND created_at > '2024-01-01'
ORDER BY created_at DESC;

-- Optimal index:
CREATE INDEX idx_orders_lookup ON orders(org_id, status, created_at DESC);
--          equality(1)  equality(2)  range+sort(3)
```

### Common Ordering Mistakes

| Mistake | Why It Fails | Fix |
|---------|-------------|-----|
| Range column before equality | Index scan stops at first range | Equality columns first |
| ORDER BY column before WHERE | Cannot skip to ORDER BY | WHERE columns first |
| Too many columns (>4) | Diminishing returns, write overhead | Profile actual queries |

## Partial Indexes

Create an index on a subset of rows. Smaller index, faster scans.

```sql
-- Only index active records (90% of queries hit active)
CREATE INDEX idx_tasks_active ON tasks(project_id, priority)
WHERE deleted_at IS NULL;

-- Only index unprocessed jobs
CREATE INDEX idx_jobs_pending ON jobs(queue, created_at)
WHERE status = 'pending';
```

### When to Use Partial Indexes

| Scenario | Benefit |
|----------|---------|
| Soft-deleted tables (query active only) | Index is 10-50% smaller |
| Status columns (query one status predominantly) | Skip irrelevant rows |
| Boolean flags (query TRUE only, small % of table) | Dramatic size reduction |
| Multi-tenant (one tenant is 80% of queries) | Focused index for hot tenant |

## Covering Indexes (Index-Only Scans)

Include all columns a query needs so the database never touches the table.

```sql
-- PostgreSQL: INCLUDE clause
CREATE INDEX idx_orders_covering ON orders(customer_id, status)
INCLUDE (total, created_at);

-- MySQL: all needed columns in the index
CREATE INDEX idx_orders_covering ON orders(customer_id, status, total, created_at);
```

### Covering Index Checklist

- [ ] Query SELECT list is fully covered by index
- [ ] WHERE clause columns are in the index key
- [ ] ORDER BY columns are in the index key
- [ ] INCLUDE columns are for SELECT only (not filterable)

## When NOT to Index

| Situation | Why |
|-----------|-----|
| Table has < 1,000 rows | Full scan is faster than index lookup |
| Column with < 5 distinct values on large table | Low selectivity, planner ignores index |
| Write-heavy table with rare reads | Index maintenance cost > read benefit |
| Columns only used in SELECT (not WHERE/ORDER) | Index does not help (unless covering) |
| Duplicate of existing composite prefix | `(A, B)` already covers `(A)` queries |
| Expression not matching index | `WHERE LOWER(email)` does not use index on `email` |

### Low Selectivity Exception

If a boolean/status column is in a composite index with a high-selectivity column, it CAN help:
```sql
-- Low selectivity alone (useless): INDEX(is_active)
-- High selectivity in composite (useful): INDEX(org_id, is_active)
```

## EXPLAIN ANALYZE Interpretation

### Key Fields to Check

| Field | Good | Bad | Action |
|-------|------|-----|--------|
| **Seq Scan** | Small tables (<1K rows) | Large tables (>10K rows) | Add index on filter columns |
| **Index Scan** | Expected on filtered queries | N/A | Ideal for selective queries |
| **Index Only Scan** | Best case (no table access) | N/A | Covering index working |
| **Bitmap Heap Scan** | Multiple index conditions | N/A | Normal for OR/multi-index |
| **Sort** | Small result set | `Sort Method: external merge` | Add ORDER BY to index |
| **Hash Join** | Equal-size tables | Huge hash table (memory) | Check join column indexes |
| **Nested Loop** | Small outer, indexed inner | Large outer without index | Add index on inner join column |
| **Rows** (estimated vs actual) | Close match | 10x+ difference | Run ANALYZE, check statistics |

### Reading EXPLAIN Output

```
Execution time breakdown:
- actual time=X..Y    X = time to first row, Y = time to all rows
- rows=N              Actual rows returned by this node
- loops=N             How many times this node executed
- Buffers: shared hit Reads from cache (good)
- Buffers: shared read Reads from disk (slow)
```

### Red Flags in EXPLAIN

| Pattern | Problem | Fix |
|---------|---------|-----|
| `Seq Scan` on table > 10K rows | Missing index | Add index on WHERE columns |
| `Sort Method: external merge Disk` | Sort spills to disk | Increase `work_mem` or add index |
| `Rows Removed by Filter: 99000` (of 100K) | Non-selective scan | Add partial index or composite |
| `actual rows=100000` vs `rows=1` | Stale statistics | `ANALYZE table_name` |
| `Nested Loop` with `Seq Scan` inner | Missing join index | Index inner table's join column |

## Index Maintenance

### Regular Tasks

| Task | Frequency | Command (PostgreSQL) |
|------|-----------|---------------------|
| Check bloat | Weekly | `SELECT * FROM pg_stat_user_indexes WHERE idx_scan = 0` |
| Remove unused indexes | Monthly | Drop indexes with 0 scans over 30+ days |
| Reindex bloated indexes | Quarterly | `REINDEX INDEX CONCURRENTLY idx_name` |
| Update statistics | After bulk loads | `ANALYZE table_name` |
| Check index size vs table | Quarterly | Total index size should be < 2x table size |

### Identifying Unused Indexes

```sql
SELECT schemaname, relname, indexrelname, idx_scan, pg_size_pretty(pg_relation_size(indexrelid))
FROM pg_stat_user_indexes
WHERE idx_scan = 0 AND indexrelid NOT IN (
    SELECT conindid FROM pg_constraint WHERE contype IN ('p', 'u')
)
ORDER BY pg_relation_size(indexrelid) DESC;
```

## MySQL vs PostgreSQL Index Differences

| Feature | PostgreSQL | MySQL (InnoDB) |
|---------|-----------|---------------|
| Covering indexes | INCLUDE clause | All columns in index key |
| Partial indexes | Yes (WHERE clause) | No native support |
| Expression indexes | Yes (`CREATE INDEX ON (LOWER(email))`) | Generated columns + index |
| GIN/GiST | Yes | No |
| BRIN | Yes | No |
| Clustered index | Optional (CLUSTER) | Always on PK (mandatory) |
| Index-only scan | Requires recent VACUUM | Automatic via clustered index |
| Concurrent creation | `CREATE INDEX CONCURRENTLY` | `ALGORITHM=INPLACE` (limited) |
