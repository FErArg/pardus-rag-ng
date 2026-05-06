# Plan de Acción: Corrección de Vulnerabilidades de Seguridad — pardus-rag

**Fecha**: 2026-05-02
**Versión**: 0.4.21
**Estado**: Pendiente de implementación

---

## Resumen Ejecutivo

El proyecto tiene **vulnerabilidades significativas** que deben abordarse. La más crítica es la **ausencia total de autenticación y autorización** — cualquier cliente MCP puede ejecutar cualquier operación.

### Clasificación de Hallazgos

| Severidad | Cantidad | Descripción |
|-----------|----------|-------------|
| CRITICAL | 5 | Sin auth, sin authorization, execute_sql raw, path traversal en ingest_async, singleton sin aislamiento |
| HIGH | 4 | Path traversal en open/create database, symlink check incompleto, tmp path expuesto, deserialización bincode insegura |
| MEDIUM | 8 | Inconsistencia symlink checks, exception messages expuestos, tmp leak en thread, jobs unbounded, relative TMP_DIR, unsafe Rust |
| LOW | 2 | Sin k bound en similarity search, metadata_schema column injection |

---

## FASE 1: Críticas — Authentication & Authorization

### 1.1 Authentication Layer (CRITICAL)

**Ubicación**: `mcp/src/server.py`

**Implementación**:
```python
import os

API_KEY = os.environ.get("PARDUSDB_API_KEY", "")

def _require_auth(args: dict) -> bool:
    """Check API key from args or environment."""
    provided = args.get("_api_key") or os.environ.get("PARDUSDB_API_KEY_HEADER", "")
    return API_KEY == "" or provided == API_KEY
```

**Aplicar** a todos los MCP handlers. Retornar `{"isError": True, "content": "Unauthorized"}` si falla.

**Archivo**: `mcp/src/server.py`
**Líneas**: ~20

---

### 1.2 Authorization — Path Restrictions (CRITICAL)

**Ubicación**: `mcp/src/server.py`

**Implementación**:
```python
ALLOWED_BASE_DIRS = os.environ.get("PARDUSDB_ALLOWED_DIRS", "").split(":") or []

def validate_path(path: str, base_dir: str = None) -> tuple[bool, str]:
    """Validate path is within allowed directories."""
    if not ALLOWED_BASE_DIRS and not base_dir:
        return True, ""  # No restrictions configured

    resolved = Path(path).resolve()
    allowed = ALLOWED_BASE_DIRS.copy()
    if base_dir:
        allowed.append(base_dir)

    for base in allowed:
        base_resolved = Path(base).resolve()
        if str(resolved).startswith(str(base_resolved) + os.sep):
            return True, ""

    return False, f"Path outside allowed directories: {path}"
```

**Aplicar a**:
- `handle_open_database` (línea ~574)
- `handle_create_database` (línea ~557)
- `handle_ingest_chunked` (línea ~1000)
- `handle_ingest_async` (línea ~1415)

**Archivo**: `mcp/src/server.py`
**Líneas**: ~30

---

## FASE 2: Path Traversal & Symlink Validation

### 2.1 Unificar validación de path

**Ubicación**: `mcp/src/server.py` — función centralizada

```python
def _validate_file_access(file_path: str, base_dir: str = None) -> tuple[bool, str]:
    """
    Returns (is_valid, error_message).
    Validates:
    - Path exists
    - Resolved path is within allowed base_dir
    - No symlink traversal outside base_dir
    """
    path = Path(file_path)
    if not path.exists():
        return False, f"File not found: {file_path}"

    resolved = path.resolve()

    # Check symlink
    if path.is_symlink():
        return False, f"Symlinks not allowed: {file_path}"

    if base_dir:
        base_resolved = Path(base_dir).resolve()
        if not str(resolved).startswith(str(base_resolved) + os.sep):
            return False, f"Path outside allowed directory: {file_path}"

    return True, ""
```

**Reemplazar checks inconsistentes**:
- `handle_import_text` (línea 824) → usar `_validate_file_access()`
- `handle_ingest_chunked` → agregar validación faltante
- `handle_ingest_async` → agregar validación faltante

**Archivo**: `mcp/src/server.py`
**Líneas**: ~40

---

### 2.2 TOCTOU Mitigation

**Problema**: Window entre `exists()` y `read()` permite symlink swap

**Solución**: Verificar `is_symlink()` + stat.mode antes de leer

```python
def _safe_read_file(path: str) -> tuple[bool, str, bytes]:
    """Read file safely, checking for symlinks and path traversal."""
    import stat as stat_mod

    try:
        p = Path(path)

        # Check symlink first
        if p.is_symlink():
            return False, "Symlinks not allowed", b""

        stat = p.stat()

        # Verify it's a regular file
        if not stat_mod.S_ISREG(stat.st_mode):
            return False, "Not a regular file", b""

        return True, "", p.read_bytes()
    except Exception as e:
        return False, str(e), b""
```

