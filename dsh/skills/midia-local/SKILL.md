---
name: midia-local
description: Inspecionar, cortar trechos, extrair áudio e converter arquivos locais de áudio e vídeo com FFmpeg, verificando duração, codecs e decodificação.
---

Use para operações locais com duração/início explícitos. Leia [o contrato](references/contrato.md) e execute `python3 scripts/media.py --spec pedido.json` a partir desta skill, ou usando o caminho absoluto do script.

`probe` inspeciona sem alterar. Demais operações preservam o original, recusam sobrescrita e verificam decodificação do resultado antes de publicar. FFmpeg e ffprobe precisam estar no PATH; encoders são verificados na instalação. O timeout é total para todos os subprocessos.

O JSON informa codecs, dimensões e decisões de rotação/aspecto. Explique ao usuário quando houver seleção só dos primeiros streams, normalização de rotação ou exclusão de metadados. Para meta de tamanho, use a skill `compressao-midia` quando disponível; esta skill faz transformações, sem prometer compactação.

## Verificando capa/arte embutida — inspecione o arquivo, não tire print

Quando o usuário diz que um áudio "não tem thumb/capa", a causa é o container/arquivo, não a tela do app. **Não capture screenshot do GUI** para responder isso; analise o arquivo baixado diretamente:

- Streams de imagem + tags de capa via ffprobe:
  `ffprobe -v error -show_entries stream=codec_type,index -of json <arquivo>` → capa embutida aparece como stream `data` (APIC no mp3, Vorbis COMMENT_PICTURE no OGG/opus) ou um stream vídeo. Sem stream `data`, não há capa — o app pode ter enviado `--embed-thumbnail --add-metadata`, mas yt-dlp não retornou arte para esse item.
- Confirmação de áudio puro sem capa: `ffprobe -v error -select_streams v:0 -show_entries stream=codec_type -of json <arquivo>` devolve zero/erro quando não há vídeo; não é prova de que falta capa, mas confirma ausência de stream de imagem separado.
- Ponto-chave para conversores (opus/mp3): a capa vive nas tags do container, não como arte visual na interface. Verificar o arquivo em disco responde a dúvida; screenshot da GUI é irrelevante para "está baixando com capa ou não".
