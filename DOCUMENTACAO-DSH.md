# Arquitetura Técnica do DSH-Backup

Este documento descreve a arquitetura técnica versionada em
`xoykor/DSH-Backup`. Ele complementa `INSTALACAO.md`: enquanto aquele arquivo
foca no layout e restauração da instalação, este explica o comportamento do
harness, as camadas de controle do agente e os patches locais do runtime.

O snapshot atual é baseado em:

- `@deepseek-ai/dsh@0.1.5-rc.2`;
- Node `>=22`;
- pnpm `11.26.0`;
- LM Studio como backend local principal;
- Ornith 1.5 9B como modelo local padrão do profile robusto.

---

## 1. Visão geral

O repositório deixou de ser apenas uma cópia de arquivos de configuração. Ele
versiona uma camada própria de comportamento sobre o DSH:

```text
modelo local
   │
   ▼
preset do agente
   │
   ▼
ferramentas / skills / goals
   │
   ▼
verification + context guard
   │
   ▼
executor DSH
   │
   ├── jobs
   ├── filesystem
   ├── shell
   ├── web
   ├── browser
   └── memory
   │
   ▼
patches do runtime
   │
   ▼
LM Studio / serviços locais / sistema operacional
```

A estratégia central é deslocar parte da confiabilidade do modelo para
mecanismos determinísticos do harness:

- reduzir superfícies de orquestração para modelos pequenos;
- impedir loops no executor;
- exigir evidência antes de conclusão;
- compactar contexto de forma durável;
- manter memória persistente separada de estado transitório;
- observar jobs sem punir esperas válidas.

---

## 2. Composição do DSH

O DSH usa Cordis para compor bundles e patches. A precedência exata pode variar
conforme profile e overlays, mas conceitualmente há:

1. bundles base do DSH;
2. patches dos bundles;
3. bundles do profile;
4. `cordis.patch.yml` do profile;
5. patch global `~/.dsh/cordis.patch.yml`;
6. overlays adicionais;
7. settings persistidos pela UI.

Por isso existem arquivos com valores aparentemente diferentes para a mesma
política. Durante uma sessão, a configuração efetiva exposta pelo runtime é a
autoridade.

---

## 3. Profiles

Existem **3 profiles**.

### 3.1 `web`

Profile de interface web padrão.

Bundles relevantes:

- DSH base;
- DSH web app;
- Relay Codex;
- Context Guard;
- Continue Button;
- Global Token Meter;
- DSH-memory.

O profile usa reload de patch em modo `live`.

### 3.2 `robust-local`

Profile especializado para modelos locais.

Principais características:

- Context Guard como bundle próprio;
- DSH-memory como dependência;
- verificação de metas;
- verification enforcement;
- browser local;
- ferramentas auxiliares de plugin, teste, score, budget e diagnóstico;
- checkpoint rewind;
- doublecheck;
- library/RAG.

O goal padrão é desabilitado neste profile e uma variante verificada é montada
no lugar.

### 3.3 `headless`

Profile para execução sem a UI web.

---

## 4. Presets

Existem **6 presets**:

| Preset | Papel |
|---|---|
| `local-models` | modelo local genérico |
| `local-models-ptc` | ferramentas em modo PTC |
| `local-robust-9b` | execução robusta single-agent para 9B |
| `local-robust-27b` | execução robusta para o modelo local de 27B |
| `ornith-gemini-architect` | arquitetura/planejamento híbrido |
| `relay-codex` | integração Relay/Codex |

### 4.1 Local Robust 9B

O `local-robust-9b` é deliberadamente restritivo na orquestração:

- Ralph desabilitado;
- subagents desabilitados;
- forks desabilitados;
- providers externos de subagent desabilitados;
- workflow genérico desabilitado;
- ferramentas nativas mantidas.

A instrução do preset também estabelece explicitamente:

```text
Do not use Ralph.
Do not use subagents or delegation.
Work alone.
```

O objetivo é reduzir a árvore de decisões do modelo e fazer o 9B trabalhar com
ferramentas determinísticas em vez de delegação recursiva.

### 4.2 PTC

No `local-models-ptc`, a apresentação de ferramentas usa o modo `ptc`.
Ralph, subagents e workflow genérico permanecem desabilitados para não criar
outra superfície de programação/orquestração concorrente com `run_code`.

