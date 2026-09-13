---
name: dados-tabulares
description: Transformar tabelas locais CSV, TSV e JSON com operações explícitas de limpeza, filtro, deduplicação, seleção e conversão, preservando o arquivo de origem.
---

# Dados tabulares

Use esta skill quando a entrada é um arquivo local CSV, TSV ou JSON e a entrega é outra tabela local. O helper aplica somente as operações declaradas em um arquivo JSON, mantendo strings como strings para preservar Unicode, zeros à esquerda e vazios.

Fluxo:

1. Confirme o caminho da entrada, o formato (ou uma extensão reconhecida), as colunas e cada regra solicitada. Não invente remoções, chaves ou conversões de tipos.
2. Escreva uma especificação JSON com `operations`. As operações disponíveis são `clean` (`trim_strings`, opcionalmente `collapse_whitespace`), `filter` (`where` com `eq`, `ne`, `in`, `contains`, `gt`, `gte`, `lt`, `lte` ou `not_empty`), `dedupe` (`keys` e `keep`), `select` (`columns`) e `rename` (`mapping`).
3. Execute `scripts/table_transform.py --input IN --output OUT --operations OPS.json`. Use `--input-format` e `--output-format` quando a extensão não for suficiente.
4. Leia o JSON de resultado. Ele informa contagens antes/depois, colunas, operações e hashes SHA-256. O script recusa que a saída seja o mesmo caminho da entrada.

O helper trata chaves ausentes como vazias ao produzir uma tabela tabular. JSON de objetos pode ser uma lista ou `{ "rows": [...] }`. A conversão CSV/TSV usa UTF-8 e cabeçalho; tipos numéricos do JSON permanecem numéricos somente quando a saída continua JSON. Para uma regra que altere dados, apresente a especificação e valide amostra e contagens antes de usar a saída em outra tarefa.

Dependência: Python 3 padrão, sem pacotes externos. O arquivo original não é modificado; a pasta de destino pode ser criada pelo helper.
