# Documentação do DSH — Arquitetura, Skills e Limitações

Repositório de backup das configurações **live** do DeepSeek Harness (`@deepseek-ai/dsh`
0.1.5-rc.2) + Codex. Este arquivo responde a quatro perguntas:

1. **Como funciona o DSH?** (arquitetura, perfis, ferramentas, ciclo de contexto)
2. **Quais skills estão implementadas e o que cada uma faz** (+ como funcionam)
3. **Quais limitações foram encontradas** no runtime desta sessão
4. **A instalação live tem backup em `/home/x/Documentos/DSH/` → GitHub?** (confirmação)

> **Autoridade:** a instalação live (`~/.dsh`, `~/.codex`) é a fonte da verdade.
> Este repositório espelha o live, aplicando normalização de caminhos e excluindo
> segredos/sessões/cache. Ver também [`INSTALACAO.md`](./INSTALACAO.md) (instalação)
> e [`README.md`](./README.md) (restauração).

---

## 1. Como funciona o DSH

### 1.1 Visão geral

O `dsh` é um **harness de agente** escrito em TypeScript como monorepo pnpm com
~150 pacotes sob `@deepseek-ai/`. O comando `dsh` é o único launcher Node suportado:
perfis são **empilhamentos ordenados de camadas de patch de bundles de plugins**,
sobrepostos às overrides do próprio usuário. Não há bins públicos separados para SDK
ou ACP — eles são perfis (`sdk`, `sdk-minimal`, `acp`), não comandos distintos.

Fonte: [`@deepseek-ai/dsh/README.md`](../../packages/dsh/README.md) (checkout local).

### 1.2 Perfis e composição da árvore de patches

Um diretório de perfil contém:
- `package.json` — dependências de plugins fora da árvore + manifest `dsh.profile`
  (lista ordenada `bundles` + ciclo de vida `patchReload`)
- `cordis.patch.yml` — camada de patch do próprio usuário

A composição parte de uma raiz vazia e aplica, nesta ordem:
1. o patch de cada bundle em `dsh.profile.bundles` (ordem)
2. depois `cordis.patch.yml` do perfil, depois `$DSH_HOME/cordis.patch.yml` (home)
3. depois overlays `--patch`

Bundles resolvem primeiro da instalação DSH (`@deepseek-ai/dsh-base`, `dsh-web-app`,
`dsh-headless`, `dsh-sdk-app`, …), depois dos `node_modules` do perfil, onde o pnpm
instala plugins fora da árvore.

### 1.3 Modos de entrada (entry modes)

| Comando | Propósito |
|---|---|
| `dsh --profile <name>` | Bootar o perfil nomeado sob `$DSH_HOME/profiles/<name>`. |
| `dsh --profile <name> --from-default-profile <template>` | Criar um perfil custom a partir de um template, depois bootá-lo. |
| `dsh --profile acp` | Servir clientes ACP via stdio até desconectar. |
| `dsh --profile headless "job"` | Uma sessão persistente nova, imprimir resposta final e sair. |
| `dsh --profile sdk` / `sdk-minimal` | Servir clientes SDK via JSON-RPC stdio. |
| `dsh web` | Alias de `--profile web`. |
| `dsh plugin --profile <name> <pnpm args>` | Gerenciar plugins do perfil, encadeando ao pnpm. |

O diretório invocado é a raiz do workspace por padrão. O nome `desktop` está reservado
ao perfil proprietário do Electron; o CLI rejeita boot/config-dump/plugin-management
para ele.

### 1.4 Ferramentas do agente (tools)

As ferramentas nativas expostas nesta sessão: `ask_user_question`, `bash`,
`create_goal`, `edit`, `exit_plan_mode`, `get_goal`, `glob`, `grep`, `job_kill`,
`job_list`, `job_output`, `read`, `skill`, `todo_write`, `update_goal`, `write`,
`web_fetch`, `web_search`. Mapeiam-se aos bundles internos:
`dsh-tool-bash/pwsh/fs/goal/jobs/skill/todo/subagent/workflow/web/ask-user/fs-search/present`.

### 1.5 Skills (mecanismo)

Skills são instruções estruturadas em Markdown carregadas de `$DSH_HOME/skills/*/SKILL.md`
e de pacotes de skill embutidos (`dsh-skill`, `dsh-client-ui-skill`). Cada `SKILL.md`
tem frontmatter:

