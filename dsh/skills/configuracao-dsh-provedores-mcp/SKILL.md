---
name: "configuracao-dsh-provedores-mcp"
description: "Configure LLM model providers and external stdio MCP servers in the DeepSeek Harness (dsh) via its file-based patch mechanism, then verify when tools become callable. Covers the @deepseek-ai/dsh-mcp-client insert: entry, per-profile cordis.patch.yml wiring, lmstudio/llm-pi-ai provider config, async MCP discovery timing, and the headless vs web-host verification gap.\\\\n\\\\nConfigurar provedores de LLM e servidores MCP externos (stdio) no DeepSeek Harness (dsh) pelo mecanismo de patch por arquivo, depois verificar quando as ferramentas ficam invocáveis. Cobre a entrada insert: do @deepseek-ai/dsh-mcp-client, o wiring em cordis.patch.yml por perfil, a config do provedor lmstudio/llm-pi-ai, o timing assíncrono da descoberta MCP e a diferença de verificação entre headless e sessão web-host."
author: "dsh-skill-curator"
version: "1.0.0"
created: "2026-08-09"
---
# Configuração de provedores LLM e servidores MCP externos no DeepSeek Harness (dsh)

Configura provedores de LLM locais (LM Studio, Ollama-style via `llm-pi-ai`) e
servidores MCP externos em **stdio** dentro do dsh. A configuração persiste por
arquivo — não depende da Web UI (que pode não ser acessível headless).

## Use quando

- Pedir para registrar um servidor MCP externo como stdio no dsh (ex.: `rag_search`/`rag_answer`).
- Precisar apontar o modelo do chat para um provedor local (`lmstudio`, baseURL `http://1234/v1`).
- Diagnosticar por que uma ferramenta `mcp__<server>__*` não aparece invocável na sessão atual.

Não é para editar as linhas de loader embutidas do dsh nem para perguntas gerais sobre JSON/YAML.

## Mecanismo oficial: entrada `insert:` no patch do perfil

O dsh injeta servidores MCP externos via plugin `@deepseek-ai/dsh-mcp-client`,
wireado por uma entrada `insert:` em **`~/.dsh/profiles/<perfil>/cordis.patch.yml`**
(não um bloco `- id:` arbitrário no topo). Cada servidor stdio é uma linha:

```yaml
- id: mcp-client-rag
  insert:
    - target: web            # perfil que herda (ex.: web)
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

- `target`: perfil que compõe a entrada (geralmente `web`).
- `command`/`args`/`cwd`: processo stdio real do servidor MCP.
- Valide o YAML com um parser antes de aplicar (`python -c "import yaml,sys; yaml.safe_load(open(sys.argv[1]))" arquivo.yml`).

## Provedor LLM local (lmstudio / llm-pi-ai)

O provedor costuma já estar pré-configurado em **`~/.dsh/settings.yaml`**:
- `llm-pi-ai.providers.lmstudio`: `baseURL: http://127.0.0.1:1234/v1`,
  `api: openai-responses`, lista de modelos (incluindo o ID exato do modelo).
- Modelo padrão via `agent-default-model.provider: lmstudio, model: <id-exato>`.
- Provider ID real = **`llm-pi-ai`** (não `lmstudio`).

## Timing crítico da descoberta MCP (pitfall principal)

As ferramentas `mcp__<server>__*` são descobertas **assincronamente no boot do host**,
não injetadas mid-session. Consequências:

- Uma sessão já rodando **não** recebe a injeção depois; o tool não estará no conjunto
  de funções invocáveis desta sessão, mesmo com a config correta e composta.
- Verificação ao vivo exige uma **nova sessão web-host interativa** (`dsh --profile web`),
  seguida de ~30–60s para o discovery completar.
- Confirmação estática sem boot: `dsh --profile web --dump-config` (imprime e sai, ~600+ linhas). Grep a entrada do servidor (`mcp-client-<server>`) **e** confirme que o módulo resolve sem aviso — ex.: as linhas com `mcp-client-rag` presentes + `@deepseek-ai/dsh-mcp-client` resolvido. Prova config composta, não execução.

