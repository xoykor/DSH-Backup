# Release flow — AppImage do Downloader

## Onde vive o build
- Workflow: `.github/workflows/appimage.yml` (evento `workflow_dispatch`, push em `master`, tags `v*`).
- Passo "Montar AppImage" roda `./packaging/build-appimage.sh` com env:
  - `LINUXDEPLOY`, `APPIMAGETOOL` (AppImages *continuous* do GitHub), `YTDLP_BINARY`, `FFMPEG_BINARY=/usr/bin/ffmpeg`, `FFPROBE_BINARY=/usr/bin/ffprobe`, `APPIMAGE_OUTPUT_DIR=$GITHUB_WORKSPACE/dist`.
- Sai `dist/Downloader-x86_64.AppImage` + `.sha256`; publica artefato `Downloader-AppImage`.

## Por que NÃO buildar localmente
- O CI roda em Ubuntu com o mesmo `build-appimage.sh`, mas sem o problema do `.relr.dyn`:
  - Este sistema (CachyOS/Arch) tem binutils 2.47/glibc que emitem seções `.relr.dyn` (SHT_RELR=0x13).
  - O `linuxdeploy-x86_64.AppImage` *continuous* traz um **binutils 2.35** embutido; seu `strip` não consegue ler `.relr.dyn`.
- `build-appimage.sh` resolve com: pré-strip das libs de runtime para `$appdir/usr/lib` + flag `--deploy-deps-only "$appdir/usr/lib"` (linuxdeploy usa as cópias já limpas e não re-copia os originais com `.relr.dyn`). O shim `packaging/.bin/linuxdeploy` injeta `--strip no` (essa versão do linuxdeploy não tem essa flag → o shim só serve como pass-through).

## Disparar a build
```bash
git add packaging/build-appimage.sh packaging/.bin/   # commit antes!
git commit -m "packaging: ... workaround relr.dyn ..."
gh workflow run appimage.yml
# corrida em https://github.com/xoykor/Downloader/actions/runs/<ID>
```

## Publicar uma release (o passo que faltava)
Dispatch em `master` **não** cria release — o passo "Publicar GitHub Release" tem
`if: startsWith(github.ref, 'refs/tags/')`, e em dispatch `github.ref == refs/heads/master`.

Para publicar: criar + pushar a próxima tag. Após v0.2.3 → v0.2.4:
```bash
git tag v0.2.4 && git push origin v0.2.4
```
- O evento `on.tags: ["v*"]` dispara uma corrida nova com `headBranch == refs/tags/v0.2.4`.
- Nessa corrida, o passo "Publicar GitHub Release" roda e cria a release `gh release create vX.Y.Z dist/... --generate-notes`, anexando AppImage + `.sha256`.

## Verificar / monitorar
```bash
# status da corrida de tag (headBranch = nome da tag)
gh run list --branch v0.2.4 --json number,status,conclusion | python3 -c "import json,sys;[print(x['number'],x['status']) for x in json.load(sys.stdin)]"
gh run view <ID> --json status,conclusion
# artefato (só após sucesso)
gh run download <ID> --path dist/Downloader-x86_64.AppImage*
# releases existentes
gh release list --limit 5 --json tagName,name,isLatest
```

## Commit-message alternativo para release
Um commit com `[release-vX.Y.Z]` dispara o passo "Publicar release solicitada pelo commit" (evento push), que cria a tag se não existir e sobe os artefatos. Útil quando já há uma corrida em `master`; mas o caminho mais direto é push da tag.
