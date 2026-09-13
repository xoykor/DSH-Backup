# Handoff — Sessão DSH/Codex Backup + Skills

## Contexto
- Autoridade: **live** (`~/.dsh`, `~/.codex`) é fonte da verdade; backup espelha o live.
- Remote: `origin` → https://github.com/xoykor/DSH-Backup (branch `master`).
- Fluxo: `restore-dsh.sh snapshot` (live→backup, exclui segredos/sessões/cache) → commit → push.

## Concluído (evidência — commits)
- `INSTALACAO.md` — documentação completa da instalação live (skills 20, presets 5, plugins 8, bridge 1, modelos, perfis). Commit `3442fe9`.
- Skill `quebra-de-loop` — disciplina anti-investigação redundante. Commit `04845f2`.
- Skill `acompanhamento` — acompanhar chamadas longas via artefatos duráveis (mtime/tamanho, pgrep/ps) e job_list/job_output. Commit `abbc69d`.
- Skill `declaracao-capacidade` — documentação do guard diagnostic mode; **não** auto-concede capacidade.

## Estado atual
- Goal ativo: `goal-3bfa22ec…` (DSH sync), phase=complete, activation=disarmed.
- Skills funcionais no repo: `quebra-de-loop`, `acompanhamento` (+ 20 skills live).
- Head remoto: `abbc69d…fbe0d6`.

## Decisão pendente
- **declaracao-capacidade**: manter (documenta guard + resolução pelo operador) ou remover/mergear em `quebra-de-loop`? Aguardando usuário.

## Bloqueios
- Diagnostic mode exige capacidade read-only executor explicitamente declarada; `update_goal` não tem campo para isso e approval prompts desativados → agente **não** pode auto-conceder. Resolução = habilitação pelo operador/nível de sessão.
- Goal antigo `goal-3dfc1380…` (Scryfall scrape) referenciado em erro bloqueado; objetivo só parcialmente visível na imagem, e `get_goal` retorna apenas o goal ativo — não dá para editar sem capacidade + objetivo completo.

## Próximas ações
1. Decidir sobre `declaracao-capacidade` (manter/remover).
2. Se retomar Scryfall: operador habilita a capacidade → `update_goal edit goal-3dfc1380…` com objetivo/revision completos.
3. Re-snapshot quando o live mudar; segredos/sessões/cache continuam excluídos (reautenticar após restore).
