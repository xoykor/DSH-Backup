---
name: pesquisa-fontes
description: Produzir respostas curtas com afirmações ligadas a fontes realmente consultadas, separando fato, inferência e bloqueio. Use para perguntas externas delimitadas; não é pesquisa autônoma extensa.
---

# Pesquisa com fontes

Delimite a pergunta e a data de consulta. A busca de internet deste DSH usa exclusivamente o SearXNG local por meio da ferramenta `web_search`. Se a ferramenta estiver oculta, procure por `searxng`, `web`, `internet`, `busca`, `buscador` ou `pesquisa` no catálogo e desbloqueie `web_search`; não procure outro provedor. O endpoint local pode estar indisponível. Só use `web_fetch` ou automação de navegador se aparecerem como ferramentas registradas; o plugin de navegador pode não registrar quando `registerBrowserAutomation` não existe.

Faça uma busca pequena, selecione fontes primárias ou diretamente relevantes e abra o conteúdo completo com a ferramenta efetivamente disponível. Snippet de busca é pista, não evidência. Registre URL, título, data de consulta e o trecho que sustenta cada afirmação. Marque como `fact` o que a fonte declara e `inference` o que foi deduzido, explicando a ligação.

Se a busca, a abertura da fonte ou a rede falhar, responda com o bloqueio e o que ainda não foi verificado; não preencha lacunas com memória. Para validar o registro antes de responder, rode `scripts/validate_research --input EVIDENCE.json`. A validação Rust é local e não simula uma consulta.

Use [fixtures/evidence.json](fixtures/evidence.json) como formato mínimo.
