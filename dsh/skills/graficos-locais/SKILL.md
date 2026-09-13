---
name: graficos-locais
description: Gerar gráficos PNG, SVG ou PDF a partir de uma tabela local validada, com especificação, rótulos, unidades e proveniência preservadas.
---

# Gráficos locais

Use esta skill quando o usuário pedir um gráfico de uma tabela local. Primeiro confirme colunas, unidades, população e escala. Não adivinhe se uma coluna é medida, categoria, data ou percentual.

Crie uma especificação JSON com `kind` (`line`, `bar` ou `scatter`), `x`, `y` (uma coluna ou lista), e, quando necessário, `title`, `xlabel`, `ylabel`, `labels`, `marker`, `legend` e `xrotation`. Execute:

`python scripts/plot_table.py --input dados.csv --spec grafico.json --output grafico.png --provenance-dir evidencia-grafico`

O helper valida que x existe e que cada y é numérico e completo. Ele usa Matplotlib em backend sem interface, salva a figura e grava em `provenance-dir` uma cópia da tabela de origem, a especificação e `provenance.json` com hashes, colunas e contagem de linhas. A saída é determinística quanto à especificação e aos dados, mas detalhes de fonte podem variar entre instalações.

Dependência: Python 3 com `matplotlib`. Use um runtime que realmente contenha o pacote e configure `MPLCONFIGDIR` para uma pasta gravável quando necessário. Verifique visualmente PNG/SVG/PDF antes de entregar, conferindo rótulos, unidades, limites, legenda e cortes.
