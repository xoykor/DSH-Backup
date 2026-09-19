# Documentação da Instalação Live DSH/Codex

Este documento descreve a instalação versionada do DeepSeek Harness (DSH) e os
componentes usados para reproduzir o ambiente local. A instalação live em
`~/.dsh` e `~/.codex` continua sendo a fonte operacional; este repositório é
o snapshot declarativo usado para restaurá-la.

> **Importante:** valores de contexto, limites e políticas podem ser
> sobrescritos por profile/preset. Durante uma sessão, a mensagem
> `ACTIVE CONTEXT POLICY` emitida pelo `dsh-context-guard` é a referência
> efetiva. Não use números estáticos deste arquivo para substituir a política
> ativa.

---

## 1. Runtime e requisitos

| Item | Valor |
|---|---|
| Pacote DSH | `@deepseek-ai/dsh` |
| Versão DSH | `0.1.5-rc.2` |
| Node | `>=22` |
| pnpm | `11.26.0` |
| Prefixo de instalação | `~/.local` |
| DSH home | `~/.dsh` |
| Codex home | `~/.codex` |

O runtime é fixado por `runtime/package-lock.json`. O arquivo
`manifest.yaml` contém as versões esperadas usadas pelo restaurador.

---

## 2. Layout versionado

```text
.
├── manifest.yaml
├── restore-dsh.sh
├── runtime/
│   ├── package.json
│   ├── package-lock.json
│   └── patches/
├── dsh/
│   ├── AGENTS.md
│   ├── settings.yaml
│   ├── cordis.patch.yml
│   ├── workspace.json
│   ├── profiles/
│   ├── presets/
│   ├── skills/
│   ├── plugins/
│   └── bridges/
└── codex/
```

Na instalação live, estes caminhos são materializados principalmente em:

```text
~/.dsh/
~/.codex/
~/.local/
```

O snapshot normaliza caminhos locais para `__HOME__`, `__DSH_HOME__` e
`__CODEX_HOME__`.

---

## 3. Profiles

Atualmente existem **3 profiles** versionados.

### 3.1 `web`

Perfil principal de interface web.

Dependências próprias relevantes:

- `dsh-context-guard`;
- `dsh-continue-button`;
- `dsh-global-token-meter`;
- `dsh-memory 0.7.1`;
- `relay-dsh-plugin-codex 0.2.2`.

O profile usa `patchReload: live`.

### 3.2 `robust-local`

Perfil dedicado à execução agentic local mais controlada.

Bundles principais:

- `@deepseek-ai/dsh-base`;
- `@deepseek-ai/dsh-web-app`;
- `dsh-context-guard`;
- `dsh-memory`.

Também injeta componentes locais adicionais por
`profiles/robust-local/cordis.patch.yml`, incluindo:

- goal verification;
- verification enforcement;
- browser tool;
- plugin guide;
- test drive;
- score;
- performance diagnostics;
- budget;
- output styles;
- translate;
- library/RAG;
- checkpoint rewind;
- doublecheck.

O goal padrão do DSH é desabilitado nesse profile e substituído pela camada
`goal-verified`.

### 3.3 `headless`

Perfil para execução sem a interface web, usado em jobs e clientes que não
dependem da UI interativa.

---

## 4. Presets de agente

Existem **6 presets** em `dsh/presets/`:

1. `local-models`
2. `local-models-ptc`
3. `local-robust-9b`
4. `local-robust-27b`
5. `ornith-gemini-architect`
6. `relay-codex`

### `local-robust-9b`

Preset principal para Ornith 1.5 9B.

Características relevantes:

- execução single-agent;
- Ralph desabilitado;
- subagents e delegação desabilitados;
- workflow genérico desabilitado;
- ferramentas nativas preservadas;
- Goals e verificação usados explicitamente;
- política anti-investigação redundante;
- compatibilidade com jobs gerenciados;
- integração com Context Guard.

O preset contém skills próprias:

- `anti-investigacao-redundante`;
- `auditoria-visual`.

### `local-models-ptc`

Preset de apresentação de ferramentas no modo PTC. Ralph, subagents e workflow
genérico permanecem desabilitados para evitar uma segunda superfície de
orquestração concorrente com `run_code`.

### `local-robust-27b`

Preset robusto equivalente voltado ao modelo local de 27B configurado no
profile `robust-local`.

---

## 5. Modelos locais e providers

### LM Studio

O provider local usa:

```text
http://127.0.0.1:1234/v1
```

e a API OpenAI-compatible `openai-responses`.

No profile `robust-local`, os modelos explicitamente configurados são:

| ID | Janela configurada | Max output |
|---|---:|---:|
| `ornith-1.5-9b` | 131072 | 24576 |
| `qwen3.8-27b-gsq-rco` | 64000 | 12000 |

O modelo padrão do profile robusto é:

```text
lmstudio / ornith-1.5-9b
reasoningEffort: high
```

