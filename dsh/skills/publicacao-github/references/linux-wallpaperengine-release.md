# Referência: release do linux-wallpaperengine (sessão 2026-10)

Projeto C++ de desktop (Wallpaper Engine). Repo: `xoykor/linux-wallpaperengine` (local `__HOME__/linux-wallpaperengine`). Usuário: xoykor/Fernando.

## Fluxo de release (descoberto nesta sessão)
- **Não há CI que constrói AppImage nem cria releases.** Workflows existentes são manuais:
  - `cmake.yml` → só testes/formatting, não publica nada.
  - `appimage.yml` → dispara em **push de qualquer tag `v*`**; faz build do engine, baixa appimagetool/linuxdeploy, roda `build-appimage.sh --version <tag>`, sobe artefatos e publica via `softprops/action-gh-release`. (Verificar se este workflow ainda está no tree — a sessão encontrou inconsistência: em um ponto parecia "sem CI de AppImage", depois confirmou que existe.)
- Portanto release = **commit + tag anotada**; a CI faz build+publicação. Confirma com `ls .github/workflows/` antes de assumir.

## Recipe de build (não committada como binário)
- `build-appimage.sh`, `AppRun`, README e `.github/workflows/appimage.yml` vivem no tree (presentes em `origin/main`). Artefatos `.AppImage` não são committados.
- Tag de versão embutida via `--version <tag>` na recipe.

## Convenção de versão confirmada
- Última tag remota = **v0.0.39** → próxima = **v0.0.40**. Confirme com `gh api repos/xoykor/linux-wallpaperengine/releases/latest` antes de criar.

## Bug corrigido nesta release (contexto)
- Sintoma: wallpaper some ao app ir fullscreen/maximizado e não volta à área de trabalho.
- Raiz: commit `2fbbd81` ("Release wallpaper GPU resources while covered") nula `m_renderContext` via `.reset()` no branch de pausa, mas o branch de despausar verificava `makeAnyViewportCurrent()` (precisa de contexto vivo) **antes** de `prepareOutputs()` recriá-lo → dead-end eterno.
- Correção: reordenar — chamar `prepareOutputs()` antes do guard `makeAnyViewportCurrent()`. Commits: `4391a57` + `2fbbd81`, já em HEAD/origin/main @ c99b6a6.

## Pitfall git confirmado (evidência real desta sessão)
- `git tag -a -m "msg" c99b6a6` retornou 0 ("create OK") mas a tag NÃO era criada; `git tag -l 'v0.0.40'` vazio e verify falhava.
- Causa: abreviação `c99b6a6` resolveu para um **ref acidental `.git/refs/tags/c99b6a6`** (contém SHA) criado por tentativa quebrada anterior, poluindo a resolução do git.
- Diagnóstico: `ls -la .git/refs/tags; cat .git/refs/tags/*`. Correção aplicada: `git update-ref -d refs/tags/c99b6a6`, depois criar com **SHA de 40 caracteres** no HEAD e verificar (`git show vX.Y.Z | head`).
- Lição durável: sempre usar SHA completo ou ref explícito ao criar tags; nunca abreviação.
