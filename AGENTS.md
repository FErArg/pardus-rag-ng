# AGENTS.md — PardusDB MCP Server

## Tools Available (20 MCP Tools)

| Tool | When to Use |
|------|-------------|
| `create_database` | Crear nuevo archivo .pardus |
| `open_database` | Abrir DB existente antes de otras operaciones |
| `create_table` | Crear tabla con VECTOR(dim) + columnas metadata |
| `insert_vector` | Insertar 1 solo vector |
| `batch_insert` | Insertar múltiples vectors de una vez |
| `search_similar` | Buscar por vector (pre-generado externamente) |
| `search_text` | Buscar por texto (el servidor genera embedding automáticamente) |
| `execute_sql` | SQL raw — SOLO si no hay tool específica (AVANZADO) |
| `list_tables` / `use_table` | Gestionar tabla activa |
| `status` | Verificar conexión actual |
| `import_text` | Importar directorio completo (PDF, DOCX, XLSX, CSV, JSON, MD, TXT) |
| `ingest_chunked` | Ingestar 1 archivo con sentence-aware chunking |
| `ingest_joplin` | Ingestar nota de Joplin (después de joplin_read_note) |
| `ingest_async` | Archivos grandes (50MB+) — evita timeout |
| `ingest_status` | Ver progreso de job async |
| `health_check` | Verificar integridad de tabla |
| `get_schema` | Ver estructura de tabla |
| `get_stats` | **NUEVO** — Ver estadísticas de tokens ahorrados |
| `set_model` | **NUEVO** — Configurar modelo LLM para tracking preciso |
| `reset_stats` | **NUEVO** — Resetear contadores de sesión |

### MCP Defaults

- Embedding dimension: **384** (model: `all-MiniLM-L6-v2`)
- Max file size: **50MB**
- Sentence-transformers: **opcional** — si no está, usa zero vectors

## System Behavior

### Helper vs Binary (importante para user)

```
pardus              → Abre ~/.pardus/pardus-rag.db (crea si no existe)
pardusdb            → REPL: in-memory o busca database.pardus en CWD
pardusdb <path>     → Abre archivo específico
```

### Tmp Directory (ingestión)

**Proceso actual**:
1. Archivo se convierte a `.md` en `./tmp/{uuid}/`
2. Se parsea el `.md` y se ingiere a la DB
3. Si ingreso exitoso → tmp se borra
4. Si hay error → tmp se preserva (path visible en error message)

**Nota**: El tmp se limpia SOLO después de confirmación de DB exitosa.

## SQL Reference

```sql
-- Vectores usan corchetes
INSERT INTO docs (embedding, content) VALUES ([0.1, 0.2, ...], 'texto');

-- Similarity search (resultados ordenados por distancia ascendente)
SELECT * FROM docs WHERE embedding SIMILARITY [0.1, 0.2, ...] LIMIT 10;

-- Crear tabla
CREATE TABLE docs (embedding VECTOR(384), content TEXT, title TEXT);
```

## Common Workflows

### RAG Pipeline Completo

```python
# 1. Abrir/crear DB
open_database(path="/home/user/mi.db")

# 2. Crear tabla (384 dim para MiniLM)
create_table(table="docs", vector_dim=384, metadata_schema={"content": "TEXT", "title": "TEXT"})

# 3. Importar documentos
import_text(dir_path="/home/user/docs", table="docs", recursive=true)

# 4. Buscar por texto (embedding auto-generado)
search_text(query="que documentos hay sobre X", table="docs", k=5)
```

### Ingestar Archivo Grande (evitar timeout)

```python
# 1. Abrir DB
open_database(path="/home/user/mi.db")

# 2. Usar ingest_async (retorna job_id inmediatamente)
ingest_async(file_path="/home/user/docs/informe.pdf", table="docs", chunk_size=500)

# 3. Monitorear progreso
ingest_status(job_id="job_000001")

# 4. Repetir hasta status="completed"
```

### Ingestar Nota de Joplin

