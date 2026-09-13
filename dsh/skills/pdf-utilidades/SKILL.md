---
name: pdf-utilidades
description: Inspecionar e transformar PDFs locais, extrair texto e executar OCR de páginas escaneadas ou imagens, com resultados verificáveis e preservação dos originais.
---

# Utilidades PDF

Use `scripts/pdf_ops.py` para operações delimitadas em PDF. Os comandos são `inspect`, `extract`, `split`, `merge`, `reorder` e `render`.

Antes de alterar um arquivo, confirme a lista e a ordem de páginas. `reorder` exige uma permutação completa 1-based, como `--pages 3,1,2`; não aceita uma ordem parcial ambígua. `split` grava `page-001.pdf`, `page-002.pdf` e assim por diante. `merge` usa a ordem fornecida em `--inputs`.

Exemplos:

`python scripts/pdf_ops.py inspect --input entrada.pdf`

`python scripts/pdf_ops.py extract --input entrada.pdf --output texto.txt`

`python scripts/pdf_ops.py reorder --input entrada.pdf --output reordenado.pdf --pages 2,1`

`python scripts/pdf_ops.py render --input reordenado.pdf --output-dir render`

O JSON emitido inclui contagem de páginas, classificação textual e caminhos de saída. `inspect` e `extract` distinguem PDFs com texto extraível de PDFs provavelmente escaneados ou vazios. Para OCR, use o helper específico abaixo. `render` usa Poppler `pdftoppm`, detectando `PDFTOPPM`, PATH ou o binário bundled conhecido.

Dependências: Python 3 com `pypdf`; `pdftoppm` do Poppler apenas para renderização. O script recusa substituir o arquivo de entrada, inclusive por hardlink, e os resultados devem ser reabertos e renderizados quando a aparência importar. `pypdf` não recalcula nem interpreta conteúdo gráfico.

## OCR local

Para documentos escaneados, execute `python3 scripts/ocr_local.py --input entrada.pdf --pages 1-3 --lang por --output-dir ocr-novo`. Para uma imagem, omita `--pages`. O helper usa Tesseract, sem depender de visão do 9B ou de `pypdf`; para PDF também precisa de `pdfinfo` e `pdftoppm`. O modelo de idioma português acompanha o pacote, com origem e licença em `assets/tessdata/`; outros idiomas podem vir do sistema ou de `--tessdata-dir`.

Consulte [references/ocr.md](references/ocr.md) para idiomas, limites, saídas e códigos de retorno. TXT e TSV são gerados por página, com contagem de palavras e marcação de páginas vazias. Confira amostras contra o original: confiança do motor não equivale a exatidão, e OCR não preserva necessariamente tabelas ou diagramação. A saída fica em pasta nova; uma execução parcial nunca é declarada completa.