---

## 5. AGENTS.md: política global

`dsh/AGENTS.md` é a principal camada de instrução global do agente.

Ela define, entre outras coisas:

- política tool-first;
- comportamento anti-loop;
- política de compactação;
- observação correta de jobs;
- memória persistente;
- regras de segurança do `run_code`;
- ambiente CachyOS/Arch;
- shell interativo fish para comandos destinados ao usuário;
- catálogo de skills.

O arquivo é uma política de modelo. As garantias críticas de loop, timeout e
compactação não dependem somente dele; são reforçadas pelo executor.

---

## 6. Tool-first

A skill global `tool-first` orienta investigação local na seguinte ordem:

1. ferramenta determinística pronta;
2. pipeline shell curto;
3. scratch Lua para lógica estruturada;
4. Python quando biblioteca/formato especializado justificar;
5. leitura direta do trecho necessário.

A intenção é evitar:

- despejo de arquivos inteiros;
- scripts desnecessários;
- parsing manual de formatos já suportados;
- consumo excessivo de contexto.

Resultados devem preservar evidência acionável: caminho, linha, contagem,
truncamento e erro.

---

## 7. Anti-loop em duas camadas

Há duas camadas complementares.

### 7.1 Orientação ao modelo

Skills como:

- `quebra-de-loop`;
- `anti-investigacao-redundante` nos presets robustos;
- `acompanhamento`;

ensinam o agente a não repetir investigações equivalentes.

### 7.2 Interceptação determinística

O plugin `dsh-context-guard` observa diretamente a execução.

Ele mantém estado sobre:

- ação canônica;
- argumentos;
- fingerprints de resultado;
- família de erro;
- versão de mudança do workspace;
- sequência recente de ações;
- texto repetido do assistente;
- jobs coletados;
- pressão de contexto.

Trocar apenas:

- wording;
- ferramenta;
- ordem de leitura;
- grep por read;
- chamada equivalente;

não é suficiente para escapar do bloqueio se o executor conclui que a
investigação continua materialmente igual.

---

## 8. Context Guard

O plugin está em:

```text
dsh/plugins/dsh-context-guard/
```

Ele injeta hooks no runtime DSH e atua antes/depois de chamadas de ferramenta,
durante passos do agente e em eventos de sessão.

### 8.1 Progresso

Progresso é evidência nova, por exemplo:

- novo resultado;
- erro materialmente diferente;
- teste com resultado diferente;
- mutação real do workspace;
- hipótese eliminada;
- correção confirmada.

Executar uma ferramenta por si só não é progresso.

### 8.2 Falhas equivalentes

Falhas são agrupadas por famílias. Repetir a mesma classe de falha sem mudança
observável consome o orçamento anti-loop da estratégia.

### 8.3 Ciclos

O guard guarda um histórico compacto de ações e fingerprints. Sequências
repetidas com resultados inalterados podem encerrar o turno mesmo quando cada
chamada individual usa argumentos ligeiramente diferentes.

### 8.4 PAUSE/STOP

Quando o guard decide pausar ou encerrar, o bloqueio ocorre na fronteira do
executor. Texto do modelo não pode reautorizar ferramentas.

---

## 9. Limites de turno: correção importante

Documentação histórica mencionava como limite geral:

```text
48 passos
48 chamadas
15 minutos
```

Isso **não é verdadeiro para os presets robustos atuais**.

`local-robust-9b` e `local-robust-27b` configuram:

```yaml
maxTurnSteps: null
maxTurnToolCalls: null
maxTurnMs: null
```

Portanto, nesses presets, uma tarefa produtiva pode continuar através de
compactações até ser implementada e verificada.

Continuam ativos:

- detecção de loop;
- limites de diagnóstico;
- timeout próprio de ferramentas;
- cancelamento;
- autoridade/permissões;
- orçamento de contexto;
- compactação.

Os defaults globais de 48/48/900000 ms ainda existem para presets que não os
sobrescrevem.

---

## 10. Política de contexto

O Context Guard deriva os limites absolutos a partir de ratios.

Os campos configuráveis incluem:

