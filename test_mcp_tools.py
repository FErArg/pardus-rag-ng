#!/usr/bin/env python3
"""Test script for PardusDB MCP tools."""

import sys
import os
import asyncio
import subprocess

sys.path.insert(0, "/home/ferarg/.pardus/mcp")
from server import (
    handle_create_database,
    handle_create_table,
    handle_import_text,
    handle_execute_sql,
    handle_list_tables,
    handle_search_similar,
    handle_get_schema,
    handle_health_check,
    handle_import_status,
    db_client,
)

DB_PATH = "/home/ferarg/.pardus/test-rag.pardus"
TABLE = "rag_docs"
DOCS_PATH = "/home/ferarg/Git/Git-Svr1/pardus-rag/docs"


def cleanup():
    subprocess.run(["rm", "-f", DB_PATH], check=False)


async def run_tests():
    print("=" * 60)
    print("PARDUSDB MCP TOOLS TEST")
    print("=" * 60)

    # Fase 2.1: Create database
    print("\n[Fase 2.1] Create database")
    result = await handle_create_database({"path": DB_PATH})
    print(f"  {result['content'][0]['text'][:100]}")
    print(f"  db_path set: {db_client.db_path}")

    # Fase 2.2: Create table
    print("\n[Fase 2.2] Create table 'rag_docs'")
    result = await handle_create_table({"name": TABLE, "vector_dim": 384})
    print(f"  {result['content'][0]['text'][:120]}")

    # Fase 2.3: List tables
    print("\n[Fase 2.3] List tables")
    result = await handle_list_tables()
    text = result['content'][0]['text']
    for line in text.split('\n'):
        if 'Table' in line or 'rag_docs' in line or 'rows' in line.lower():
            print(f"  {line.strip()}")

    # Fase 2.4: Import .md files
    print(f"\n[Fase 2.4] Import .md files from {DOCS_PATH}")
    result = await handle_import_text({
        "dir_path": DOCS_PATH,
        "table": TABLE,
        "file_patterns": [".md"],
        "vector_dim": 384,
    })
    print(f"  isError={result.get('isError', False)}")
    for line in result['content'][0]['text'].split('\n'):
        if line.strip():
            print(f"  {line.strip()}")

    # Fase 2.5: Verify import - use simple SELECT (parser doesn't support LENGTH() or AS)
    print("\n[Fase 2.5] Verify import (.md data)")
    result = await handle_execute_sql({
        "sql": f"SELECT filename, chunk_index, content FROM {TABLE};"
    })
    output = result['content'][0]['text']
    # Show data rows
    for line in output.split('\n'):
        if 'values=' in line.lower() or 'id=' in line.lower():
            print(f"  {line.strip()[:120]}")

    # Fase 2.6: Import .pdf files
    print(f"\n[Fase 2.6] Import .pdf files from {DOCS_PATH}")
    result = await handle_import_text({
        "dir_path": DOCS_PATH,
        "table": TABLE,
        "file_patterns": [".pdf"],
        "vector_dim": 384,
    })
    print(f"  isError={result.get('isError', False)}")
    for line in result['content'][0]['text'].split('\n'):
        if line.strip():
            print(f"  {line.strip()}")

    # Fase 2.7: Count total rows
    print("\n[Fase 2.7] Count total rows")
    result = await handle_execute_sql({"sql": f"SELECT COUNT(*) FROM {TABLE};"})
    for line in result['content'][0]['text'].split('\n'):
        if 'count' in line.lower() or 'integer' in line.lower() or 'id=' in line.lower():
            print(f"  {line.strip()}")

    # Fase 2.8: Import status
    print("\n[Fase 2.8] Import status")
    result = await handle_import_status({"table": TABLE})
    for line in result['content'][0]['text'].split('\n')[:10]:
        if line.strip():
            print(f"  {line.strip()}")

    print("\n" + "=" * 60)
    print("FASE 2 COMPLETADA")
    print("=" * 60)

    # Phase 3: Search
    print("\n" + "=" * 60)
    print("FASE 3: Busqueda semantica")
    print("=" * 60)

    # Fase 3.1: Get a sample embedding
    print("\n[Fase 3.1] Get sample vector for search")
    result = await handle_execute_sql({
        "sql": f"SELECT embedding FROM {TABLE} WHERE chunk_index = 1 LIMIT 1;"
    })
    output = result['content'][0]['text']
    print(f"  Output (first 200 chars):\n{output[:200]}")
    # Extract embedding vector from output
    import re
    emb_match = re.search(r'\[([\d., ]+)\]', output)
    if emb_match:
        vec_str = emb_match.group(1).replace(' ', '')
        vec = [float(x) for x in vec_str.split(',') if x][:10]
        print(f"  Sample vector (first 10 dims): {vec}")
        vec_full = [float(x) for x in vec_str.split(',') if x]
        print(f"\n[Fase 3.2] Search similar vectors (k=3)")
        result = await handle_search_similar({
            "table": TABLE,
            "query_vector": vec_full,
            "k": 3,
        })
        for line in result['content'][0]['text'].split('\n'):
            if line.strip():
                print(f"  {line.strip()[:120]}")

    print("\n" + "=" * 60)
    print("FASE 3 COMPLETADA")
    print("=" * 60)

    # Phase 4: Persistence
    print("\n" + "=" * 60)
    print("FASE 4: Persistencia")
    print("=" * 60)
    
    print("\n[Fase 4.1] Verify persistence - close and reopen DB")
    result = await handle_create_database({"path": DB_PATH})
    print(f"  {result['content'][0]['text'][:80]}")
    
    print("\n[Fase 4.2] List tables after reopen")
    result = await handle_list_tables()
    for line in result['content'][0]['text'].split('\n'):
        if 'Table' in line or 'rag_docs' in line or 'rows' in line.lower():
            print(f"  {line.strip()}")

    print("\n[Fase 4.3] Count rows after reopen")
    result = await handle_execute_sql({"sql": f"SELECT COUNT(*) FROM {TABLE};"})
    for line in result['content'][0]['text'].split('\n'):
        if 'count' in line.lower() or 'integer' in line.lower() or 'id=' in line.lower():
            print(f"  {line.strip()}")

    print("\n[Fase 4.4] Get schema")
    result = await handle_get_schema({"table": TABLE})
    for line in result['content'][0]['text'].split('\n')[:8]:
        if line.strip():
            print(f"  {line.strip()}")

    print("\n" + "=" * 60)
    print("FASE 4 COMPLETADA")
    print("=" * 60)

    # Phase 5: Health check
    print("\n" + "=" * 60)
    print("FASE 5: Health Check")
    print("=" * 60)

    print("\n[Fase 5.1] Health check (full)")
    result = await handle_health_check({})
    for line in result['content'][0]['text'].split('\n')[:20]:
        if line.strip():
            print(f"  {line.strip()}")

    print("\n" + "=" * 60)
    print("TODAS LAS FASES COMPLETADAS")
    print("=" * 60)


if __name__ == "__main__":
    cleanup()
    asyncio.run(run_tests())
