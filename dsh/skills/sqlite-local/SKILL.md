---
name: sqlite-local
description: Inspecionar schema e consultar bancos SQLite locais somente leitura com parâmetros, limites de tempo e linhas, exportando JSON ou CSV.
---

# SQLite local

Use `scripts/sqlite_read`, um helper Rust distribuído pelo skill `tool-first`. O helper abre `mode=ro`, desabilita extensões e schema confiável, bloqueia escrita, ATTACH e PRAGMAs fora da introspecção. Nunca copie somente o arquivo principal de um banco ativo como se fosse um snapshot completo: o WAL pode conter dados confirmados.

Inspecione primeiro:

```bash
scripts/sqlite_read --database app.db --mode schema
```

Para consultar, escreva um JSON com SQL e parâmetros separados; não interpole valores recebidos do usuário no SQL:

```json
{"sql":"SELECT id, nome FROM clientes WHERE cidade = :cidade ORDER BY id","params":{"cidade":"Fortaleza"},"max_rows":100,"timeout_seconds":3}
```

```bash
scripts/sqlite_read --database app.db --mode query --spec consulta.json --output clientes.json
```

`params` aceita objeto para parâmetros nomeados ou lista para `?`. `--output` cria um arquivo novo; `.csv` seleciona CSV, ou informe `--output-format json|csv`. Sem saída, o JSON contém `columns` e `rows` como arrays (nomes duplicados não perdem dados). Com saída, stdout traz apenas o resumo. BLOBs viram objetos com base64. CSV representa null como célula vazia e BLOB como JSON textual; prefira JSON quando precisar distinguir tipos.

Confira `returned_rows`, `truncated` e `read_only`. A consulta roda em uma transação de leitura SQLite que considera WAL confirmado; não é fornecido hash enganoso do banco ativo. O relatório `schema` lista SQL de tabelas/índices/views/triggers, podendo conter literais da aplicação: compartilhe somente o necessário.

Limites: 100 linhas/3 segundos por padrão; até 10.000 linhas/30 segundos, 256 colunas, célula até 64 KiB e resultado até 1 MiB. `truncated: true` significa que existem linhas adicionais. O limite de tempo usa progress handler da VM SQLite e espera de lock limitada; não inclui gravação de exportação. SQL de múltiplas instruções é recusado. Código 0 indica sucesso; 2 indica erro e não modifica o banco. Não use para migrações ou manutenção com escrita.
