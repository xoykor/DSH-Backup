---
name: midia-local
description: Inspecionar, cortar trechos, extrair áudio e converter arquivos locais de áudio e vídeo com FFmpeg, verificando duração, codecs e decodificação.
---

Use para operações locais com duração/início explícitos. Leia [o contrato](references/contrato.md) e execute `python3 scripts/media.py --spec pedido.json` a partir desta skill, ou usando o caminho absoluto do script.

`probe` inspeciona sem alterar. Demais operações preservam o original, recusam sobrescrita e verificam decodificação do resultado antes de publicar. FFmpeg e ffprobe precisam estar no PATH; encoders são verificados na instalação. O timeout é total para todos os subprocessos.

O JSON informa codecs, dimensões e decisões de rotação/aspecto. Explique ao usuário quando houver seleção só dos primeiros streams, normalização de rotação ou exclusão de metadados. Para meta de tamanho, use a skill `compressao-midia` quando disponível; esta skill faz transformações, sem prometer compactação.