- `contextWindow`;
- `economyRatio`;
- `checkpointRatio`;
- `compactRatio`;
- `responseRatio`;
- `summaryRatio`;
- `summaryMinRatio`;
- `safetyRatio`;
- `retainRatio`.

Em vez de depender de valores escritos neste documento, o agente recebe um
notice semelhante a:

```text
ACTIVE CONTEXT POLICY:
effective context window ...
economy ...
checkpoint ...
automatic compaction ...
```

Esse notice e o medidor nativo são a referência da sessão.

---

## 11. Compactação

O DSH original foi estendido para tornar a compactação mais segura.

### 11.1 Fluxo

```text
threshold atingido
     │
     ▼
interrompe admissão de novo trabalho
     │
     ▼
aguarda passo ativo estabilizar
     │
     ▼
resume histórico durável balanceado
     │
     ▼
valida tamanho/saída
     │
     ▼
persiste resumo
     │
     ▼
persiste checkpoint
     │
     ▼
substitui superfície de contexto
     │
     ▼
retoma execução
```

### 11.2 Falha fechada

Não há substituição se o resumo:

- falhar;
- estiver vazio;
- for truncado;
- contiver saída não textual inadequada;
- não couber com a margem de segurança;
- não puder ser persistido.

A compactação não apaga evidência de loops ou renova artificialmente orçamento
de diagnóstico.

---

## 12. Patches de runtime

Existem **5 patches** versionados.

### 12.1 Checkpoint Compaction

Local:

```text
runtime/patches/checkpoint-compaction/
```

Extende `@deepseek-ai/dsh-compaction-basic@0.1.5-rc.2`.

Funções principais:

- resumo do histórico durável;
- pricing do envelope;
- redução do output cap quando necessário;
- persistência antes da substituição;
- preservação de mensagens que chegam fora do span;
- rejeição de tool calls emitidas durante o resumo.

### 12.2 Compaction Progress

Local:

```text
runtime/patches/compaction-progress/
```

Adiciona feedback visual à UI durante compactação.

As barras são indeterminadas porque o protocolo não fornece percentual real de
prefill do LM Studio.

### 12.3 Goal Round Compaction

Local:

```text
runtime/patches/goal-round-compaction/
```

Corrige interação entre goals e pausa de compactação. Rejeições transitórias
causadas pelo Context Guard deixam de ser interpretadas como bloqueio
permanente do goal.

Uma pausa intencional do usuário não é retomada automaticamente.

### 12.4 Job Observation

Local:

```text
runtime/patches/job-observation/
```

Expõe capacidade de observação real para:

- `job_output`;
- `job_list`.

A capacidade é reconhecida pela definição registrada da ferramenta, não pelo
nome escrito pelo modelo.

`job_kill` e mutações de goal não recebem capacidade read-only.

### 12.5 Local HTTP Timeout

Local:

```text
runtime/patches/local-http-timeout/
```

O DSH pode configurar watchdogs de 900000 ms, mas o transporte Node/Undici
podia encerrar o request antes disso durante prefill sem streaming.

O patch aplica timeouts maiores somente ao origin loopback configurado,
preservando:

- abort signals;
- TLS;
- conteúdo da request;
- política de redirects fora do origin.

---

## 13. Jobs gerenciados

Esperar um job ativo é diferente de repetir uma investigação.

O padrão recomendado é:

```text
job_output(job_id, wait=true, wait_ms≈30000)
```

Quando o executor reconhece a espera de um job realmente ativo:

- ela não cria progresso artificial;
- ela não limpa falhas anteriores;
- ela não conta como repetição de investigação;
- ela não cancela o job ao expirar.

`waitExpired:true` significa que o período de espera terminou com o job ainda
ativo.

A primeira coleta terminal pode ser tratada como observação válida. Releituras
repetidas de um job já concluído voltam a ser limitadas normalmente.

---

## 14. Timeout e diagnóstico

Após um timeout real de executor, o guard entra em modo de diagnóstico.

Defaults atuais:

- no máximo 3 chamadas diagnósticas;
- no máximo 2 minutos.

Somente observadores reconhecidos pelo executor podem furar as restrições
read-only apropriadas.

Um segundo timeout durante diagnóstico encerra a estratégia; compactação ou
texto do modelo não renovam esse orçamento.