```yaml
---
name: <nome>
description: <para o modelo — quando usar / escopo>
user-invocable: false        # pode o usuário chamar diretamente?
disable-model-invocation: false  # o modelo pode invocá-la automaticamente?
---
# corpo da instrução (política, passos, limites)
```

O `description` é a única coisa que o modelo lê para decidir quando aplicar; o corpo
é a política executada. Skills com `user-invocable: false` não são chamadas pelo
usuário e `disable-model-invocation: true` bloqueiam invocação automática (ex.:
`local-single-agent`).

### 1.6 Ciclo de contexto / Context Guard (loop-safety)

Para sessões de modelo local há um **guardião de contexto** persistente que mede
tokens estimados e impõe limites duradouros por turno:

- < 65536 tokens — operação normal.
- 65536–81920 (economia): leituras direcionadas, resultados concisos, diffs.
- 81920–94371 (preparar checkpoint): preservar objetivo, restrições, trabalho feito,
  decisões, arquivos mudados, comandos/resultados relevantes, erros abertos, estado
  atual e **um próximo passo**.
- ≥ 94371: compactação automática (janela 131072, thresholdRatio 0.72).

Limites duros por turno (resets apenas com uma nova virada do usuário; a compactação
não os renova): **48 passos, 48 chamadas de ferramenta, 15 minutos e 120 000 tokens
high-water**. Após timeout, o executor gerencia o processo, coleta saída disponível e
entra em *diagnostic mode* (no máximo 3 chamadas limitadas, 2 min, 24 000 tokens). O
comando exato que expirou é bloqueado até ver uma mudança de código/configuração ou
estratégia. `PAUSE` cancela o turno e nega chamadas subsequentes na fronteira do
executor — prosa do modelo não a sobrepõe.

Progresso = evidência nova (resultado, erro novo, teste mudado, correção confirmada).
Leituras idênticas, timeouts repetidos ou chamadas equivalentes **não** resetam o budget.

---

## 2. Skills implementadas — o que cada uma faz e como funciona

### 2.1 Skills funcionais no repositório (22 skills live em `~/.dsh/skills/`)

