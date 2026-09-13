# Contrato de midia-local

`python3 scripts/media.py --spec pedido.json`. Dependências: Python 3 stdlib, FFmpeg e ffprobe no PATH; nenhuma chamada de rede. Os scripts são autocontidos.

Campos: `operation` (`probe`, `trim`, `extract-audio`, `convert`), `input`, `output` (exceto probe), `timeout_seconds` (1–3600, padrão 120). `probe` aceita somente operação, input e timeout. Caminhos são locais, relativos ao diretório de execução; o diretório do destino deve existir. Destinos existentes/symlinks/hardlinks são recusados.

`trim` exige `duration_seconds` positiva, `start_seconds` >= 0 (padrão 0); o trecho precisa caber na duração de entrada. Reencoda para produzir corte preciso, sem copiar keyframes imprecisos. `extract-audio` exige stream de áudio. `convert` converte toda a duração.

Saída de vídeo: `.mp4` com `libx264` e AAC se houver áudio; `crf` 0–51 (padrão 23). Pode informar `width` e `height` pares, 2–8192, para encaixar com barras sem distorção; `fps` positivo <= 120 altera FPS só se informado. Sem dimensões explícitas, preserva SAR e preenche até 1 pixel em dimensões ímpares; FFmpeg aplica rotação aos pixels. Somente primeiro vídeo e primeiro áudio são selecionados; legendas, capítulos, anexos e metadados são removidos. A validação retorna dimensões, SAR e rotação efetivas.

Saída de áudio: `.m4a` AAC, `.mp3` libmp3lame ou `.wav` PCM s16le. `audio_bitrate_kbps` inteiro 8–320, padrão 128, vale para AAC/MP3 e áudio de vídeo. Wav ignora bitrate. O codec precisa existir localmente. Campos desconhecidos e campos de vídeo para saída de áudio falham.

```json
{"operation":"probe","input":"video.mp4"}
```
```json
{"operation":"trim","input":"video.mp4","output":"trecho.mp4","start_seconds":5,"duration_seconds":10,"timeout_seconds":120}
```
```json
{"operation":"extract-audio","input":"video.mp4","output":"audio.mp3","audio_bitrate_kbps":128}
```
```json
{"operation":"convert","input":"entrada.wav","output":"fala.m4a","audio_bitrate_kbps":96}
```

Saída JSON: `ok`, `status`, caminhos, bytes, `probe` e `decisions`. Exit 0 sucesso, 2 erro. Resultado é validado por codec, duração (tolerância max(0,35 s, 3%)) e decodificação completa. Arquivos parciais temporários são removidos em falhas; nenhum destino existente é alterado. FFmpeg aceita apenas protocolos file/pipe e não baixa conteúdo. A qualidade visual não é julgada automaticamente.

Teste: `python3 tests/test_media.py`.

Opções explícitas adicionais: audio_channels (1 ou 2) altera canais; sample_rate_hz (8000–192000) solicita frequência de amostragem. O encoder deve aceitar a frequência; incompatibilidade falha sem publicar o destino. Ambos exigem stream de áudio. fps (positivo até 120) exige vídeo. Sem esses campos, os canais/frequência/FPS são mantidos conforme o encoder. Os valores efetivos são conferidos no ffprobe antes de publicar.
