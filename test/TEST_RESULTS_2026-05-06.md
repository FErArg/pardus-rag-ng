# PardusDB Test Results

## Tests Ejecutados: 2026-05-06

---

## Tests Funcionales (Rust)

| Suite | Resultado |
|-------|-----------|
| `cargo test` | **113 passed** ✅ |

---

## Tests de Seguridad

| Test | Resultado | Notas |
|------|-----------|-------|
| SQL Injection (`' OR '1'='1`) | ✅ Bloqueado | Parser rechaza quotes en payloads |
| SQL Injection (`DROP TABLE`) | ⚠️ funcional | Solo si se usa `execute_sql` raw |
| Path Traversal (`../../../etc/passwd`) | ⚠️ **VULNERABLE** | Intenta crear archivo arbitrario |
| Vector Dimension Enforcement | ✅ Funciona | 384 requerido, 3 dado = rechazado |
| Large Vector Handling | ✅ Rechazado | Vectores > límite rechazados |

### Security Issues Encontradas

1. **Path Traversal**: El binario `pardusdb` acepta paths con `..` y trata de crear archivos en rutas arbitrarias. El input `../../../etc/passwd` causa que intente crear un archivo en `/etc/passwd`.

2. **DROP TABLE funcional**: El comando DROP TABLE existe y funciona. Si un usuario tiene acceso al MCP `execute_sql`, puede ejecutar `DROP TABLE`.

---

## Tests de Rendamiento

| Test | Resultado |
|------|-----------|
| Create/Open DB | ✅ Funciona |
| .tables | ✅ Muestra tablas |
| INSERT with dimension check | ✅ Rechaza vectores de dimensión incorrecta |

---

## MCP Tools (19 detectadas)

```
pardusdb_create_database
pardusdb_open_database
pardusdb_create_table
pardusdb_insert_vector
pardusdb_batch_insert
pardusdb_search_similar
pardusdb_search_text
pardusdb_execute_sql
pardusdb_list_tables
pardusdb_use_table
pardusdb_status
pardusdb_import_text
pardusdb_ingest_chunked
pardusdb_ingest_joplin
pardusdb_ingest_async
pardusdb_ingest_status
pardusdb_health_check
pardusdb_get_schema
pardusdb_import_status
```

---

## Recomendaciones de Seguridad

1. **Path Validation**: Agregar validación de paths en el MCP para prevenir `..` en rutas de archivo
2. **SQL Read-only Mode**: Considerar modo solo-lectura para queries via MCP
3. **Command Whitelist**: Para `execute_sql`, permitir solo SELECT por defecto

---

## Archivos de Test

- `/tmp/test_pardus/security_test.py` — Script de tests de seguridad
- `/tmp/test_pardus/test.pardus` — DB de prueba temporal