---

## 15. Verificação de metas

O profile `robust-local` inclui:

- `dsh-goal-verification`;
- `dsh-verification`.

A configuração atual usa `mode: enforce`.

Para trabalhos relevantes, a intenção é aproximar a execução de:

```text
pedido
→ contrato/intenção
→ implementação
→ evidência
→ oráculos/verificação
→ conclusão
```

O sistema captura evidências e evita que uma simples alegação do modelo seja
tratada como prova de conclusão.

---

## 16. Memória persistente

A camada persistente atual é **dsh-memory 0.7.1**.

Ela é instalada como dependência dos profiles:

- `web`;
- `robust-local`.

O `AGENTS.md` estabelece o uso das operações:

| Operação | Uso |
|---|---|
| `memory_search` | recuperar contexto durável |
| `memory_write` | criar fato durável |
| `memory_update` | atualizar valor canônico |
| `memory_review` | curadoria/manutenção |
| `memory_stats` | diagnóstico |

O modelo não deve usar memória persistente para estado transitório de tarefas,
logs ou segredos.

O antigo plugin Memento foi removido do harness atual.

---

## 17. Skills globais

Existem **24 skills globais** em `dsh/skills/`.

| # | Skill | Função |
|---:|---|---|
| 1 | `acompanhamento` | esperar jobs e verificar término real |
| 2 | `apresentacoes-template` | preencher PPTX baseado em template |
| 3 | `compressao-midia` | comprimir mídia com limites medidos |
| 4 | `configuracoes-estruturadas` | editar JSON/YAML/TOML de forma delimitada |
| 5 | `context-guard` | política de contexto e loop |
| 6 | `dados-tabulares` | transformar/reconciliar dados tabulares |
| 7 | `diagnostico-servicos-logs` | diagnóstico read-only de serviços/logs |
| 8 | `documentos-template` | preencher DOCX baseado em template |
| 9 | `graficos-locais` | gerar gráficos a partir de tabelas |
| 10 | `imagens-lote` | converter/redimensionar imagens em lote |
| 11 | `jornadas-navegador` | executar jornadas curtas de browser |
| 12 | `local-single-agent` | execução explícita sem delegação |
| 13 | `midia-local` | operações locais com áudio/vídeo |
| 14 | `organizacao-arquivos` | cópia/rename em lote |
| 15 | `paginas-estaticas` | páginas HTML/CSS pequenas |
| 16 | `pdf-utilidades` | inspeção/transformação de PDF |
| 17 | `pesquisa-fontes` | pesquisa externa delimitada com fontes |
| 18 | `planilhas-locais` | edição de XLSX |
| 19 | `prism-modpack` | criação/correção de modpack Prism |
| 20 | `quebra-de-loop` | quebrar investigação redundante |
| 21 | `sqlite-local` | consultas SQLite read-only |
| 22 | `testes-api` | teste delimitado de endpoints HTTP |
| 23 | `tool-first` | investigação determinística primeiro |
| 24 | `verificacao-projeto` | descobrir e executar verificações existentes |

Skills específicas de preset existem separadamente, por exemplo
`anti-investigacao-redundante` e `auditoria-visual` no
`local-robust-9b`.

---

## 18. Plugins versionados

Existem **20 diretórios de plugins** em `dsh/plugins/`:

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

Nem todos são necessariamente carregados em todo profile.

`dsh-memory` não aparece nessa lista porque é uma dependência externa fixada
nos `package.json` dos profiles.

---

## 19. Modelos

### Robust local

O profile robusto registra:

| Provider | Modelo | Janela configurada | Output cap |
|---|---|---:|---:|
| LM Studio | `ornith-1.5-9b` | 131072 | 24576 |
| LM Studio | `qwen3.8-27b-gsq-rco` | 64000 | 12000 |

O Ornith é o default do profile.

O plugin `dsh-qwen-defaults` faz routing/defaults específicos do Qwen quando o
preset de 27B está ativo.

---

## 20. Serviços externos locais

O harness depende de alguns serviços fora do snapshot.

### LM Studio

```text
http://127.0.0.1:1234/v1
```

### SearXNG

```text
http://127.0.0.1:8888
```

### Browser tool

