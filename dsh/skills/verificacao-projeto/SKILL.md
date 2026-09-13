---
name: verificacao-projeto
description: Descobrir e executar verificações que já existem em um projeto, com timeout e relatório de evidências. Use para validar uma mudança local; não invente comandos nem altere o projeto.
---

# Verificação de projeto

Antes de testar, leia os manifests e identifique comandos reais. Rode `scripts/run_checks.py --root PROJETO` para listar verificações declaradas em `package.json`, `pyproject.toml`, `Cargo.toml` e alvos comuns de `Makefile`; descoberta não executa comandos. Para uma seleção explícita, passe `--command nome=COMANDO` (repetível), ou use `--run-discovered` apenas quando executar todos os checks descobertos for apropriado.

O helper captura código de saída, duração, stdout/stderr truncados e classifica `passed`, `failed_project`, `failed_infrastructure` ou `skipped`. Um comando inexistente, dependência ausente, timeout ou indisponibilidade do executor é infraestrutura; falha de asserção, compilação ou lint é falha do projeto. Corrija a causa e rode novamente apenas a verificação afetada.

Não crie comandos só porque parecem convencionais. Se nenhum manifestar uma verificação, informe `no_checks_discovered`. Executores indisponíveis deixam o resultado incompleto e não contam como sucesso. O resultado em JSON inclui commit e estado sujo quando o projeto é Git; vincule-o ao estado testado e ao ambiente. A skill não instala dependências, publica artefatos ou reinicia serviços.

Use [fixtures/plan.json](fixtures/plan.json) e [fixtures/project/package.json](fixtures/project/package.json) para um teste mínimo do runner.
