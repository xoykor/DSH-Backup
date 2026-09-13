---
name: pdf-utilidades
description: Inspecionar e transformar PDFs locais com extração de texto, separação, junção, reordenação e renderização verificáveis, mantendo o PDF de origem.
---

# Utilidades PDF

Use `scripts/pdf_ops.py` para operações delimitadas em PDF. Os comandos são `inspect`, `extract`, `split`, `merge`, `reorder` e `render`.

Antes de alterar um arquivo, confirme a lista e a ordem de páginas. `reorder` exige uma permutação completa 1-based, como `--pages 3,1,2`; não aceita uma ordem parcial ambígua. `split` grava `page-001.pdf`, `page-002.pdf` e assim por diante. `merge` usa a ordem fornecida em `--inputs`.

Exemplos:

`python scripts/pdf_ops.py inspect --input entrada.pdf`

`python scripts/pdf_ops.py extract --input entrada.pdf --output texto.txt`

`python scripts/pdf_ops.py reorder --input entrada.pdf --output reordenado.pdf --pages 2,1`

`python scripts/pdf_ops.py render --input reordenado.pdf --output-dir render`

O JSON emitido inclui contagem de páginas, classificação textual e caminhos de saída. `inspect` e `extract` distinguem PDFs com texto extraível de PDFs provavelmente escaneados ou vazios. Isso é um diagnóstico, não OCR: OCR só deve ser proposto se um executável externo estiver instalado e autorizado. `render` usa Poppler `pdftoppm`, detectando `PDFTOPPM`, PATH ou o binário bundled conhecido.

Dependências: Python 3 com `pypdf`; `pdftoppm` do Poppler apenas para renderização. O script recusa substituir o arquivo de entrada, inclusive por hardlink, e os resultados devem ser reabertos e renderizados quando a aparência importar. `pypdf` não recalcula nem interpreta conteúdo gráfico.