```text
http://127.0.0.1:8731
```

Os binários/modelos desses serviços não são versionados aqui.

---

## 21. Testes

O repositório contém suites específicas para componentes críticos.

### Context Guard

```text
dsh/plugins/dsh-context-guard/tests/
├── client.test.mjs
├── job-observation.test.mjs
├── policy.test.mjs
└── preset-policies.test.mjs
```

### Runtime patches

```text
runtime/patches/job-observation/tests/runtime.test.mjs
runtime/patches/checkpoint-compaction/tests/checkpoint.test.mjs
runtime/patches/compaction-progress/tests/progress.test.mjs
runtime/patches/goal-round-compaction/tests/runtime.test.mjs
runtime/patches/local-http-timeout/tests/transport.test.mjs
```

Os testes de patches usam, quando aplicável, objetos reais do runtime DSH e
servidores locais determinísticos para reproduzir falhas.

---

## 22. Restore e integridade

`restore-dsh.sh` oferece:

```text
snapshot
restore
verify
```

O restore:

- usa o runtime travado no lockfile;
- preserva instalação anterior em backup;
- materializa marcadores de caminho;
- reinstala profiles;
- aplica patches;
- valida hashes;
- rejeita conteúdos de runtime desconhecidos.

Os aplicadores de patch são idempotentes e mantêm backup do original quando
apropriado.

---

## 23. Snapshot e privacidade

O snapshot exclui intencionalmente:

- sessões;
- histórico;
- caches;
- credenciais;
- `.env*`;
- auth files;
- `credentials*`;
- `node_modules`;
- `*.jsonl`;
- caches Python.

`workspace.json` tem associações de sessões removidas antes de ser versionado.

Essa filtragem não equivale a uma auditoria genérica de segredos. Um token
colocado em um arquivo com nome inesperado ainda pode ser versionado; portanto
o diff do snapshot deve ser revisado antes do push em repositório público.

---

## 24. Permissões

A configuração atual define:

```yaml
permission:
  defaultPreset: danger-full-access
```

O objetivo é permitir operação agentic local completa.

É importante distinguir:

- Context Guard controla loops/execução redundante;
- verification controla alegações de conclusão;
- permissões controlam autoridade;
- nenhum desses mecanismos, isoladamente, equivale a sandbox forte.

---

## 25. Configuração duplicada e política efetiva

Algumas políticas aparecem em mais de um arquivo:

```text
dsh/settings.yaml
dsh/cordis.patch.yml
dsh/profiles/robust-local/settings.yaml
dsh/profiles/robust-local/cordis.patch.yml
preset.yml
agent.cordis.yml
```

Isso é consequência da composição do DSH, mas cria risco de documentação
desatualizada.

Regra operacional:

> quando houver divergência, diagnostique a precedência e use a política
> efetivamente exposta pelo runtime, não um valor isolado encontrado em um
> arquivo.

---

## 26. Estado atual resumido

| Componente | Estado |
|---|---|
| DSH | `0.1.5-rc.2` |
| Profiles | 3 |
| Presets | 6 |
| Skills globais | 24 |
| Plugins em `dsh/plugins` | 20 |
| Runtime patches | 5 |
| Memória persistente | DSH-memory 0.7.1 |
| Modelo robusto default | Ornith 1.5 9B |
| Backend local | LM Studio |
| Pesquisa | SearXNG |
| Subagents no Robust 9B | desabilitados |
| Ralph no Robust 9B | desabilitado |
| Workflow genérico no Robust 9B | desabilitado |
| Verificação | enforce |
| Permission preset | danger-full-access |

---

## 27. Referências internas

- `README.md` — visão geral.
- `INSTALACAO.md` — instalação e restauração.
- `dsh/AGENTS.md` — política global.
- `dsh/cordis.patch.yml` — patch global.
- `dsh/profiles/robust-local/` — composição robusta.
- `dsh/presets/local-robust-9b/` — preset principal do Ornith.
- `dsh/plugins/dsh-context-guard/` — proteção determinística.
- `runtime/patches/` — patches locais do runtime.
- `restore-dsh.sh` — snapshot/restore/verify.
- `HANDOFF.md` — registro histórico; não é fonte canônica da configuração
  atual.