| # | Skill | Foco / o que faz | Como funciona (resumo) |
|---|-------|------------------|------------------------|
| 1 | **acompanhamento** | Acompanhar chamadas de ferramentas demoradas sem loops redundantes. | Proba artefatos duráveis/estado por classe de ferramenta diferente (mtime/tamanho, `pgrep`/`ps`) e prefere `job_list`/`job_output` em vez de `tail` de log — cada probe produz evidência nova. |
| 2 | **apresentacoes-template** | Preencher apresentação PPTX existente com conteúdo estruturado + verificar slides renderizados. | Lê template, preenche por dados estruturados; **não** promete criação livre de design. |
| 3 | **compressao-midia** | Comprimir imagens/áudio/vídeo locais por qualidade ou meta de tamanho. | Preserva originais e limita tentativas + tempo total. |
| 4 | **configuracoes-estruturadas** | Editar configs locais JSON/YAML/TOML por caminhos e valores explícitos. | Pré-condições, validação de tipos, saída separada; não edita fora do alvo. |
| 5 | **context-guard** | Política persistente de budget/contexto/checkpoint/loop-safety (auto-reforçada). | Reinforcada pelo harness; `user-invocable:false`, não espera invocação. |
| 6 | **dados-tabulares** | Transformar tabelas CSV/TSV/JSON ou reconciliar duas por chaves explícitas. | Detecta duplicatas/divergências **sem** modificar as origens. |
| 7 | **diagnostico-servicos-logs** | Diagnosticar containers/serviços/URLs/arquivos de log locais. | Coleta limitada + evidências redigidas; **não** reinicia nem altera serviços. |
| 8 | **documentos-template** | Preencher template DOCX com dados estruturados + verificar pacote/campos. | Para documentos Word baseados em modelo; não cobre redline complexo. |
| 9 | **graficos-locais** | Gerar gráficos PNG/SVG/PDF a partir de tabela local validada. | Preserva especificação, rótulos, unidades e proveniência. |
| 10 | **imagens-lote** | Redimensionar/cortar/convertir/generar miniaturas de imagens locais em lote. | Preserva originais; confirma dimensões/formato. |
| 11 | **jornadas-navegador** | Executar jornadas funcionais curtas no navegador local a partir de passos/checks. | Relatório por etapa + captura de falhas. |
| 12 | **local-single-agent** | Rodar tarefas com um único agente principal local, sem subagentes/workflow/Ralph/chamadas delegadas. | `disable-model-invocation:true` — bloqueia invocação automática. |
| 13 | **midia-local** | Inspecionar/cortar/extrair áudio/convertir arquivos locais de áudio/vídeo (FFmpeg). | Verifica duração, codecs e decodificação. |
| 14 | **organizacao-arquivos** | Planejar/aplicar cópias/renomeações em lote por mapeamentos explícitos. | Detecta colisões/duplicatas, verifica hashes, registra recuperação parcial. |
| 15 | **paginas-estaticas** | Criar/ajustar página HTML/CSS local baseada em template + verificar links/assets/responsividade. | Para sites estáticos pequenos; publicação não faz parte da skill. |
| 16 | **pdf-utilidades** | Inspecionar/transformar PDFs locais, extrair texto e OCR de páginas escaneadas/imagens. | Resultados verificáveis; preserva originais. |
| 17 | **pesquisa-fontes** | Respostas curtas com afirmações ligadas a fontes realmente consultadas (fato/inferência/bloqueio). | Para perguntas externas delimitadas; não é pesquisa autônoma extensa. |
| 18 | **planilhas-locais** | Criar/editar XLSX locais em células/intervalos/abas/tabelas explícitos. | Preserva conteúdo fora do alvo e declara situação de recálculo. |
| 19 | **quebra-de-loop** | Check automatizado contra loops de investigação redundante + guia para quebrá-los. | Antes de cada passo, exige evidência suficiente; nunca repete leituras equivalentes. |
| 20 | **sqlite-local** | Inspecionar schema e consultar bancos SQLite locais somente leitura (parâmetros/limites). | Exporta JSON ou CSV. |
| 21 | **testes-api** | Verificar endpoints HTTP autorizados com especificação JSON limitada (status/cabeçalhos/corpo). | Sem repetir requisições nem vazar segredos. |
| 22 | **verificacao-projeto** | Descobrir e executar verificações que já existem em um projeto (timeout + relatório de evidências). | Não inventa comandos nem altera o projeto. |

> **Discrepância de documentação:** [`INSTALACAO.md`](./INSTALACAO.md) §9 lista 20
> skills; o live tem **22** (`acompanhamento` e `quebra-de-loop` não estavam na tabela).
> O `HANDOFF.md` ainda referencia uma skill `declaracao-capacidade` que **não está** em
> `~/.dsh/skills/`. Ou seja: os docs estão ligeiramente defasados do live.

### 2.2 Como as skills funcionam (mecanismo comum)

1. **Frontmatter** (`name`, `description`, flags de invocação) é o contrato — o modelo
   decide *quando* aplicar pelo `description`.
2. **Corpo** = política executável: passos, pré-condições, limites e verificação.
3. **Disciplina compartilhada:** todas seguem "evidência suficiente → ação autorizada",
   sem repetir leituras equivalentes; preferem ferramentas duráveis (`job_list`,
   `job_output`) sobre logs voláteis; preservam originais e declaram estado de recálculo/
   verificação.

---

## 3. Limitações encontradas (nesta sessão / runtime)