O profile configura tempos longos de streaming para acomodar prefill e
raciocínio local.

### Configuração raiz

`dsh/settings.yaml` contém a configuração global/default do host. Ela não deve
ser confundida com a configuração específica de `profiles/robust-local`.

A precedência de camadas importa: bundles, patch do profile, patch global e
overlays podem alterar valores. Por isso a política ativa informada pelo runtime
é a autoridade durante a execução.

---

## 6. Context Guard

O plugin `dsh-context-guard` é uma camada de execução determinística. Ele não
depende apenas de instruções de prompt.

Ele observa:

- pressão de contexto;
- número de passos e chamadas, quando o preset define limites;
- uso de tokens quando configurado;
- fingerprints de resultados;
- tentativas semanticamente equivalentes;
- famílias de erro;
- mudanças reais no workspace;
- ciclos repetidos de ferramentas;
- timeouts;
- estado de jobs gerenciados.

### Presets robustos

`local-robust-9b` e `local-robust-27b` configuram:

```text
maxTurnSteps: null
maxTurnToolCalls: null
maxTurnMs: null
```

Portanto não possuem um teto cumulativo artificial de 48 passos, 48 chamadas ou
15 minutos no turno. Continuam valendo:

- anti-loop;
- timeouts individuais;
- orçamento de diagnóstico;
- compactação;
- cancelamento do usuário;
- limites próprios de ferramentas.

Outros presets podem continuar usando os defaults globais.

### Política de contexto

Os limiares são derivados por razões do tamanho de janela configurado. A UI do
Context Guard permite editar:

- janela;
- economy;
- checkpoint;
- compactação;
- reserva de resposta;
- reserva de resumo;
- margem de segurança;
- retenção pós-compactação.

A mensagem `ACTIVE CONTEXT POLICY` mostra os números absolutos efetivos para a
sessão corrente.

---

## 7. Compactação de contexto

A instalação inclui compactação automática integrada ao Context Guard.

Fluxo esperado:

```text
pressão de contexto
→ pause do trabalho normal
→ resumo textual do histórico durável
→ validação do envelope/tamanho
→ persistência do resumo
→ checkpoint
→ substituição da superfície de contexto
→ retomada
```

Uma saída de resumo vazia, truncada, cancelada, não textual ou não persistida
não autoriza a substituição do histórico original.

O histórico durável original continua disponível no log/event store.

---

## 8. Patches locais do runtime

Existem **5 patches** em `runtime/patches/`.

### 8.1 `checkpoint-compaction`

Corrige o fluxo de checkpoint antes da compactação e impede substituição do
histórico sem resumo válido e persistido.

### 8.2 `compaction-progress`

Exibe progresso visual de leitura/resumo e gravação durante a compactação.

### 8.3 `goal-round-compaction`

Permite que um goal ativo retome corretamente após a pausa transitória causada
pela compactação.

### 8.4 `job-observation`

Marca `job_output` e `job_list` como observadores reconhecidos pelo executor.
Uma espera bloqueante por um job ativo pode ser tratada como neutra para a
detecção de investigação redundante.

`waitExpired:true` com job ainda `running` ou `stopping` significa apenas
que a espera terminou; não é timeout de execução do job.

### 8.5 `local-http-timeout`

Ajusta o transporte HTTP usado por providers loopback para respeitar os
timeouts maiores configurados no DSH/LM Studio. Evita falha prematura do
transporte durante prefill local silencioso.

### Integridade dos patches

Os aplicadores validam hashes de origem e de resultado. Conteúdo desconhecido
é recusado em vez de receber patch cegamente.

---

## 9. Memória persistente

A memória persistente oficial do ambiente é **dsh-memory 0.7.1**.

Ela está configurada nos profiles `web` e `robust-local`.

A política global em `AGENTS.md` orienta o agente a usar:

- `memory_search` — recuperar fatos duráveis relevantes;
- `memory_write` — registrar um novo fato durável;
- `memory_update` — atualizar um fato canônico existente;
- `memory_review` — manutenção/curadoria;
- `memory_stats` — diagnóstico.

Não devem ser armazenados como memória:

- logs transitórios;
- segredos;
- resultados intermediários;
- estado de execução de uma tarefa;
- informações facilmente recuperáveis do próprio repositório.

O antigo `dsh-memento` foi removido. Não há duas camadas concorrentes de
memória persistente no profile atual.

---

## 10. Skills

Existem **24 skills globais** em `dsh/skills/`:

1. `acompanhamento`
2. `apresentacoes-template`
3. `compressao-midia`
4. `configuracoes-estruturadas`
5. `context-guard`
6. `dados-tabulares`
7. `diagnostico-servicos-logs`
8. `documentos-template`
9. `graficos-locais`
10. `imagens-lote`
11. `jornadas-navegador`
12. `local-single-agent`
13. `midia-local`
14. `organizacao-arquivos`
15. `paginas-estaticas`
16. `pdf-utilidades`
17. `pesquisa-fontes`
18. `planilhas-locais`
19. `prism-modpack`
20. `quebra-de-loop`
21. `sqlite-local`
22. `testes-api`
23. `tool-first`
24. `verificacao-projeto`

