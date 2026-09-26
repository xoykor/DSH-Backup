---
name: prezi-em-pdf
description: Converter uma apresentação Prezi (view pública) em um PDF multi-página, capturando cada frame do present mode e montando o PDF a 1920x1080. Use quando o usuário peça para "percorrer a apresentação, tirar prints e montar o pdf" de um link prezi.com/view/...; não promete design livre nem captura de sites estáticos.
---

# Prezi (view) em PDF

Captura cada slide/frame do **present mode** de uma apresentação Prezi e monta um único PDF multi-página a 1920×1080 px @ 100 DPI. Fluxo: `scripts/capture.mjs` (Playwright headless Chromium) → `scripts/assemble.py` (PIL).

## Dependências nesta instalação
- Node.js + Playwright (`node_modules/playwright`, browser em `~/.cache/ms-playwright`) — `capture.mjs` resolve o pacote localmente, por `NODE_PATH`, por `PLAYWRIGHT_NODE_MODULES`, por roots compartilhados do sistema ou pelo runtime auxiliar do Codex, e roda de qualquer diretório. Se o browser empacotado pelo Playwright não estiver disponível, usa `PREZI_CHROMIUM_PATH`, `CHROMIUM_PATH` ou Chromium do sistema. `pngjs` é opcional e habilita a filtragem de quadros totalmente brancos/pretos.
- Python 3 com Pillow global; Poppler `pdfinfo` e `pdftoppm`.

## Fluxo (3 passos)
Antes de lançar a captura, carregue [execucao-longa](../execucao-longa/SKILL.md) e [acompanhamento](../acompanhamento/SKILL.md). A captura dura minutos e precisa de background gerenciado. O script já resolve Playwright: execute-o diretamente; não use um `require('playwright')` de outro diretório nem uma varredura de `/` como pré-requisito.

1. **Capture** os frames com caminhos absolutos: `node __DSH_HOME__/skills/prezi-em-pdf/scripts/capture.mjs URL DIR_SAIDA`, usando `bash` com `run_in_background: true`. Crie uma pasta nova por tentativa (por exemplo, use o caminho retornado por `mktemp -d` e acrescente `/pages`); não reutilize a captura anterior. Preserve stdout/stderr no job para `job_output` mostrar progresso. O script salva PNGs e manifest incrementalmente.
2. **Acompanhe e monte**: registre o `job_id` retornado e aguarde com `job_output` usando `wait: true` e `timeout_ms: 30000`. Uma espera expirada com job ativo só exige acompanhar o mesmo job. Nunca use Bash com `sleep`, loops de polling ou `tail` repetido para esperar. Após estado terminal, confira código de saída, `completed` e evidência reconhecida no manifest: controle nativo desativado, controle visível de reinício/replay, ou pelo menos cinco imagens idênticas consecutivas após navegação. Quadros praticamente idênticos a uma página já capturada são pulados e a navegação continua. O quadro de interface com “Restart/Replay” encerra a captura e não entra no PDF. Só então execute `python3 __DSH_HOME__/skills/prezi-em-pdf/scripts/assemble.py DIR_PNGS SAIDA.pdf`, também em background para capturas grandes. O manifest determina a ordem e os paths `file` são relativos a `DIR_PNGS`. O montador recusa captura incompleta ou legada sem comprovação de conclusão. Rotula as páginas e preserva a proporção em canvas 1920×1080 a 100 DPI.
3. **Verifique** (não declare pronto sem isso): conte páginas e dimensão com `pdfinfo`/`file`, renderize 1ª e última página com `pdftoppm -png`, confirme conteúdo real (não branco) e rótulos presentes.

## Gotchas que definem o workflow
- **Present mode é obrigatório**: na landing, as setas não avançam sob o overlay azul "Present". O script clica `.viewer-common-info-overlay-button-filled`, `button[aria-label="Present"]` ou o texto visível `Present`.
- **Viewer em iframe e chrome da página**: o viewer público pode estar em um iframe e a página pode exibir cabeçalho, banner de cookies e controles de navegação. O script procura o botão em todos os frames, rejeita o banner quando presente e oculta esses elementos antes de capturar.
- **Conclusão versus interrupção**: aceite controle nativo de próxima etapa desativado, controle visível de `Restart`/`Replay`, ou ao menos cinco screenshots binariamente idênticos consecutivos após capturar mais de um frame diferente. O quadro de interface `Restart`/`Replay` encerra a captura e não deve entrar no PDF. Uma capa que reaparece, uma tela estática isolada, código 0 do processo, quantidade de PNGs ou a numeração do PDF nunca provam conclusão. Um retorno a uma página anterior é pulado, mas não encerra por si só; se a captura ficar parada nessa página, permaneça incompleta. `deadline`, `max-pages`, `empty-frame`, `no-navigation`, `returned-to-start` e `repeated-view-stall` permanecem incompletos. O processo sai com código 2 nesses casos; as conclusões registram sua evidência específica, e erros geram código não zero.
- **settle()** toma screenshots até a tela parar de mudar (poll 180ms, janela máx 2.6s) antes de registrar um frame; frames brancos/preto puros são ignorados como progresso.
- **PIL não abre PDFs**: use `file`/`pdfinfo` para contagem/dimensão e `pdftoppm -png` para rasterizar páginas; PIL lê PNG sem problema (só não PDF).
- **Ordem vem do manifest, não da lista de arquivos**: o capture pula quadros duplicados ou praticamente idênticos (ao menos 99,95% dos pixels amostrados diferem no máximo 3 níveis por canal), frames brancos e a interface de reinício, então os índices não ficam contíguos. O manifest lista somente páginas únicas salvas; os paths `file` são relativos ao `DIR_PNGS`. O montador normal só aceita manifest com `completed:true` e uma prova registrada de término. `--partial-export` gera explicitamente um artefato que traz “PARCIAL” em cada página; nunca use essa opção em uma entrega solicitada como completa. Não transforme falha de montagem em permissão para trocar a opção.

## Recuperação

Se atingir `deadline` ou `max-pages`, preserve a tentativa e sua evidência. Para o mesmo pedido completo, uma nova tentativa pode usar limite maior proporcional ao progresso observado, em outra pasta, mantendo limite finito. Não repita a mesma configuração nem aumente indefinidamente. Ausência do indicador de fim exige diagnosticar o viewer, não adivinhar pela semelhança visual ou aumentar apenas o tempo.

Se um timeout externo ativar o diagnóstico do context-guard, observe apenas o job pelos observadores admitidos. A conclusão dele não libera Bash nem renova o orçamento. Pare com o estado e caminhos preservados; retome a verificação no próximo turno humano autorizado. Não desative o guard nem lance captura duplicada.

## Verificação mínima
`file SAIDA.pdf` → "PDF document, version X, N page(s)"; `pdfinfo SAIDA.pdf | grep -Ei 'Pages|Page size'`; renderize e inspecione primeira/última página. Páginas esperadas = número de PNGs no diretório.

Para um teste curto, os limites podem ser reduzidos com `PREZI_MAX_PAGES`, `PREZI_DEADLINE_MS`, `PREZI_SETTLE_MAX_MS` e `PREZI_NOCHANGE_STREAK`; esses overrides não são necessários no uso normal.