| # | Limitação | Evidência |
|---|-----------|-----------|
| L1 | **Budgets duros por turno** — 48 passos, 48 chamadas de ferramenta, 15 min, 120k tokens; reset só com nova virada do usuário. A compactação não renova. | `context-guard/SKILL.md`, `AGENTS.md` |
| L2 | **Context Guard interrompe** o passo ativo nos thresholds e dispara compactação automática (≥94371). | `context-guard/SKILL.md` |
| L3 | **Diagnostic mode** pós-timeout: no máximo 3 chamadas limitadas, 2 min, 24k tokens; comando expirado bloqueado até mudança de código/config/estratégia. | `context-guard/SKILL.md` |
| L4 | **`PAUSE`** cancela o turno e nega chamadas subsequentes na fronteira do executor — prosa/notice não sobrepõe. | `context-guard/SKILL.md` |
| L5 | **Approval prompts desativados** nesta sessão: ações que exigem aprovação são rejeitadas automaticamente; o agente **não** pode pedir escalonamento de sandbox nem auto-conceder capacidade. | instrução de sessão, `HANDOFF.md` §23 |
| L6 | **`update_goal` sem campo para read-only-executor capability** → agente não pode auto-habilitar; resolução = habilitação pelo operador/nível de sessão. | `HANDOFF.md` §23 |
| L7 | **Goal antigo (Scryfall scrape)** só parcialmente visível na imagem; `get_goal` retorna apenas o goal ativo — não dá para editar sem objetivo/revision completos + capacidade. | `HANDOFF.md` §24 |
| L8 | **Docs defasados do live** — INSTALACAO.md diz 20 skills (live=22); HANDOFF menciona skill `declaracao-capacidade` ausente no live. | ver §2.1 |
| L9 | **Perfil `desktop` reservado** ao Electron; CLI rejeita boot/config-dump/plugin-management para ele. | `@deepseek-ai/dsh/README.md` |
| L10 | **Comandos inválidos / flags de outro modo / erros de config / boot falho → exit nonzero.** | `@deepseek-ai/dsh/README.md` |
| L11 | **Backup exclui intencionalmente** sessões, histórico, caches, estado do navegador e credenciais → reautenticar após restore. | `README.md`, `.gitignore` |
| L12 | **Snapshot sem dry-run**, allowlist explícito, substitui caminhos machine-específicos por marcadores; modelos locais (LM Studio) e apps externos são pré-requisitos não versionados. | `README.md`, `INSTALACAO.md` §12 |

---

## 4. Backup live → GitHub: confirmado

**Sim.** A instalação live tem backup neste repositório, empurrado para o GitHub.

- **Remote Git:** `origin` → `https://github.com/xoykor/DSH-Backup` (branch `master`).
- **Página do repo (verificada via web_fetch, HTTP 200):**
  > "Backup das configurações do Deepseek Harness - Otimizado para o uso agentico de IA localmente e integração com o Codex da OpenAI."

### Fluxo live → backup → GitHub

1. `restore-dsh.sh snapshot` — copia **live→backup** com normalização automática de
   caminhos; exclui segredos/sessões/cache (allowlist explícito, sem dry-run).
2. Commit local no branch `master`.
3. Push para `origin` (`https://github.com/xoykor/DSH-Backup`).

### Evidência concreta

| Item | Valor |
|------|-------|
| Diretório do backup (live) | `/home/x/Documentos/DSH/` |
| Remote GitHub | `https://github.com/xoykor/DSH-Backup` |
| Branch | `master` |
| Status da página no GitHub | **Ao vivo** (HTTP 200, descrição confirmada) |
| Arquivos versionados | `INSTALACAO.md`, `README.md`, `manifest.yaml`, `HANDOFF.md`, `restore-dsh.sh`, `runtime/`, `dsh/` (profiles/plugins/presets/skills/configs), `.gitignore` |
| **Não** versionado (intencional) | `secrets`, `sessions`, `storages`, `attachments`, `backups`, `compaction-*`, `node_modules`, credenciais, histórico |

> Nota: o workspace `/home/x/Documentos/DSH` é o clone do repo; o **live** real está
> em `~/.dsh` e `~/.codex`. O snapshot normaliza `$HOME`/`$CODEX_HOME`/`$DSH_HOME` no
> commit e a restauração reverte as substituições.

---

## 5. Referências

- [`INSTALACAO.md`](./INSTALACAO.md) — documentação completa da instalação live (modelos, perfis, presets, plugins, bridge).
- [`README.md`](./README.md) — restore/snapshot/verify e política de versionamento.
- [`HANDOFF.md`](./HANDOFF.md) — handoff de sessão (commits, decisão pendente `declaracao-capacidade`, bloqueios).
- Checkout do runtime: `/home/x/.local/lib/dsh-runtime-0.1.5-rc.2/` → pacote `@deepseek-ai/dsh@0.1.5-rc.2`.
- Sistema-prompt/contexto do agente nesta sessão: `~/.dsh/AGENTS.md` (inclui a skill `anti-investigacao-redundante`).
