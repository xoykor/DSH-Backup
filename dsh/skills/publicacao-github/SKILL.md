---
name: "publicacao-github"
description: "Publish changes to your own open-source repos on GitHub — detect whether release is CI-automated or manual, bump version per the existing tag convention, create the annotated tag using a full 40-char SHA (never an abbreviation that can collide with an existing ref name), and attach build artifacts to a GitHub Release. Use when asked to push + tag/release an OSS project; not for issues, PRs, reviews, or CI debugging.\n\nPublicar mudanças nos seus próprios repositórios open-source no GitHub — detectar se a release é automatizada por CI ou manual, subir versão pela convenção da última tag, criar a tag anotada com SHA de 40 caracteres (nunca abreviação que pode colidir com nome de ref existente) e anexar artefatos à Release do GitHub. Use quando pedir para push + tag/release um projeto OSS; não é para issues, PRs, revisões nem depuração de CI."
author: "dsh-skill-curator"
version: "0.1.0"
---
# Publicação no GitHub (tag + release)

## Objetivo / quando usar
Publicar mudanças dos **seus próprios repositórios open-source** no GitHub: subir versão pela convenção da última tag, criar a tag anotada e garantir que o artefato de build chegue à Release. Use quando o pedido seja "push + nova tag/release", "criar release vX.Y.Z" ou similar. Não é para issues, PRs, revisões nem depuração de CI.

## Passo 1 — Descubra o fluxo de release ANTES de agir
- Leia `.github/workflows/` inteiro. Identifique se existe um workflow que dispara **build + publicação em push de tag `v*`** (ex.: `appimage.yml`, `release.yml`). Um workflow só de testes/formatting (`cmake.yml`) NÃO publica nada.
- Se houver CI que faz upload dos assets ao push da tag → seu trabalho é apenas **commit + criar a tag**; a CI constrói e publica. Não tente buildar localmente.
- Se não houver CI de release → é **manual**: você builda o artefato localmente e sobe para uma GitHub Release.
- Localize a recipe de build (ex.: `build-appimage.sh`, `AppRun`) — os artefatos normalmente NÃO são committados; a recipe vive no tree mas o binário não.

## Passo 2 — Convenção de versão
- Descubra a última tag real: `git describe --tags` local, ou `gh api repos/{owner}/{repo}/releases/latest`. Não invente número nem confie em memória sem confirmar.
- Bump menor após tag sem-pré: `v0.0.39` → `v0.0.40`. Confirme que a tag de destino ainda não existe antes de criar.

## Passo 3 — Criar a tag anotada (pitfall crítico)
- Use sempre **SHA completo de 40 caracteres** ou ref explícito: `git tag -a -m "msg" <sha40>`. Nunca abreviação curta.
- **Pitfall:** uma abreviação (ex.: `c99b6a6`) pode resolver para um **NOME DE REF existente** em vez do commit → a tag é criada no lugar errado OU o comando retorna 0 mas falha silenciosamente. Sintomas: `git tag -l 'vX.Y.Z'` vazio, `git cat-file -t vX.Y.Z`/peel falham apesar de "create OK" impresso.
- **Causa comum:** arquivo acidental `.git/refs/tags/<sha>` (contém um SHA) polui a resolução do git. Diagnosticar: `ls -la .git/refs/tags; cat .git/refs/tags/*`.
- **Correção:** deletar o ref acidental (`git update-ref -d refs/tags/<nome>`) e criar a tag com o SHA de 40 caracteres no HEAD. Verificar depois: `git show vX.Y.Z | head`, `git tag -l vX.Y.Z`.

## Passo 4 — Build do artefato (ex.: AppImage)
- Se CI faz build: push commit+tag dispara o workflow; acompanhe com `job_output` e verifique a URL dos assets na Release quando concluir.
- Se manual: rode a recipe local (ex.: `build-appimage.sh --version <tag>`) → gera `.AppImage` + checksum. Suba para a Release via `gh release upload vX.Y.Z caminho/asset`.

## Passo 5 — Autenticação antes de side-effects
- Verifique identidade/scope: `gh auth status` (push/tag precisam de `repo`, e publicação por CI de `workflow`). Sem token, use o credencial helper do gh ou SSH. Não peça escalonamento de sandbox.

## Passo 6 — Verificação final
- Tag aponta para o commit certo; artefato presente na Release; workflow concluído sem erro. Só então declare concluído.

### Referências
- `references/linux-wallpaperengine-release.md` — fluxo de release + pitfall git confirmado deste projeto (sessão 2026-10).
