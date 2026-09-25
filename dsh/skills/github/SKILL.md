---
name: github
description: Gerenciar repositórios GitHub, issues, pull requests, revisões e GitHub Actions usando `gh` instalado ou uma integração realmente disponível, com alvo explícito e verificação do resultado.
---

# GitHub

Use esta skill para consultar ou alterar repositórios, issues, pull requests, revisões e GitHub Actions. Prefira o GitHub CLI (`gh`) quando ele estiver instalado. Se não estiver, use somente uma integração que apareça nas ferramentas disponíveis no DSH e cuja operação e resposta sejam conhecidas; não invente nomes de conectores, endpoints ou capacidades.

## Descoberta e escopo

Antes de uma operação remota, confirme a ferramenta sem expor credenciais:

```bash
command -v gh
gh --version
gh help
```

Consulte também `gh <comando> --help` para a operação escolhida e use apenas flags mostradas ali. Não leia ou imprima `GH_TOKEN`, `GITHUB_TOKEN`, tokens de hosts Enterprise, arquivos de configuração ou qualquer outro segredo. Não faça chamadas remotas durante a descoberta da ferramenta.

Resolva o alvo exato antes de consultar ou alterar qualquer coisa:

- dê prioridade a `HOST/OWNER/REPO`, `OWNER/REPO`, URL, número de issue/PR, branch, workflow ou run fornecidos pelo usuário;
- se o repositório não foi informado, inspecione o diretório atual e seus remotes, e confirme o repositório antes de continuar; não escolha um remoto por suposição;
- passe `--repo HOST/OWNER/REPO` ou `-R` em `issue`, `pr`, `run` e `workflow`, e um repositório explícito nos comandos `repo` quando houver risco de ambiguidade;
- nunca transforme um nome, URL ou número recebido em código shell. Passe cada valor como argumento separado e faça escaping seguro quando o executor não oferecer argumentos estruturados.

Leia o recurso antes de editá-lo. Use `gh repo view`, `gh issue view`, `gh pr view --comments`, `gh pr diff`, `gh pr checks`, `gh workflow view --yaml` ou `gh run view` conforme o caso. Para saídas estáveis, use `--json` com campos disponíveis na ajuda e, quando necessário, `--jq` ou `--template`; não dependa de texto truncado ou de uma lista sem o repositório identificado.

## Operações

Os comandos verificados do CLI cobrem estas áreas:

- `gh repo`: `view`, `list`, `create`, `clone`, `fork`, `edit`, `sync` e outras subcomandos exibidos por `gh repo --help`;
- `gh issue`: `list`, `view`, `create`, `edit`, `comment`, `reopen`, `close` e outras subcomandos exibidos por `gh issue --help`;
- `gh pr`: `list`, `view`, `diff`, `checks`, `create`, `edit`, `comment`, `review`, `ready`, `reopen` e outras subcomandos exibidos por `gh pr --help`;
- Actions: `gh workflow list/view/run` e `gh run list/view/watch`, além de `cancel`, `rerun` e `download` quando pedidos explicitamente.

Para issues, PRs, comentários e reviews, prefira gravar o texto em um arquivo temporário UTF-8 e usar `--body-file`:

```bash
gh issue create -R OWNER/REPO --title "TÍTULO" --body-file BODY_FILE
gh issue comment -R OWNER/REPO 123 --body-file BODY_FILE
gh pr create -R OWNER/REPO --base BASE --head HEAD --title "TÍTULO" --body-file BODY_FILE
gh pr comment -R OWNER/REPO 456 --body-file BODY_FILE
gh pr review -R OWNER/REPO 456 --comment --body-file BODY_FILE
```

Use `gh pr review --approve` ou `--request-changes` somente quando o usuário pedir exatamente essa decisão. Para `gh api`, prefira `--input` com um JSON validado quando o payload for estruturado. Verifique o método: `--raw-field`/`--field` pode mudar o padrão para `POST`; use `-X GET` em leituras que tenham parâmetros. Não use `gh api` para contornar uma operação ou permissão não confirmada.

Para Actions, confirme primeiro que o workflow e seus inputs existem (`gh workflow list` e `gh workflow view WORKFLOW --yaml`). Só então use `gh workflow run WORKFLOW --ref REF` com `-f key=value` ou `--json` conforme a ajuda. `gh run list` e `gh run view RUN_ID --log-failed` servem para acompanhar e diagnosticar. Um run criado ou enfileirado não é sucesso: verifique `status` e `conclusion` até haver estado final, ou informe que permanece pendente.

## Autorização e segurança operacional

A autorização explícita do usuário para a operação atual basta; não peça reconfirmação. Execute somente a mutação pedida. Não faça merge, close, delete, archive, cancel, rerun, disable, enable, lock, unlock, transferência, exclusão de branch ou alteração de configurações sem pedido explícito, mesmo que pareça ser o próximo passo. `--dry-run` é útil para PRs, mas confirme seus efeitos: a ajuda do CLI informa que ele ainda pode fazer push de alterações Git.

Depois de toda mutação, faça readback do mesmo repositório e recurso. Confira URL, número, título, estado, branch, reviewers, labels, corpo ou estado do run conforme o pedido. Se o comando falhar, retornar estado parcial ou produzir apenas uma URL sem confirmação do recurso, informe a saída e o limite da verificação; nunca declare êxito por inferência. Preserve o texto e o alvo usados para permitir auditoria, omitindo segredos.

Não envie mensagens, comentários ou reviews em nome do usuário sem pedido explícito para essa ação. Quando a integração não estiver disponível, a autenticação não for suficiente, o alvo continuar ambíguo ou o readback não confirmar o resultado, pare com um relatório curto do bloqueio e do dado necessário para continuar.
