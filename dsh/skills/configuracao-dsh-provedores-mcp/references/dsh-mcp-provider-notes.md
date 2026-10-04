# Notas de campo — provedores LLM e servidores MCP externos no dsh

Conhecimento condensado da sessão de setup do pipeline RAG com Ornith + LM Studio.
Reutilizar como recipe, não redescobrir. Nomes exatos podem variar; confirmar na execução.

## 1. Recipe: registrar servidor MCP externo (stdio)

Arquivo-alvo: `~/.dsh/profiles/web/cordis.patch.yml` (backup antes de editar).
Mecanismo: entrada `- id:` com bloco `insert:` que aponta para o perfil `web`.

Passos:
1. Backup: `cp ~/.dsh/profiles/web/cordis.patch.yml "~/.dsh/profiles/web/cordis.patch.yml.bak-$(date +%Y%m%d-%H%M%S)"`.
2. Adicionar a entrada (preservando as existentes) — usar append/insert no fim da lista de `- id:`.
3. Validar YAML: `python -c "import yaml,sys; yaml.safe_load(open(sys.argv[1]))" ~/.dsh/profiles/web/cordis.patch.yml`.

## 2. Snippet completo (servidor stdio)

```yaml
- id: mcp-client-rag
  insert:
    - target: web
      patch:
        - op: add
          path: /mcpClientServers/insert/0
          value:
            serverName: rag
            transport: stdio
            command: npm
            args: ["run", "mcp:stdio"]
            cwd: __HOME__/projects/rag-v2
```

- `serverName`: nome que vira o prefixo das tools (`mcp__rag__*`).
- `command`/`args`: processo real do servidor MCP (aqui `npm run mcp:stdio`).
- `cwd`: diretório do repo com `node_modules` instalado.
- `@deepseek-ai/dsh-mcp-client` resolve no build; confirmar sem erro via dump (ver §4).

## 3. Provedor LLM local já pré-configurado

Em `~/.dsh/settings.yaml`:
- `llm-pi-ai.providers.lmstudio`: `baseURL: http://127.0.0.1:1234/v1`, `api: openai-responses`.
- Modelo padrão: `agent-default-model.provider: lmstudio, model: <id-exato>`.
- Provider ID real = **`llm-pi-ai`**.
- Confirmação estática na composição do perfil web: políticas de contexto das linhas ~263–276 do dump.

## 4. Verificação sem boot (estática)

```bash
dsh --profile web --dump-config > /tmp/dsh_dump.txt 2>&1   # imprime e sai, exit 0
grep -n "mcp-client-rag" /tmp/dsh_dump.txt                # entry composta?
```
Prova que a config está presente na composição do perfil — não prova execução.

## 5. Registro de erros confirmados

- **Headless aborta**: `dsh --profile headless` → `cannot get property "agentPresets" without inject`.
  Headless não tem `agentPresets`; verificação agêntica ao vivo só em web-host interativo.
- **Conflito de porta**: segundo `dsh --profile web` enquanto o chat roda →
  `EADDRINUSE: address already in use 127.0.0.1:3080`. O host em 3080 hospeda este chat; não iniciar segunda instância web.
- **Timeout do stdio**: servidor rag sai com exit 0 após ~200s (espera stdin por design); usar `job_output`/timeout, não busy-poll.

## 6. Verificação ao vivo (nova sessão web)

1. `dsh --profile web`, abrir Web UI (~`http://localhost:8080`).
2. Esperar ~30–60s para o discovery do stdio completar.
3. Settings → MCP servers: servidor **Connected**, tools esperados (`rag_search`/`rag_answer`).
4. Chat: "Quais ferramentas MCP você tem disponíveis?" → lista `mcp__rag__*`.
5. Teste indireto (pergunta sobre um arquivo/fixtures) → modelo chama o tool e cita a resposta; pergunta sem base → admitir ignorância.
6. Se **Error**: `cd <cwd> && npm run mcp:stdio` para ver o erro real (servidor já confirmado iniciando limpo).

## 7. Repos/pacotes (confirmar na execução)

- Repo RAG: espelho público do projeto do Hub LM Studio; clonar direto o repo correto, não `dirty-data/rag-v2` (clona mal no GitHub).
- Workspace pnpm/npm com `mcp:stdio` → `@rag-v2/mcp-server`; depende de `@rag-v2/core`, `@rag-v2/lmstudio-shared` → precisa de install raiz.
