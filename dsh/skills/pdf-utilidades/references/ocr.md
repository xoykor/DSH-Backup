# OCR de imagens e PDFs

```text
python3 scripts/ocr_local.py --input documento.pdf --pages 1,3-5 --lang por --output-dir resultado-ocr
python3 scripts/ocr_local.py --input imagem.png --lang por+eng --psm 6 --output-dir resultado-imagem
```

PDFs exigem seleção explícita de páginas, numeradas a partir de 1; imagens usam página 1. Não repita páginas. Máximo: 100 páginas por chamada. O idioma padrão é `por`; seu arquivo oficial do Tesseract acompanha a skill. `eng`, quando pedido, pode vir da instalação do sistema. Idioma ausente causa erro antes de processar. `--tessdata-dir DIR` oferece uma raiz adicional com prioridade para modelos explicitamente fornecidos.

`--dpi` aceita 72–400, padrão 200; o renderizador limita também o lado maior a 5000 pixels. `--psm` aceita 3 (página automática, padrão), 4 (coluna), 6 (bloco), 7 (linha) ou 11 (texto esparso). O helper não corrige orientação automaticamente. `--timeout-seconds` aceita 1–600, padrão 120, para as ferramentas de todas as páginas juntas. O processo e seus filhos são encerrados no timeout.

Saída em diretório novo: `page-NNN.txt`, `page-NNN.tsv` e `report.json`. O relatório mantém proveniência por SHA-256, páginas, idioma e caminhos; não inclui o texto extraído na resposta curta. TSV contém coordenadas e confiança por palavra. `completed_empty` indica processamento concluído sem texto; não deve ser apresentado como extração bem-sucedida de conteúdo.

Exit 0: processamento de todas as páginas concluído (`completed` ou `completed_empty`). Exit 2: erro de entrada, dependência, ferramenta, timeout ou resultado `partial`. Em resultado parcial, só as páginas listadas no relatório foram verificadas; outras saídas podem estar incompletas. O helper não sobrescreve pasta existente, não produz PDF pesquisável e não altera o original.
