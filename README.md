# DSH Backup / Local Agent Harness

Snapshot declarativo e reproduzível da instalação local do DeepSeek Harness
(DSH), com foco em execução agentic por modelos locais.

O repositório começou como backup de configuração, mas atualmente também
versiona a camada de integração que torna o ambiente reproduzível: perfis,
presets, skills, plugins locais, patches do runtime, bridge, configuração do
Codex e o instalador/restaurador.

## Estado atual

- DSH: `@deepseek-ai/dsh@0.1.5-rc.2`
- Node: `>=22`
- pnpm: `11.26.0`
- profiles: **3**
- presets de agente: **6**
- skills globais em `dsh/skills`: **24**
- diretórios de plugins em `dsh/plugins`: **20**
- patches versionados do runtime: **5**
- memória persistente: **dsh-memory 0.7.1**
- backend local principal: **LM Studio**
- busca web: **SearXNG local**

Os presets robustos são orientados a modelos locais e usam proteção de
contexto, verificação de metas, compactação segura e mecanismos determinísticos
contra loops de ferramentas.

## Arquitetura

```text
DSH 0.1.5-rc.2
├── runtime fixado por lockfile
├── runtime/patches/
│   ├── checkpoint-compaction
│   ├── compaction-progress
│   ├── goal-round-compaction
│   ├── job-observation
│   └── local-http-timeout
├── dsh/
│   ├── AGENTS.md
│   ├── settings.yaml
│   ├── cordis.patch.yml
│   ├── profiles/
│   │   ├── headless
│   │   ├── robust-local
│   │   └── web
│   ├── presets/
│   │   ├── local-models
│   │   ├── local-models-ptc
│   │   ├── local-robust-9b
│   │   ├── local-robust-27b
│   │   ├── ornith-gemini-architect
│   │   └── relay-codex
│   ├── skills/
│   ├── plugins/
│   └── bridges/
└── codex/
```

O perfil `robust-local` atualmente inclui `dsh-context-guard` e
`dsh-memory` como dependências do próprio profile. O perfil `web` também
carrega `dsh-memory`.

## Context Guard

O `dsh-context-guard` não é apenas uma instrução de prompt. Ele atua na
fronteira do executor e acompanha, entre outros sinais:

- pressão de contexto;
- chamadas de ferramenta;
- fingerprints de resultados;
- falhas equivalentes;
- mudanças observáveis no workspace;
- ciclos repetidos de investigação;
- timeouts;
- observação de jobs gerenciados.

Os valores efetivos de janela e limiares são derivados da política ativa do
preset/profile. A mensagem `ACTIVE CONTEXT POLICY` emitida pelo runtime é a
fonte de verdade durante uma sessão; números estáticos na documentação não
devem substituir essa política.

## Restore

Feche processos DSH relevantes e execute, a partir da raiz do repositório:

```bash
./restore-dsh.sh restore
```

O script:

1. instala o runtime fixado pelo `runtime/package-lock.json`;
2. expõe o executável em `~/.local/bin/dsh`;
3. restaura os caminhos gerenciados de `~/.dsh` e `~/.codex`;
4. reinstala os profiles salvos;
5. aplica os patches versionados e verificados por hash;
6. valida os profiles restaurados.

Antes da substituição, os caminhos gerenciados existentes são preservados em
`~/.dsh-restore-backups/<timestamp>/`.

## Snapshot

Para atualizar o repositório a partir da instalação live:

```bash
./restore-dsh.sh snapshot
```

O snapshot usa allowlist e normaliza caminhos dependentes da máquina com:

- `__HOME__`
- `__DSH_HOME__`
- `__CODEX_HOME__`

Sessões, histórico, credenciais, caches, estado do navegador e outros dados
efêmeros não fazem parte do snapshot.

## Verificação

```bash
./restore-dsh.sh verify
```

A verificação confere o runtime esperado, a configuração salva, profiles e
patches conhecidos.

## O que não é versionado

Por projeto, este repositório não deve conter:

- credenciais e tokens;
- sessões/conversas;
- caches;
- estado do navegador;
- bancos de histórico;
- modelos do LM Studio;
- `node_modules` gerados;
- dados efêmeros de execução.

Após um restore, reautentique integrações externas e forneça variáveis de
ambiente/segredos fora do Git.

## Documentação

- [INSTALACAO.md](./INSTALACAO.md) — layout da instalação, profiles, presets,
  modelos e componentes ativos.
- [DOCUMENTACAO-DSH.md](./DOCUMENTACAO-DSH.md) — arquitetura técnica,
  Context Guard, compactação, jobs, memória e patches do runtime.
- [HANDOFF.md](./HANDOFF.md) — registro histórico de decisões e sessões de
  manutenção; pode conter contexto antigo e não deve ser tratado como fonte
  canônica da configuração atual.
