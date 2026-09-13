---
name: dados-tabulares
description: Transformar tabelas locais CSV, TSV e JSON ou reconciliar duas tabelas por chaves explícitas, identificando duplicatas e divergências sem modificar as origens.
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

## Reconciliação de duas tabelas

Use `scripts/table_reconcile.py` para comparar fontes por uma chave indicada pelo usuário. O transformador acima mantém sua interface; a reconciliação produz relatório JSON separado, sem deduplicar os dados.

```json
{"keys":["id"],"compare_columns":["nome","saldo"],"expected_counts":{"left_rows":100,"right_rows":100},"max_examples":100}
```

```bash
python3 scripts/table_reconcile.py --left antes.csv --right depois.csv --spec comparacao.json --output divergencias.json
```

`keys` é obrigatório e pode ser composto. `compare_columns` é opcional; por padrão compara a união das colunas, exceto chaves. Não há coerção: `"001"`, `1` e `1.0` são distintos; célula JSON ausente também difere de null. Chaves vazias/ausentes ou não escalares são recusadas. Use formatos equivalentes ou transformação explícita prévia para alinhar tipos entre CSV e JSON.

Duplicatas são mantidas como grupos. Se qualquer lado de uma chave compartilhada tiver mais de uma linha, o grupo fica `ambiguous`, sem escolher uma linha arbitrária. `only_left_rows` e `only_right_rows` incluem todas as linhas das chaves exclusivas. A contagem de cada lado deve ser igual a exclusivas + ambíguas + pares iguais + pares diferentes. `counts_validated` verifica essa identidade; `expected_counts` pode conferir qualquer contador do relatório.

As contagens cobrem todas as linhas. Exemplos são limitados globalmente por `max_examples` (1–1.000; padrão 100), com até 20 números de linha por grupo; `examples_truncated` avisa quando faltam exemplos. Números começam em 1 na primeira linha de dados, sem cabeçalho CSV. Entradas até 32 MiB e 100.000 linhas cada; relatório até 8 MiB. A saída deve ser nova, em pasta existente. Código 0: relatório válido; 3: contagem esperada divergente (relatório ainda gravado); 2: erro. Nenhuma diferença é corrigida automaticamente.
