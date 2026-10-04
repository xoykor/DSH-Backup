---
name: "downloader-pipeline"
description: "Understand and modify the media download/publish pipeline of the Downloader C project (C17/GTK4 + CLI), especially playlist deduplication. Use when editing engine.c/media.c/publish.c to avoid duplicates on re-download or conversion; not for general yt-dlp/ffmpeg questions.\\n\\nEntender e modificar o fluxo de download/publicação do projeto Downloader (C17/GTK4 + CLI), especialmente a deduplicação de playlists e o embutimento de capa (thumbnail) em áudio. Use ao editar engine.c/media.c/publish.c para evitar duplicatas em re-download ou conversão, diagnosticar capas ausentes (APIC/Vorbis PICTURE) em opus/mp3; não é para perguntas gerais sobre yt-dlp/ffmpeg."
author: "dsh-skill-curator"
version: "0.1.0"
---
# Downloader — fluxo de download/publicação e deduplicação

Detalhes do caminho FILE → publish_finished_track, por que o loop pós-yt-dlp é código morto, e o guard correto: `references/publish-flow.md`.

## Quando usar
- Editar o pipeline de download/conversão do projeto **Downloader** (C17/GTK4 + CLI).
- Diagnosticar ou consertar duplicatas `(1)` no re-download de playlists ou faixas.
- Colocar um guard de deduplicação no local certo, em vez de no loop pós-yt-dlp.
- Diagnosticar por que áudios (opus/mp3) não recebem capa embutida apesar de `--embed-thumbnail --add-metadata` ser enviado — causa raiz é o pacote Python `mutagen` ausente na etapa de postprocessamento.

## Arquitetura essencial (não óbvia)
- Itens de **playlist são publicados DURANTE o download**, via eventos FILE:
  `yt-dlp` → callback `download_progress_line` (`engine.c`) → `publish_finished_track`.
- Cada item cai na pasta de destino assim que yt-dlp termina ele, depois é `cp`'do fora do staging.
- O loop de scan pós-yt-dlp em `execute_download` (fim do loop, lê `tmp_dir`) roda com **zero entradas**
  nesse fluxo real — um guard de dedup colocado lá é código morto para playlists.

## Onde o guard de deduplicação deve ficar
- Em `publish_finished_track`, após a validação de probe (`item_error`), antes de publicar/re-gravar.
- Gatilho: `context->is_playlist && track->id[0]`.
- Chave: `dld_library_find(destination_dir, track->id, format)` — exige o arquivo **em disco** (library.c).
  - Encontrado → emitir COMPLETED "Já existe — faixa pulada" e retornar sem publicar.
  - Não encontrado → publicar/recuperar no mesmo nome.

## Por que o loop pós-yt-dlp falha como guard
- `dld_publish_output` com política padrão RENAME cria `(1)` quando o guard não dispara.
- No re-download parcial, itens existentes não são pulados individualmente → duplicatas visíveis.
- Debug prints dentro do loop de scan produzem saída zero mesmo que a cópia aconteça: confirma que
  a publicação já ocorreu por eventos FILE antes do loop rodar.

## Capa de arte em áudio (embed-thumbnail)
- `media.c` envia `--embed-thumbnail --add-metadata` para opus e mp3 (mesmos args), então o app já pede a capa ao yt-dlp — não é falta de solicitação.
- A etapa de postprocessamento que grava a arte no container precisa do pacote Python **mutagen**. Sem ele, o passo falha e nenhuma capa fica embutida:
  `ERROR: Postprocessing: module mutagen was not found. install: python3 -m pip install mutagen`
- Confirmar empiricamente (sem tocar no diretório do usuário): rodar os args exatos do app num destino de teste e inspecionar com ffprobe a existência de stream de imagem / tag APIC/Vorbis PICTURE. Áudios `ogg`/opus sem capa = mutagen ausente.
- Reparo: `python3 -m pip install mutagen` (pip 26.x, Python 3.14 neste ambiente). É dependência do pipeline de metadados, não do download em si.

## Diagnóstico por arquivo, não pela tela
- Perguntas sobre se um mídia baixado tem capa/arte embutida (APIC/Vorbis PICTURE) são respondidas inspecionando o **arquivo**, não a interface gráfica.
- `ffprobe` + inspeção de tags resolve; screenshots do GUI ou estado da janela são irrelevantes para "está baixando com capa ou não".
- Se o usuário disser "apenas analise os metadados" / "não precisa tirar print", execute exatamente isso — sem capturar a tela.

## Regras
- `ctest --test-dir build/c` — suite completa sem regressões.
- Regression test exato: `test_playlist_redownload_no_duplicates` (em `test_engine.c`) — re-download parcial de playlist não cria `(1)`. Receita de reprodução + formato dos eventos FILE fake-yt-dlp: `references/publish-flow.md`.
- Confirmar que eventos FILE carregam `track->id` não vazio (media.c copia o campo "id").
- Manter o loop de scan como rede de segurança genuína para versões do yt-dlp sem eventos FILE.
- Não inferir progresso apenas por ter executado uma ferramenta; evidência nova ou dado faltante conta.
