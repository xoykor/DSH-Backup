# Fluxo de publicação e deduplicação — detalhes (Downloader)

## Como os itens chegam no disco (o caminho real)
1. `yt-dlp` baixa cada item em staging (`tmp_dir`).
2. O callback `download_progress_line` (`engine.c`) dispara eventos **FILE** assim que yt-dlp termina uma faixa.
3. Cada evento FILE → `publish_finished_track` (`media.c`) → `dld_publish_output`.
4. O arquivo é `cp`'do da staging para a pasta de destino (destino final).

## Por que o loop pós-yt-dlp em execute_download é código morto para playlists
- Em `execute_download`, após o scan pós-yt-dlp, há um loop que lê `tmp_dir`.
- No fluxo real acima, `publish_finished_track` já rodou **durante** os eventos FILE (meio do download).
- Quando o loop de scan chega, `tmp_dir` está vazio → itera zero entradas.
- Qualquer guard de dedup colocado nesse loop NÃO dispara para playlists = código morto.

## Onde o guard correto vive
- Função: `publish_finished_track` (`media.c`).
- Posição: após a validação de probe (`item_error`) e antes de publicar/re-gravar.
- Gatilho: `context->is_playlist && track->id[0]`.
- Chave: `dld_library_find(destination_dir, track->id, format)` — exige o arquivo **em disco** (library.c).
  - Encontrado → emitir COMPLETED "Já existe — faixa pulada" e retornar sem publicar/re-gravar.
  - Não encontrado → publicar/recuperar no mesmo nome.

## Por que debug prints dentro do loop de scan são silenciosos (e por que isso é uma pista)
- Se você instrumenta o loop pós-yt-dlp com `fprintf(stderr, ...)` e ele NÃO imprime, mas a cópia `(1)` ainda acontece:
  → a publicação já ocorreu por eventos FILE antes do loop rodar. O código que você pensou estar rodando não é o caminho real.
- Ação: rastreie o controle logo após o ponto suspeito e localize onde `dld_publish_output` realmente é chamado (aqui, em `publish_finished_track`).

## Reprodução/regressão (receita) — test_engine.c
Dois helpers fake-yt-dlp com eventos FILE idênticos ao real:
- Formato de evento: JSON com `"id":"id1"` / `"id":"id2"`, escrevendo para `tmp_dir`, depois `cp`'do para o destino.
- Teste parcial (`test_partial_playlist`): baixa os dois itens, depois **deleta id2 do disco** entre as corridas.
- Teste de regressão (`test_playlist_redownload_no_duplicates`): re-download parcial deve pular id1 (em índice + disco) e recuperar id2 (só em índice), sem criar `(1)`.
- `format="auto"` é estável entre corridas → a chave `media_id|format` não varia.

## Regras de manutenção
- Confirmar que eventos FILE carregam `track->id` não vazio (media.c copia o campo "id").
- Manter o loop de scan como rede de segurança genuína para versões do yt-dlp SEM eventos FILE.
- Não inferir progresso só por ter executado uma ferramenta; evidência nova ou dado faltante conta.
