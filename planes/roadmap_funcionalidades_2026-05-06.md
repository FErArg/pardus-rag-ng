# PardusDB - Roadmap de Funcionalidades Futuras

**Fecha:** 2026-05-06
**Versión actual:** 0.4.24

---

## Core Database

| Feature | Prioridad | Descripción | Complejidad |
|---------|-----------|-------------|-------------|
| Concurrent writes | 🔴 Alta | Múltiples writers simultáneos | Alta |
| Full-text search (FTS5) | 🔴 Alta | Búsqueda por texto completo en SQL | Alta |
| JOINs entre tablas | 🔴 Alta | Soporte para consultas con joins | Alta |
| Backup/Restore | 🔴 Alta | Exportar/importar DB completa | Media |
| Aggregate functions | 🟡 Media | COUNT, SUM, AVG, GROUP BY | Media |

---

## MCP Server

| Feature | Prioridad | Descripción | Complejidad |
|---------|-----------|-------------|-------------|
| Built-in embeddings | 🔴 Alta | Generar vectors sin herramienta externa | Alta |
| Hybrid search | 🔴 Alta | Vector + keyword search combinado | Alta |
| Streaming responses | 🟡 Media | Resultados grandes en streaming | Media |
| API key auth | 🟡 Media | Autenticación para MCP server | Baja |
| Multiple DB pooling | 🟡 Media | Soporte multi-database simultáneas | Media |

---

## Operations

| Feature | Prioridad | Descripción | Complejidad |
|---------|-----------|-------------|-------------|
| Docker image | 🔴 Alta | Contenedor listo para usar | Baja |
| Web dashboard | 🟡 Media | UI para gestión de DB | Alta |
| Prometheus metrics | 🟡 Media | Observabilidad (query latency, etc.) | Baja |
| Connection pooling | 🟡 Media | HTTP mode con pool | Media |

---

## Performance

| Feature | Prioridad | Descripción | Complejidad |
|---------|-----------|-------------|-------------|
| HNSW/IVF index | 🔴 Alta | Índices para búsquedas rápidas en million-scale | Alta |
| Query cache | 🟡 Media | Cachear resultados frecuentes | Media |
| Batch optimizations | 🟡 Media | Bulk inserts más rápidos | Baja |
| GPU acceleration | 🟢 Baja | Soporte CUDA para vectors | Muy Alta |

---

## Security

| Feature | Prioridad | Descripción | Complejidad |
|---------|-----------|-------------|-------------|
| Encryption at rest | 🟡 Media | Encriptar archivos DB | Alta |
| Rate limiting | 🟢 Baja | Limitar requests por cliente | Baja |
| Input validation | 🟡 Media | Sanitización más robusta | Media |

---

## Notas

- 🔴 Alta = Crítico para production
- 🟡 Media = Important but not critical
- 🟢 Baja = Nice to have

### Dependencias externas sugeridas

- **Embeddings:** sentence-transformers, openai embeddings, o local models (llama.cpp)
- **FTS5:** SQLite FTS5 extension
- **HNSW:** crate `hnsw_rs` o similar
- **Docker:** `crates.io/docker` o Dockerfile manual

### Roadmap suggested order

1. **Docker image** - Prioridad alta por facilidad de deployment
2. **Built-in embeddings** - Elimina dependencia externa
3. **HNSW/IVF index** - Performance crítica para scale
4. **Backup/Restore** - Data safety
5. **Full-text search** - Feature parity con SQLite
6. **Web dashboard** - UX improvement
