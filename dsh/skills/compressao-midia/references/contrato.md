# Contrato de compressao-midia

`python3 scripts/compress.py --spec pedido.json`. Python 3, Pillow (imagens), FFmpeg/ffprobe (áudio e vídeo). O backend é uma cópia local para distribuição independente.

Obrigatórios: `kind` (`image`, `audio`, `video`), `input`, `output`. Todos os caminhos são locais, relativos ao diretório de execução, e o pai do destino deve existir. Recusa destinos existentes, symlinks, hardlinks ou iguais à fonte.

Opcionais:
- `quality`: inteiro 1–100 (padrão 82); maior é melhor. Imagem usa qualidade JPEG/WebP; PNG é sem perdas e ignora qualidade. Vídeo mapeia para CRF entre 18 e 40; áudio explícito mapeia para bitrate entre 32 e 256 kbps.
- `target_bytes`: inteiro positivo até 10¹² OU `target_mb`: número positivo até 10⁶. **1 MB = 1.000.000 bytes**. O alvo é comparado aos bytes finais reais. Sem alvo, há uma tentativa. Com alvo, qualidade pode cair entre tentativas.
- `max_attempts`: inteiro 1–6 (padrão 3), teto de tentativas; PNG sempre uma tentativa sem perdas.
- `timeout_seconds`: 1–3600 (padrão 180); orçamento total inclui encode, probe e verificação. Cada processo é encerrado no vencimento.
- `width`, `height`: ambos inteiros 1–8192; imagem cabe na caixa sem ampliar; vídeo exige valores pares e usa barras para preservar proporção. Não há redução automática de resolução/FPS/canais.
- `background`: RGB opaco como `#ffffff`, obrigatório para JPEG a partir de transparência.
- `audio_bitrate_kbps`: 8–320 (padrão 128), para áudio ou stream de áudio do vídeo. Meta pode reduzir o bitrate de áudio isolado; em vídeo mantém bitrate explícito e ajusta vídeo. Quando omitido, o áudio do vídeo pode reduzir para caber no orçamento.

```json
{"kind":"image","input":"foto.png","output":"foto.webp","quality":82,"target_mb":0.5,"max_attempts":3}
```
```json
{"kind":"audio","input":"gravacao.wav","output":"gravacao.mp3","target_mb":5,"timeout_seconds":180}
```
```json
{"kind":"video","input":"gravacao.mov","output":"compactado.mp4","target_mb":25,"max_attempts":3,"timeout_seconds":600}
```

Saídas suportadas: JPEG/PNG/WebP estáticos; `.m4a` AAC e `.mp3` libmp3lame; `.mp4` H.264 com AAC opcional. A disponibilidade real do encoder é verificada. Imagens animadas/multipágina são recusadas. Vídeo sem áudio é aceito. Apenas os primeiros streams de vídeo/áudio são preservados; metadados, capítulos, anexos e legendas são excluídos. Rotação é aplicada aos pixels; SAR é retido, salvo dimensões explícitas com letterbox/quadrado. EXIF de imagem é removido após orientação; ICC é retido quando disponível.

JSON retorna `ok`, `status`, `output` (ou null), `bytes_before`, `bytes_after` do melhor candidato, `reduction_percent`, `target_bytes`, `target_met`, `attempts`, `validation`, `decisions`.
- `ok` e exit 0: menor que original e meta satisfeita quando presente.
- `target_unmet`, exit 2: teto atingido; um candidato menor pode ser publicado, mas a meta falhou.
- `not_smaller`, exit 2: candidato não reduz tamanho; `output: null` e destino não é criado.
- `error`, exit 2: erro/timeout; temporários são removidos e não publica novo destino.

O usuário deve avaliar qualidade perceptual; validação de arquivo não prova aparência ou inteligibilidade. Vídeo usa bitrate com limites, não promete meta exata antes da medição. PNG sem alterar pixels frequentemente não chega a alvos agressivos. Teste: `python3 tests/test_compress.py`.

Opções explícitas adicionais: audio_channels (1 ou 2) altera canais; sample_rate_hz (8000–192000) solicita frequência de amostragem. O encoder deve aceitar a frequência; incompatibilidade falha sem publicar o destino. Ambos exigem stream de áudio. fps (positivo até 120) exige vídeo. Sem esses campos, os canais/frequência/FPS são mantidos conforme o encoder. Os valores efetivos são conferidos no ffprobe antes de publicar.
