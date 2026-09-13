# Documentação da Instalação Live DSH/Codex

Guia completo da instalação **live** do DeepSeek Harness (`@deepseek-ai/dsh`
0.1.5-rc.2) e do Codex que roda nesta máquina. Este arquivo descreve o estado
capturado da instalação real (`~/.dsh` e `~/.codex`).

> **Autoridade:** a instalação live é a fonte da verdade. Os valores abaixo são
> os que estão em execução agora, não apenas os do backup antigo.
>
> Este documento foi gerado como parte do repositório de backup. Ele descreve o
> conteúdo real e pode ser usado para entender, migrar ou restaurar esta
> instalação.

---

## 1. Modelo de Autoridade

- **Live** (`~/.dsh`, `~/.codex`) = fonte da verdade (o que está em execução).
- **Backup** (este repositório) deve espelhar o live, aplicando normalização de
  caminhos e excluindo segredos/sessões/cache.
- O snapshot oficial (`restore-dsh.sh snapshot`) faz a cópia live→backup com
  normalização automática; não há flag de dry-run.

---

## 2. Layout da Instalação Live

```
~/.dsh/            # configuração do DSH (autoridade)
├── AGENTS.md              # instruções/contexto do agente (sistema)
├── settings.yaml          # modelos, janelas, políticas de contexto/plugins
├── cordis.patch.yml       # patch de política de modelo (ornith/qwen defaults)
├── workspace.json         # estado da área de trabalho
├── skills/                # 20 skills
├── profiles/              # 3 perfis (headless, robust-local, web)
├── plugins/               # 8 plugins
├── bridges/               # 1 bridge (FreeDeepseekAPI-EN)
└── .agent-presets/        # 5 presets de agente

~/.codex/             # instalação do Codex (também presente nesta host)
├── config.toml           # configuração principal do Codex
├── computer-use/          # integração de uso de computador
├── rules/                 # regras do Codex
├── skills/                # skills do Codex
└── plugins/cache/personal # cache de plugins do Codex
```

Diretórios **não** versionados (intencionalmente excluídos): `secrets`,
`sessions`, `storages`, `attachments`, `backups`, `compaction-*`,
`node_modules`. Ver `.gitignore`.

---

## 3. Arquivos de Configuração Raiz

### 3.1 settings.yaml
Define os modelos e as políticas de contexto/plugins. Pontos-chave:

- **Modelos remotos (DeepSeek):**
  - `deepseek-v4-flash` — DeepSeek-V4-Flash
  - `deepseek-v4-pro` — DeepSeek-V4-Pro
- **Modelos locais:**
  - `ornith-1.5-9b` — modelo local de raciocínio (default do agente)
  - `qwen3.8-27b-gsq-rco` — modelo local alternativo
- **Modelo padrão do agente** (`agent-default-model.model`): `ornith-1.5-9b`.
- Política de janela: raised to the model's own cap (ornith).

### 3.2 cordis.patch.yml
Patch de política de modelo aplicado sobre o core:

- Define políticas por contexto:
  - `model: ornith-1.5-9b`
  - `model: qwen3.8-27b-gsq-rco`
- Request defaults injetados via plugin:
  - `/home/x/.dsh/plugins/dsh-qwen-defaults/lib/index.js` (`qwen-request-defaults`)

### 3.3 AGENTS.md
Sistema-prompt/contexto do agente (política de segurança, loop-safety, etc.).

### 3.4 workspace.json
Estado da área de trabalho (não versionado por segredos/sessões).

---

## 4. Modelos

| ID | Nome | Tipo | Papel |
|----|------|------|-------|
| `deepseek-v4-flash` | DeepSeek-V4-Flash | remoto | rápido / geral |
| `deepseek-v4-pro` | DeepSeek-V4-Pro | remoto | raciocínio profundo |
| `ornith-1.5-9b` | ornith 1.5 9B | local | **default do agente**, raciocínio |
| `qwen3.8-27b-gsq-rco` | qwen3.8 27B | local | alternativo |

---

## 5. Perfis (`profiles/`)

