---
name: "appimage-release"
description: "Publish a Downloader AppImage by dispatching the GitHub Actions build (gh workflow run appimage.yml), never building locally. Use when asked to create/publish an AppImage or release for the Downloader project; not for packaging/build-appimage.sh internals alone.\n\nPublicar um AppImage do projeto Downloader disparando a build no GitHub Actions (`gh workflow run appimage.yml`), nunca localmente. Use quando pedir para criar/publicar um AppImage ou release do Downloader; não é só para os detalhes internos de packaging/build-appimage.sh."
author: "dsh-skill-curator"
version: "0.1.0"
---
# Downloader — publicar AppImage via GitHub Actions

Regra de ouro: **criar um AppImage = disparar a build no GitHub Actions, nunca localmente.**
Detalhes do porquê e dos gatilhos de release: `references/release-flow.md`.

## Quando usar
- Pedir para "criar um AppImage", "gerar uma release" ou "publicar o AppImage" do Downloader.
- Verificar status/resultado da corrida, listar artefatos ou releases.
- Corrigir por que "não saiu nova release" (dispatch em master só sobe artefato).

## Fluxo correto (resumido)
1. **Commit** as mudanças antes de disparar — o checkout do Actions pega código commitado; trabalho não commiteado é ignorado.
2. `gh workflow run appimage.yml` → roda em runner Ubuntu remoto, executa `./packaging/build-appimage.sh`.
3. Esse dispatch dispara em `master`: **build + sobe artefato**, mas NÃO publica release (a criação de release só roda quando `github.ref` começa com `refs/tags/`).
4. Para **publicar uma release**: criar e pushar a próxima tag `vX.Y.Z` (ex: depois de v0.2.3 → v0.2.4). O evento `tags: ["v*"]` cria uma corrida nova que **sim** publica a release via o passo "Publicar GitHub Release".
5. Commit `[release-vX]` também dispara release, mas só no evento push (não em workflow_dispatch).

## Comandos gh úteis
- Disparar build: `gh workflow run appimage.yml`
- Ver corrida: `gh run view <ID> --json status,conclusion`
- Corridas na tag (a da release): `gh run list --branch vX.Y.Z --json number,status`
  - A corrida de tag aparece com `headBranch` = nome da tag (ex: `v0.2.4`), não `master`.
- Artefatos: `gh run download <ID> --path dist/Downloader-x86_64.AppImage*`
- Releases: `gh release list`, `gh release view vX.Y.Z`

## Armadilhas conhecidas
- **workflow_dispatch em master ≠ release.** Só sobe o artefato; sem tag, nenhum passo de "Publicar GitHub Release" roda.
- Build local (rodar `./packaging/build-appimage.sh` aqui) não é o caminho — usa binutils 2.47/glibc que emitem `.relr.dyn`, e o linuxdeploy *continuous* tem strip embutido 2.35 que trava nesses `.relr.dyn`. O CI resolve isso com pré-strip das libs + `--deploy-deps-only` (ver `build-appimage.sh`).
- Link da corrida: https://github.com/xoykor/Downloader/actions/runs/<ID>