**Archivo**: `mcp/src/server.py`
**Líneas**: ~25

---

## FASE 3: Resource Isolation — db_client Singleton

### 3.1 Aislar estado por request/caller

**Ubicación**: `mcp/src/server.py`

**Implementación** — Thread-local storage:
```python
import threading

_thread_local = threading.local()

def _get_db_client() -> PardusDBClient:
    """Get or create thread-local database client."""
    if not hasattr(_thread_local, 'client'):
        _thread_local.client = PardusDBClient()
    return _thread_local.client

# Reemplazar uso de db_client global
db_client = _get_db_client()  # En contexts donde se necesita
```

**Nota**: Requiere refactor de `PardusDBClient` para ser thread-safe. Si no lo es, usar locking.

**Archivo**: `mcp/src/server.py`
**Líneas**: ~15

---

### 3.2 Jobs Cleanup — TTL-based

**Ubicación**: `server.py:1219` (`_jobs` dict)

```python
import time

_JOB_TTL_SECONDS = int(os.environ.get("PARDUSDB_JOB_TTL", 3600))

def _cleanup_stale_jobs():
    """Remove completed/failed jobs older than TTL."""
    now = time.time()
    stale = [
        jid for jid, job in _jobs.items()
        if now - job["started_at"] > _JOB_TTL_SECONDS
        and job["status"] in ("completed", "failed")
    ]
    for jid in stale:
        del _jobs[jid]

# Llamar al inicio de cada handler que access _jobs
_cleanup_stale_jobs()
```

**Archivo**: `mcp/src/server.py`
**Líneas**: ~20

---

## FASE 4: Information Disclosure

### 4.1 Remover tmp path de errores en producción

**Ubicación**: `server.py` — múltiples líneas

```python
DEBUG = os.environ.get("PARDUSDB_DEBUG", "false").lower() == "true"

# En cada lugar que hace:
# error_msg += f"\n[debug] tmp preserved at: {tmp_uuid_dir}"
# Cambiar a:
if DEBUG:
    error_msg += f"\n[debug] tmp preserved at: {tmp_uuid_dir}"
```

**Líneas a modificar**:
- `server.py:1026`
- `server.py:1081`
- `server.py:1113`
- `server.py:1285`
- `server.py:1294`
- `server.py:1309`
- `server.py:1347`
- `server.py:1362`
- `server.py:1401`

**Archivo**: `mcp/src/server.py`
**Líneas**: ~20

---

### 4.2 Sanitizar exception messages

**Ubicación**: Todos los handlers

**Crear helper**:
```python
def _safe_error(e: Exception, include_debug: bool = False) -> str:
    """Return sanitized error message."""
    if include_debug and DEBUG:
        return f"Error: {type(e).__name__}: {e}"
    return "Error: An internal error occurred. Check logs for details."
```

**Aplicar a** todos los `except Exception as e:` que hacen `return ... f"Error: {e}"`

**Archivo**: `mcp/src/server.py`
**Líneas**: ~15 + ~50 para refactorizar todos los handlers

---

## FASE 5: Rust Backend Hardening

### 5.1 File Permissions (0o600)

**Ubicación**: `src/database.rs:141-145`

**Agregar post-creación**:
```rust
use std::fs::Permissions;
use std::os::unix::fs::PermissionsExt;

let file = OpenOptions::new()
    .write(true)
    .create(true)
    .truncate(true)
    .open(path)?;

#[cfg(unix)]
file.set_permissions(Permissions::from_mode(0o600))?;

Ok(db)
```

**Archivo**: `src/database.rs`
**Líneas**: ~10

---

### 5.2 bincode HMAC Integrity

**Ubicación**: `src/database.rs:103, 166`

**Agregar HMAC verification**:
```rust
use hmac::{Hmac, Mac};
use sha2::Sha256;

type HmacSha256 = Hmac<Sha256>;

const SECRET_KEY: &[u8] = b"your-secret-key-change-in-production";

fn verify_data(data: &[u8], expected_hmac: &[u8]) -> bool {
    let mut mac = HmacSha256::new_from_slice(SECRET_KEY).expect("HMAC can take key of any size");
    mac.update(data);
    mac.verify_slice(expected_hmac).is_ok()
}

// En TableData::load o donde se deserializa:
// Separar los últimos 32 bytes como HMAC
// Verificar antes de bincode::deserialize
```

**Nota**: Requiere agregar `hmac` y `sha2` crates a Cargo.toml

**Archivo**: `src/database.rs`, `Cargo.toml`
**Líneas**: ~40 + deps

---