- `headless` — execução sem interface interativa.
- `robust-local` — perfil robusto com modelo local.
- `web` — perfil orientado a navegação/web.

---

## 6. Presets de Agente (`.agent-presets/`)

5 presets que parametrizam o agente para cenários distintos:

1. `local-models`
2. `local-models-ptc`
3. `local-robust-9b`
4. `ornith-gemini-architect`
5. `relay-codex`

---

## 7. Plugins (`plugins/`) — 8

| Plugin | Função (resumo) |
|--------|-----------------|
| `dsh-architect` | Planejamento/arquitetura de tarefas. |
| `dsh-context-guard` | Guardião de contexto (protege janelas/contexto). |
| `dsh-global-token-meter` | Medição global de tokens na sessão. |
| `dsh-goal-verification` | Verificação de metas/objetivos. |
| `dsh-qwen-defaults` | Defaults do Qwen (injetado via cordis.patch.yml). |
| `dsh-tool-browser` | Wrapper de ferramentas de navegador. |
| `dsh-verification` | Verificação geral (com README, CHANGELOG, PROJECT_STATUS). |
| `dsh-web-search-searxng` | Busca web via instância SearXNG. |

> Descrições completas vivem nos próprios `README.md`/`SKILL.md` de cada plugin.

---

## 8. Bridges (`bridges/`)

- `FreeDeepseekAPI-EN` — bridge para a API gratuita DeepSeek (inglês).

---

## 9. Skills (`skills/`) — 20

| Skill | Foco |
|-------|------|
| `apresentacoes-template` | Templates de apresentações. |
| `compressao-midia` | Compressão de mídia. |
| `configuracoes-estruturadas` | Configurações estruturadas. |
| `context-guard` | Proteção de contexto. |
| `dados-tabulares` | Dados tabulares. |
| `diagnostico-servicos-logs` | Diagnóstico via logs de serviços. |
| `documentos-template` | Templates de documentos. |
| `graficos-locais` | Gráficos locais. |
| `imagens-lote` | Processamento em lote de imagens. |
| `jornadas-navegador` | Jornadas/navegação no navegador. |
| `local-single-agent` | Agente único local. |
| `midia-local` | Mídia local. |
| `organizacao-arquivos` | Organização de arquivos. |
| `paginas-estaticas` | Páginas estáticas. |
| `pdf-utilidades` | Utilidades PDF. |
| `pesquisa-fontes` | Pesquisa com fontes. |
| `planilhas-locais` | Planilhas locais. |
| `sqlite-local` | SQLite local. |
| `testes-api` | Testes de API. |
| `verificacao-projeto` | Verificação de projeto. |

---

## 10. Instalação do Codex (`~/.codex/`)

Instalação presente nesta host. Arquivos principais:

- `config.toml` — configuração principal.
- `computer-use/` — integração de uso de computador.
- `rules/` — regras do Codex.
- `skills/`, `plugins/cache/personal` — skills e cache de plugins.
- `installation_id`, `version.json` — metadados da instalação.

> Segredos (`auth.json`), sessões, caches e bancos SQLite **não** são versionados.

---

## 11. Pré-requisitos para Restaurar / Reautenticar

Após restaurar este backup:

1. Instale o runtime com `restore-dsh.sh restore`.
2. **Re-autentique** — segredos/sessões não foram backeadados (por design).
3. Forneça os valores de `secrets/required-env.example` do repositório.
4. Caminhos são normalizados (`$HOME`, `$CODEX_HOME`, `$DSH_HOME`) no snapshot;
   a restauração reverte as substituições.

---

## 12. Notas e Cuidados

- **Backup espelha o live**, não preserva apenas valores antigos do backup.
- Valores presentes só no backup antigo podem ter sido descartados pelo snapshot
  (ex.: override manual `maxTurnTokens: 120000` em `cordis.patch.yml`).
- Segredos, sessões e `node_modules` são intencionalmente excluídos do versionamento.
- `.gitignore` exclui runtime/secrets/cache; o snapshot aplica excludes adicionais
  (`node_modules`, `.env*`, `auth.json/auth.*.json`, `credentials*`, `__pycache__`,
  `*.pyc`, `*.jsonl`).
