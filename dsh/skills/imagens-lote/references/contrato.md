# Contrato de imagens-lote

Invocação: `python3 scripts/images.py --spec pedido.json`. Caminhos relativos são resolvidos contra o diretório de execução. Pais dos destinos devem existir. Python 3 e Pillow são necessários; a skill é autocontida.

Campos: `operation` = `resize`, `thumbnail`, `crop` ou `convert`; `items` = 1–100 objetos com `input` e `output`; `quality` inteiro 1–100 (padrão 82); `background` cor RGB opaca como `#ffffff`. Extensões de saída `.jpg`, `.jpeg`, `.png`, `.webp` selecionam formato. Formatos que o Pillow local não codifica falham explicitamente.

- `resize`: `width`, `height` inteiros 1–16384; dimensões exatas, pode mudar proporção.
- `thumbnail`: mesmos campos; cabe na caixa, conserva proporção, não amplia.
- `crop`: `box` = `[left,top,right,bottom]`, bordas direita/inferior exclusivas; deve caber na imagem orientada.
- `convert`: formato vem da extensão; não aceita dimensões nem box.

```json
{"operation":"thumbnail","width":640,"height":480,"items":[{"input":"foto.png","output":"miniatura.webp"}]}
```

```json
{"operation":"crop","box":[10,20,110,120],"background":"#ffffff","quality":85,"items":[{"input":"logo.png","output":"recorte.jpg"}]}
```

O script valida todo o lote em arquivos temporários antes de publicar. Destinos existentes, symlinks, hardlinks existentes, destinos repetidos e iguais a fontes são recusados. Uma colisão concorrente durante publicação pode produzir `status: partial`, `ok: false`, e a lista `published`; arquivos publicados pelo lote são preservados. Falhas de validação anteriores à publicação deixam nenhum resultado.

Saída JSON: `ok`, `status`, `count`, `results` com caminhos, bytes, largura, altura, formato e alpha. Exit 0 somente para sucesso; 2 em erro. Imagens animadas/multipágina são recusadas. Orientação EXIF é aplicada aos pixels e EXIF removido; perfil ICC é mantido quando disponível. Não há comparação perceptual, suporte a animação ou promessa de tamanho menor.

Teste: `python3 tests/test_images.py`.
