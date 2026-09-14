---
name: documentos-template
description: Preencher um template DOCX com dados estruturados e verificar o pacote e os campos resultantes. Use quando a tarefa pede um documento Word baseado em modelo; não cobre redline complexo.
---

# Documentos a partir de template

Use esta skill quando o usuário fornecer um `.docx` existente e campos explícitos para preencher. Preserve o arquivo original e escreva o resultado em um caminho novo.

1. Leia o template e confirme os campos no formato `{{campo}}`. Converta os dados para um JSON simples; não invente valores ausentes.
2. Execute `scripts/fill_docx --template TEMPLATE --values DATA.json --output RESULT.docx`. O filler Rust substitui campos contíguos em texto do pacote e valida XML antes de publicar. Campos divididos entre runs do Word devem ser corrigidos no template ou editados com uma biblioteca DOCX disponível.
3. Execute `scripts/validate_docx --input RESULT.docx --require "texto esperado"`. O helper Rust valida o ZIP/XML. Se houver `soffice`, acrescente `--render-dir DIR` e verifique o PDF gerado; sem renderizador, declare a limitação.

Não altere estilos, imagens ou seções sem pedido. Não afirme que a paginação foi verificada sem renderizar. Para conteúdo extenso ou campos avançados, primeiro confirme se `python-docx` está instalado e use a ferramenta disponível no ambiente; os helpers desta skill não baixam dependências.

Use [fixtures/values.json](fixtures/values.json) como exemplo de entrada. O contrato detalhado de campos está em [references/contract.md](references/contract.md).
