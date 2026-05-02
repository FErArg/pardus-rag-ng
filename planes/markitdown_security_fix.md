# Plan de Seguridad - MarkItDown Integration

## Problemas Identificados

| ID | Gravedad | Problema | Afecta | Estado |
|----|----------|----------|--------|--------|
| P1 | ⚠️ MEDIA | Sin timeout en `convert_to_markdown()` — posible hang | Linux/macOS | Pendiente |
| P2 | ⚠️ BAJA | `sql_escape` no maneja todos los edge cases | Ambos OS | Pendiente |

---

## P1: Timeout en Conversión MarkItDown

### Descripción
La función `convert_to_markdown()` (línea 244-279) no tiene timeout. Si MarkItDown se cuelga en un archivo corrupto o muy grande, el proceso completo se cuelga sin posibilidad de recovery.

### Impacto
- Denial of service si un archivo malicioso causa hang
- No hay forma de cancelar operaciones lentas

### Solución Propuesta

Usar `signal.SIGALRM` para Unix (Linux/macOS):

```python
import signal
import functools

def with_timeout(seconds: int, default=None):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            def handler(signum, frame):
                raise TimeoutError(f"{func.__name__} timed out after {seconds}s")

            old_handler = signal.signal(signal.SIGALRM, handler)
            signal.alarm(seconds)
            try:
                return func(*args, **kwargs)
            finally:
                signal.alarm(0)
                signal.signal(signal.SIGALRM, old_handler)
        return wrapper
    return decorator

@with_timeout(60, default=("", "", [{"content": "", "page": 0}]))
def convert_to_markdown(path: str) -> tuple[str, str, list[dict[str, Any]]]:
    ...
```

### Archivos a Modificar
- `mcp/src/server.py`

### Implementación
1. Agregar decorator `with_timeout` antes de `convert_to_markdown`
2. Aplicar `@with_timeout(60)` a la función
3. En caso de timeout, el archivo se marca como error y se continúa con el siguiente

---

## P2: Mejora sql_escape

### Descripción
`sql_escape()` actual:
```python
def sql_escape(s: str) -> str:
    return s.replace("\\", "\\\\").replace("'", "''").replace("\n", "\\n").replace("\r", "\\r").replace("\t", "\\t")
```

No escapa:
- Comillas dobles (`"`)
- Backticks (`` ` ``)
- Porcentaje (`%`) — relevante para LIKE patterns
- Guion bajo (`_`) — relevante para LIKE patterns

### Impacto
- Potential SQL issues si contenido de archivos tiene caracteres especiales
- No es injection directo porque no es user input, pero el contenido de archivos convertidos podría causar errores de parsing

### Solución Propuesta (Opcional - Baja Prioridad)

Mejorar `sql_escape`:

```python
def sql_escape(s: str) -> str:
    if s is None:
        return ''
    return (s
        .replace("\\", "\\\\")
        .replace("'", "''")
        .replace("\0", "\\0")
        .replace("\n", "\\n")
        .replace("\r", "\\r")
        .replace("\t", "\\t")
        .replace('"', '\\"')
        .replace("`", "\\`"))
```

### Archivos a Modificar
- `mcp/src/server.py` (línea 112-113)

---

## Orden de Implementación Sugerido

1. **P1 (Urgente)**: Agregar timeout a `convert_to_markdown`
2. **P2 (Opcional)**: Mejorar `sql_escape`

---

## Verificación Post-Fix

```bash
# Test timeout con archivo artificialmente lento (mock)
# Test SQL escape con edge cases: "test'", "test\nbreak", "test`query`"
```

---

## Notas Adicionales

- El fix de timeout usa `signal.SIGALRM` que **no funciona en Windows**
- Para Windows habría que usar Thread-based timeout approach
- Dado que el MCP server es principalmente para Linux/macOS (servidores), esto es aceptable por ahora