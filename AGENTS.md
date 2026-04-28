# AGENTS.md

Guide for AI agents working with the PardusDB codebase.

## Project Overview

PardusDB is a single-file embedded vector database in Rust with SQL-like query syntax, HNSW-based vector search, and an MCP server for AI agents. Single-crate (`src/`), no monorepo tooling.

## Key Facts

### Version Bump

Version is spread across 5 files — update **all** when bumping:
- `Cargo.toml` — package version
- `mcp/src/server.py` — `Server("pardusdb-mcp", "...")` at line 1246 (note: currently `0.4.13` vs `Cargo.toml` `0.4.12`)
- `sdk/python/pyproject.toml` — version field
- `sdk/typescript/pardusdb/package.json` — version field
- `setup.sh` + `install.sh` — `VERSION=` variable near top of each

### Build & Test

```bash
cargo build --release
cargo test                                   # all tests
cargo test --lib graph                       # single module
cargo test --test database_test              # integration tests in tests/
cargo run --example simple_rag --release     # example
cargo run --bin benchmark --release          # benchmarks in src/bin/
```

No CI, no pre-commit hooks, no formatter config, no linter config. No `rustfmt.toml` or `clippy.toml`.

### GPU Feature

Optional, behind `--features gpu`. Adds `wgpu` + `bytemuck` + `pollster` deps.

```bash
cargo build --release --features gpu
```

### Python SDK

```bash
pip install -e sdk/python
# lint: ruff, typecheck: mypy (both in pyproject.toml [dev] deps)
cd sdk/python && pip install -e ".[dev]" && ruff check && mypy pardusdb/
```



## Architecture

```
src/main.rs                   # Entrypoint: REPL or run_with_file(stdin)
src/lib.rs                    # Public API — re-exports all modules
src/database.rs               # Database: manages tables in memory, save/load
src/db.rs                     # VectorDB generic struct (low-level, not the main API)
src/table.rs                  # Table: rows + HNSW graph + UNIQUE indexes
src/graph.rs                  # HNSW with robust_prune
src/parser.rs                 # Recursive-descent SQL parser
src/storage.rs                # MARS binary format (mmap-based)
src/distance.rs               # Cosine, DotProduct, Euclidean metrics
src/concurrent.rs             # Arc<RwLock> thread-safe wrapper
src/schema.rs                 # Column, Row, Value, Schema types
src/error.rs                  # MarsError enum (thiserror)
src/prepared.rs               # Prepared statements with ? placeholders
src/node.rs                   # Graph Node + Candidate types
src/gpu.rs                    # WGSL shaders for GPU distance compute
src/shaders/                  # GPU compute shaders (WGSL)

tests/                        # Integration tests (*.rs in tests/)
src/bin/                      # Benchmarks (14 files: benchmark_*.rs, profile*.rs, ollama_test.rs)

mcp/src/server.py             # MCP server (Python, ~1300 lines)
sdk/python/pardusdb/          # Python SDK
sdk/typescript/pardusdb/      # TypeScript SDK
examples/simple_rag.rs        # Rust example
examples/python/              # Python example
```

### MCP Server (Python)

- Runs `pardusdb <path>` as a subprocess, pipes SQL via stdin, reads result from stdout.
- Spawns a new process per operation — no long-lived daemon.
- Tools are prefixed `pardusdb_`. Text search generates embeddings locally via `sentence-transformers` (all-MiniLM-L6-v2).
- File: `mcp/src/server.py` (Python; the `mcp/README.md` references an npm-published version, not the source tree).

## Conventions

- **Rust edition**: 2024. MSRV: 1.85.
- **Error type**: `MarsError` (thiserror). Never `unwrap()` in production paths.
- **RwLock poisoning**: Use `.lock().unwrap_or_else(|e| e.into_inner())` not `.unwrap()`.
- **Table store**: Default distance metric is `Euclidean` (hardcoded in `Table` struct).
- **File format**: MARS binary format (`b"MARS"` magic bytes), mmap-based via `memmap2`.

## SQL Quirks

- Vector syntax is `[0.1, 0.2, ...]` (square brackets, comma-separated floats).
- Similarity search: `WHERE embedding SIMILARITY [vec]` — results sorted by distance ascending.
- Scientific notation supported (e.g., `-4.846e-33`).
- UNIQUE constraints use HashSet for O(1) duplicate detection.
- GROUP BY is O(n) hash aggregation. JOINs use O(n+m) hash join.

## Troubleshooting

| Symptom | Cause/Fix |
|---------|-----------|
| `Vector dimension mismatch` | Table was created with `VECTOR(n)`, all inserts must match `n` |
| `Table not found` | Case-sensitive name, table must exist |
| `Invalid number` in INSERT | Scientific notation — upgrade to 0.4.13+ which handles `e`/`E` |
| Slow inserts | Use batch insert (1000-at-once is 220x faster than individual) |
| MCP server fails silently | Check `proc.returncode` — the binary might return non-zero |
| MCP "binary not found" | Ensure `pardusdb` is in PATH or set `PARDUSDB_PATH` env var |
