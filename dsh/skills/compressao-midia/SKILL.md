---
name: compressao-midia
description: Comprimir imagens, áudio e vídeo locais com qualidade ou meta de tamanho medida, preservando originais e limitando tentativas e tempo total.
---

Leia [o contrato](references/contrato.md) e execute `python3 scripts/compress.py --spec pedido.json`, usando o caminho desta skill. Escolha `kind` explicitamente e um destino novo. Python/Pillow tratam imagem; FFmpeg/ffprobe tratam áudio/vídeo. Os encoders disponíveis são conferidos.

Informe `quality` ou uma meta em bytes/MB; quando ambos aparecem, qualidade é o ponto inicial das tentativas. Reduza dimensões somente se o usuário pedir ou autorizar. Não invente sucesso: `target_met` vem do tamanho real. `target_unmet` pode incluir o melhor arquivo se menor que o original; `not_smaller` mantém somente o original. Metas impossíveis não causam loops: há no máximo 6 tentativas e timeout total.

Não remova originais. JPEG com transparência exige fundo explícito. Reporte bytes antes/depois, redução, meta atingida, limitações e decisões retornadas pelo script. A skill funciona sem importar outra skill.