## Referência autoritativa no checkout do runtime

O esquema real do servidor MCP stdio e a row de exemplo vivem dentro do checkout
do runtime instalado (`__HOME__/.local/lib/dsh-runtime-*/node_modules/@deepseek-ai/`):
- `config-catalog.md` — seção **MCP server schema** (~linha 1420), com os campos esperados.
- `mcp-memory.md` — row de exemplo completa com a entrada `insert:` + stdio.

Ler antes de inventar o formato; não confiar em blocos `- id:` ilustrativos de handoffs.

## Receita verificada nesta sessão (repo RAG + servidor stdio)

- **Clone**: `git clone https://github.com/AcidicSoil/rag-v2` em `~/projects`. O espelho público que funciona é **AcidicSoil/rag-v2** — o `dirty-data/rag-v2` do Hub clona mal.
- **Instalar** (workspace pnpm/npm; o MCP depende de `@rag-v2/core` e `@rag-v2/lmstudio-shared`): `npm install` no repo → ~170 pacotes.
- **Rodar servidor stdio**: `cd ~/projects/rag-v2 && npm run mcp:stdio`. Sai com exit 0 apenas porque o timeout matou o processo (o servidor espera no stdin por design); saída limpa sem erros de embedding no boot.
- **Modelos no LM Studio** já presentes após reboot: `ornith-1.5-9b-dsh-agentic-gpt-5.6-sol-distill` (LLM) + 2 embeddings (`text-embedding-qwen3-embedding-0.6b`, `text-embedding-nomic-embed-text-v1.5`).

## Pitfalls confirmados

1. **Perfil errado**: a entrada vive em `profiles/web/cordis.patch.yml`. Bootar outro
   perfil (ex.: `headless`) não a compõe.
2. **Gap headless**: perfis sem `agentPresets` abortam com
   `cannot get property "agentPresets" without inject`. Verificação agêntica ao vivo só
   funciona em sessão web-host interativa.
3. **Conflito de porta**: rodar um segundo `dsh --profile web` enquanto o chat já roda
   falha com `EADDRINUSE address already in use 127.0.0.1:3080`. O host que segura 3080
   é o que hospeda este chat — não iniciar uma segunda instância web (um reboot do PC
   não libera a porta; o processo já está vivo).
4. **Não confiar em nomes ilustrativos do handoff**: pacotes/repos/nomes exatos podem variar; confirmar cada URL e nome de pacote na execução (ex.: `dirty-data/rag-v2` no Hub clona mal — o espelho público que funciona é **AcidicSoil/rag-v2**; instale a workspace com `npm install` e rode o servidor stdio via `npm run mcp:stdio`, que executa `@rag-v2/mcp-server` → `npx -y tsx src/stdioServer.ts`). O servidor já foi confirmado iniciando limpo (espera no stdin por design; exit 0 só porque um timeout matou o processo).

## Fluxo de verificação ao vivo (nova sessão web)

1. Bootar: `dsh --profile web`, abrir a Web UI (~`http://localhost:8080`).
2. Esperar ~30–60s para o discovery do stdio.
3. **Settings → MCP servers**: servidor com status **Connected**, tools esperados.
4. Chat: perguntar quais ferramentas MCP existem → lista `mcp__<server>__*`.
5. Teste indireto (pergunta sobre um arquivo/fixtures) → o modelo deve chamar o tool e
   citar a resposta esperada; pergunta sem base → admitir ignorância (answerability gate).

Se aparecer **Error**, rodar manualmente no terminal para ver o erro real:
`cd <cwd-do-repo> && npm run mcp:stdio`. O servidor já foi confirmado iniciando limpo.

## Referência detalhada

Ver `references/dsh-mcp-provider-notes.md` — recipe de configuração, snippet completo,
registro do erro e passos de verificação.

## Lição de verificação desta sessão

A única prova *ao vivo* de tool-calling é uma **nova** sessão web-host interativa após boot — headless aborta com `cannot get property "agentPresets" without inject`. Config composta + backend vivo + servidor stdio rodando = tudo pronto; falta só o discovery assíncrono concluir numa conversa nova.