---
name: planilhas-locais
description: Criar ou editar arquivos XLSX locais em células, intervalos, abas e tabelas explicitamente definidos, preservando conteúdo fora do alvo e declarando a situação de recálculo.
---

# Planilhas locais

Use esta skill para alterações delimitadas em XLSX (e XLSM quando a preservação de VBA for necessária). Trabalhe com `scripts/xlsx_edit.py` e um JSON de operações. Não reestruture a pasta inteira por conveniência.

Operações suportadas:

- `set_cells`: `{ "cells": [{"sheet":"Dados", "cell":"B2", "value":"texto"}] }`.
- `set_range`: `{ "sheet":"Dados", "range":"B2:C3", "values":[[1,2],[3,4]] }`.
- `add_table`: `{ "sheet":"Dados", "ref":"A1:C5", "name":"TabelaDados", "style":"TableStyleMedium2" }`.
- `create_sheet`: `{ "sheet":"Resumo", "index":0 }` (o índice é opcional).

Use fórmulas conhecidas como strings iniciadas por `=`. Antes da execução, valide nomes de abas, referências e dimensões do intervalo. Execute:

`python scripts/xlsx_edit.py --input entrada.xlsx --output saida.xlsx --operations operacoes.json`

O helper recusa saída igual à entrada, reabre o resultado e compara os valores de células não tocadas, além de informar abas, hashes e células tocadas. O `openpyxl` preserva fórmulas como fórmulas, mas não calcula resultados. O arquivo solicita recálculo na próxima abertura por um motor compatível; não declare valores calculados sem executar tal motor e verificar seus resultados. Macros e recursos avançados podem exigir Excel/LibreOffice para validação adicional.

Dependência: Python 3 com `openpyxl` (a versão bundled do DSH é preferida). O original permanece intacto.
