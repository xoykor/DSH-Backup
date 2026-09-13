---
name: imagens-lote
description: Redimensionar, recortar por coordenadas, converter e gerar miniaturas de imagens locais em lote, preservando originais e conferindo dimensões e formato.
---

Use para transformações determinísticas em JPEG, PNG e WebP. Para edição visual criativa, use a ferramenta de imagem disponível no ambiente.

Leia [o contrato](references/contrato.md) e prepare um JSON com operação explícita e pares de caminhos. Execute `python3 scripts/images.py --spec pedido.json`, resolvendo `scripts/` relativo a esta skill. Pillow é necessário; não instale dependências sem autorização.

`resize` usa dimensões exatas; `thumbnail` cabe na caixa preservando proporção e não amplia. Recortes seguem a imagem após normalizar a orientação EXIF. JPEG de imagem com transparência exige `background` explícito. Os originais e destinos existentes são preservados. Mostre os resultados medidos do JSON; se `ok` for falso, relate a falha e eventuais caminhos em `published`.