### 5.3 Bounds Checking en distance.rs

**Ubicación**: `src/distance.rs:84-127`

**Agregar assertion**:
```rust
// Antes del loop unsafe
debug_assert!(a.len() >= unrolled_len && b.len() >= unrolled_len,
    "Vector length {} less than unrolled length {}", a.len(), unrolled_len);
```

**Archivo**: `src/distance.rs`
**Líneas**: ~5

---

## FASE 6: Configuración de Producción

### 6.1 Environment Variables

**Nuevas variables**:

| Variable | Default | Descripción |
|----------|---------|-------------|
| `PARDUSDB_API_KEY` | (none) | API key para autenticación. Requerido en producción |
| `PARDUSDB_DEBUG` | `false` | Mostrar info de debug en errores |
| `PARDUSDB_ALLOWED_DIRS` | (empty) | Lista de directorios permitidos (colon-separated) |
| `PARDUSDB_JOB_TTL` | `3600` | Seconds antes de cleanup de jobs stale |
| `PARDUSDB_MAX_UPLOAD_MB` | `50` | Max file size para ingest |

**Archivo**: `.env.example`
**Líneas**: ~15

---

### 6.2 Defaults Seguros

```python
# server.py - defaults should be restrictive
API_KEY = os.environ.get("PARDUSDB_API_KEY", "")  # No default - must be set
DEBUG = os.environ.get("PARDUSDB_DEBUG", "false").lower() == "true"
ALLOWED_BASE_DIRS = [
    p for p in os.environ.get("PARDUSDB_ALLOWED_DIRS", "").split(":")
    if p
]
JOB_TTL = int(os.environ.get("PARDUSDB_JOB_TTL", "3600"))
MAX_FILE_SIZE_MB = int(os.environ.get("PARDUSDB_MAX_UPLOAD_MB", "50"))
```

---

## Resumen de Cambios por Archivo

| Archivo | Cambios | Líneas estimadas |
|---------|---------|------------------|
| `mcp/src/server.py` | Auth, path validation, tmp cleanup, error sanitization, db isolation | ~250 |
| `src/database.rs` | File permissions 0o600, HMAC verification | ~50 |
| `src/distance.rs` | Bounds assertion | ~5 |
| `Cargo.toml` | Add hmac, sha2 crates | ~3 |
| `.env.example` | New env vars | ~15 |
| `setup.sh` | Generate random API key on install | ~15 |
| `install.sh` | Same | ~15 |

---

## Timeline Sugerido

| Fase | Descripción | Esfuerzo |
|------|-------------|----------|
| 1 | Auth + Authorization | 2-3 días |
| 2 | Path validation unification | 1 día |
| 3 | TOCTOU + tmp fixes | 1 día |
| 4 | db_client isolation | 0.5 día |
| 5 | Error message sanitization | 0.5 día |
| 6 | Rust hardening (permissions, HMAC) | 1-2 días |

**Total estimado**: 6-8 días de desarrollo

---

## Verificación Post-Implementación

1. **Penetration test** de todas las herramientas MCP
2. **Code review** de changes
3. **Load test** para verificar performance no degradada
4. **Documentar** nuevas configs en INSTALL.md / README.md

---

## Checklist de Implementación

### Fase 1: Auth
- [ ] Añadir API_KEY env var y validation
- [ ] Crear decorator/guard `_require_auth`
- [ ] Aplicar a todos los handlers
- [ ] Test: Verify 401 sin API key

### Fase 2: Path Restrictions
- [ ] Crear `validate_path()` function
- [ ] Aplicar a open/create database
- [ ] Aplicar a ingest handlers
- [ ] Test: Verify traversal blocked

### Fase 3: Symlink + TOCTOU
- [ ] Crear `_validate_file_access()`
- [ ] Crear `_safe_read_file()`
- [ ] Reemplazar checks inconsistentes
- [ ] Test: Verify symlinks rejected

### Fase 4: db_client Isolation
- [ ] Implementar thread-local storage
- [ ] Agregar job cleanup TTL
- [ ] Test: Verify no state collision

### Fase 5: Error Sanitization
- [ ] Crear `_safe_error()` helper
- [ ] Add DEBUG flag
- [ ] Sanitizar todos los handlers
- [ ] Test: Verify no internal paths leaked

### Fase 6: Rust Hardening
- [ ] Add 0o600 permissions
- [ ] Add HMAC verification
- [ ] Add bounds assertions
- [ ] Test: Verify file permissions correct

---

## Notas

- **Authentication**: API Key simple vs JWT — Se recomienda API Key para MVP, JWT para producción futura
- **Allowed dirs**: Whitelist más seguro que blacklist para producción
- **Rust hardening**: HMAC requiere cambiar formato de archivo — backward compatibility considerations