```python
# 1. Leer nota de Joplin (usar joplin_read_note tool)
# 2. Ingestar con metadata
ingest_joplin(
    table="notas",
    note_id="notebook_id:nota_id",
    note_title="Mi Nota",
    note_content="contenido completo...",
    note_tags="tag1,tag2"
)
```

## Import File Formats

- **PDF**: pypdf (requiere `pip install pypdf`)
- **DOCX**: python-docx
- **XLSX**: openpyxl
- **XLS**: xlrd
- **CSV, JSON, JSONL, MD, TXT**: parsing nativo

Si falta lib para cierto formato → ese archivo se skippea con warning.

## Limitations & Gotchas

1. **No auth en MCP** — cualquier cliente puede ejecutar cualquier operación (ver plan de seguridad)
2. **Singleton db_client** — sin isolation entre callers/concurrent requests
3. **execute_sql** — pasa SQL raw al backend (usar solo si no hay tool específica)
4. **Zero vectors fallback** — si sentence-transformers no instalado, embeddings son [0,0,...]
5. **Ingest async jobs** — no hay cleanup automático de jobs muy viejos
6. **Tmp paths en errores** — en debug mode se exponen paths internos de tmp

## Troubleshooting

| Problema | Causa probable | Solución |
|---------|---------------|----------|
| "Database not found" | DB no abierta | Usar `open_database` primero |
| "sentence-transformers not installed" | Paquete no instalado | `pip install sentence-transformers` |
| Timeout en import | Archivo muy grande | Usar `ingest_async` |
| Duplicate chunks | Hash ya existe | Normal — skippea automáticamente |
| Wrong vector dim | Dim distinta en query vs tabla | Verificar `vector_dim` en `create_table` y query |

## Token Savings Dashboard

El MCP server rastrea tokens ahorrados al usar RAG. Esto justifica el uso y control de gastos.

### Nuevas Tools

| Tool | Descripción |
|------|-------------|
| `get_stats` | Muestra dashboard de tokens (session + total) |
| `set_model` | Configura el modelo LLM actual para tracking preciso |
| `reset_stats` | Resetea contadores de sesión |

### Uso

```python
# Ver estadísticas de tokens
get_stats()

# Configurar modelo (importante para cálculos precisos)
set_model(model="gpt-4o")
# o
set_model(model="claude-3-5-sonnet-20241022")
# o
set_model(model="gemini-2.0-flash")

# Resetear contadores de sesión
reset_stats()
```

### Modelos Soportados

Los siguientes providers y modelos están soportados para context window tracking:

| Provider | Modelos | Context Windows |
|----------|---------|-----------------|
| OpenAI | GPT-4o, GPT-4o-mini, GPT-4.1, GPT-5.4/5.5 | 128K - 1.05M tokens |
| Anthropic | Claude 3.5 Sonnet, Claude Opus 4, Claude Haiku | 200K - 1M tokens |
| Google/Gemini | Gemini 2.0/2.5 Flash, Gemini 3 Pro, Gemini Exp | 8K - 2M tokens |
| DeepSeek | DeepSeek Chat, DeepSeek V3, DeepSeek R1 | 65K - 164K tokens |
| MiniMax | MiniMax M2.1, M2.5 | 200K - 1M tokens |
| Qwen/Alibaba | Qwen 3, Qwen 3.5, Qwen Coder | 8K - 1M tokens |
| Z.ai | GLM-4, GLM-5 | 65K - 205K tokens |

### CLI Stats

```bash
# Ver stats desde CLI
pardusdb --stats
```

### Dashboard Web

Abre `mcp/dashboard.html` en un navegador para ver el dashboard visual con auto-refresh.

## Security Notes (para production)

Sin configurar, el MCP server permite:
- Abrir/crear archivos en cualquier path
- Ejecutar SQL arbitrario via `execute_sql`
- No hay autenticación ni autorización

**Para production**: Configurar `PARDUSDB_API_KEY` y `PARDUSDB_ALLOWED_DIRS` (ver plan de seguridad en `planes/seguridad-2026-05-02.md`)