Alguns presets também possuem skills próprias sob
`dsh/presets/<preset>/skills/`.

O catálogo deve ser carregado sob demanda. O agente não deve abrir todas as
skills preventivamente.

---

## 11. Plugins versionados

Existem atualmente **20 diretórios de plugins** em `dsh/plugins/`:

1. `dsh-architect`
2. `dsh-budget`
3. `dsh-checkpoint-rewind`
4. `dsh-context-guard`
5. `dsh-continue-button`
6. `dsh-doublecheck`
7. `dsh-fast`
8. `dsh-global-token-meter`
9. `dsh-goal-verification`
10. `dsh-library`
11. `dsh-output-styles`
12. `dsh-plugin-guide`
13. `dsh-qwen-defaults`
14. `dsh-score`
15. `dsh-system-search`
16. `dsh-test-drive`
17. `dsh-tool-browser`
18. `dsh-translate`
19. `dsh-verification`
20. `dsh-web-search-searxng`

`dsh-memory` é instalado como dependência dos profiles a partir da release
fixada, portanto não faz parte dessa contagem de diretórios em `dsh/plugins`.

---

## 12. Busca web e browser

### SearXNG

O provider de pesquisa web local é configurado em:

```text
http://127.0.0.1:8888
```

O plugin `dsh-web-search-searxng` expõe essa busca ao DSH.

### Browser

O profile robusto monta `dsh-tool-browser`, cujo serviço é configurado em:

```text
http://127.0.0.1:8731
```

Esses serviços externos precisam estar disponíveis no host para que as
ferramentas correspondentes funcionem.

---

## 13. Permissões

A configuração atual usa:

```yaml
permission:
  defaultPreset: danger-full-access
```

Isso é intencional para tarefas agentic locais que precisam operar o sistema,
mas amplia o raio de ação de shell, filesystem e plugins. O Context Guard limita
loops e comportamento redundante; ele não substitui um sandbox de segurança.

---

## 14. Backup e restore

### Criar snapshot

```bash
./restore-dsh.sh snapshot
```

O snapshot:

- usa allowlist de áreas gerenciadas;
- remove associações de sessões do `workspace.json`;
- exclui `.git`, `node_modules`, `.env*`, auth, credentials,
  `__pycache__`, `*.pyc` e `*.jsonl`;
- normaliza caminhos dependentes da máquina.

### Restaurar

```bash
./restore-dsh.sh restore
```

O restore:

1. lê `manifest.yaml`;
2. instala o runtime bloqueado;
3. preserva os caminhos gerenciados existentes em backup;
4. materializa `~/.dsh` e `~/.codex`;
5. reinstala dependências dos profiles;
6. aplica patches do runtime;
7. valida a configuração.

### Verificar

```bash
./restore-dsh.sh verify
```

Use a verificação para conferir o estado instalado sem substituir a
configuração.

---

## 15. Dados deliberadamente não versionados

O repositório não pretende preservar:

- credenciais;
- tokens;
- sessões;
- histórico de conversa;
- caches;
- estado de navegador;
- modelos do LM Studio;
- package-manager caches;
- artefatos transitórios de execução.

Após um restore, autenticações externas devem ser refeitas.

> A exclusão de nomes conhecidos não deve ser interpretada como um scanner de
> segredos genérico. Antes de publicar um snapshot, revise o diff e verifique se
> novos arquivos de configuração não passaram a conter tokens ou chaves.

---

## 16. Codex

O snapshot também preserva partes selecionadas de `~/.codex`, incluindo:

- configuração;
- computer-use;
- rules;
- skills;
- plugins pessoais selecionados.

Arquivos de autenticação, sessões e caches permanecem fora do snapshot.

---

## 17. Fonte de verdade e precedência

Use esta ordem conceitual ao diagnosticar configuração:

1. runtime/base bundles;
2. bundle patches;
3. profile;
4. `cordis.patch.yml` do profile;
5. patch global de `~/.dsh`;
6. overlays/flags adicionais;
7. settings persistidos pela UI;
8. política efetiva exposta ao agente/runtime.

Quando houver divergência entre números documentados e a sessão em execução,
confie na configuração efetiva mostrada pelo próprio DSH.

---

## 18. Arquivos de referência

- `README.md` — visão geral e operação.
- `DOCUMENTACAO-DSH.md` — arquitetura detalhada.
- `dsh/AGENTS.md` — política global do agente.
- `dsh/cordis.patch.yml` — patch global.
- `dsh/profiles/robust-local/` — configuração do host robusto.
- `runtime/patches/*/README.md` — detalhes dos patches.
- `restore-dsh.sh` — snapshot, restore e verify.
- `HANDOFF.md` — registro histórico; não é fonte canônica do estado atual.
