---
name: apresentacoes-template
description: Preencher uma apresentação PPTX existente com conteúdo estruturado e verificar slides renderizados. Use quando houver template de PowerPoint; não promete criação livre de design.
---

# Apresentações a partir de template

Use um `.pptx` fornecido pelo usuário, mapeando campos `{{campo}}` para valores explícitos. Preserve mestre, tema, ordem e elementos que não forem alvo.

1. Confirme os campos e prepare um JSON. Para texto de slide, use `scripts/fill_pptx.py --template TEMPLATE --values DATA.json --output RESULT.pptx`.
2. Rode `scripts/validate_pptx --input RESULT.pptx --render-dir render/`. O helper Rust valida o ZIP/XML, procura marcadores restantes e, quando `soffice` existe, converte a apresentação em PDF para inspeção visual.
3. Relate qualquer limitação de renderização ou de campos divididos entre runs. Se a tarefa exigir tabelas, gráficos, animações ou ajuste de layout, use `python-pptx`/PptxGenJS somente se instalados e faça uma verificação adicional.

Não alterar o template original, não reordenar slides sem instrução e não declarar que não há cortes apenas por o arquivo abrir: a evidência deve incluir renderização e inspeção das páginas.

Use [fixtures/values.json](fixtures/values.json) como entrada mínima.
