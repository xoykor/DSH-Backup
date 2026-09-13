# Contrato de preenchimento

Entrada: objeto JSON, ou objeto com uma chave `values`, cujas chaves usam letras, números, `_`, `-` ou `.`. O marcador no DOCX é `{{nome}}`; espaços dentro das chaves são aceitos.

Valores escalares são convertidos para texto. Quebras de linha são preservadas no XML, mas não criam parágrafos novos. Para listas, tabelas ou conteúdo rico, use um template apropriado e uma biblioteca DOCX instalada.

O helper falha sem escrever o resultado quando encontra campo sem valor. O relatório inclui `replaced`, `missing` e os membros XML alterados. A substituição é feita apenas dentro de elementos `w:t` de partes `word/` do pacote para não corromper relações ou metadados.
