# Local Robust 27B

Clone do Local Robust 9B para `lmstudio/qwen3.8-27b-gsq-rco`, com janela de
**64000 tokens**, conforme a configuração solicitada no LM Studio.

| Limite | Local Robust 9B | Local Robust 27B |
| --- | ---: | ---: |
| Contexto | 131072 | 64000 |
| Economia | 65536 | 32000 |
| Checkpoint | 81920 | 40000 |
| Pausa para resumo antes de compactar (70%) | 91750 | 44800 |
| Retenção na compactação | 32000 | 15625 |
| Reserva máxima para resumo | 8192 | 4000 |
| Margem de segurança | 4096 | 2000 |
| Resposta máxima do modelo | 24576 | 12000 |
| Instruções: máximo em bytes | 131072 | 64000 |
| Poda: limiar/caracteres iniciais/finais | 12000/6000/2000 | 5859/2929/976 |
| Fingerprint de resultado: caracteres | 8000 | 3906 |

Os limites de tokens, bytes e caracteres foram escalados por `64000/131072`,
com truncamento para inteiros. Os marcos de contexto seguem as mesmas proporções
(50%, 62,5%, 70%). Contagens de tentativas permanecem iguais: 48 chamadas/passos e diagnóstico de
3 chamadas e 2 minutos. O prazo global de 15 minutos foi desativado nos dois
presets robustos (`maxTurnMs: null`), conforme solicitado. Outros presets preservam
seus limites existentes. Timeouts de ferramenta, conexão e inatividade do LM Studio
são independentes e continuam configurados; não são prazos de duração total do turno.

A configuração `presetPolicies` do guard seleciona os limites pelo preset composto
no escopo do agente, não por texto do prompt. O guard usa o serviço de compactação
do próprio preset. O plugin global `dsh-qwen-defaults` roteia somente o preset
`local-robust-27b` para Qwen e limita sua resposta a 12000 tokens; os outros presets
mantêm seu roteamento. O catálogo LM Studio declara a janela de 64000 para Qwen,
sem trocar o modelo ou preset padrão da instalação.

As skills próprias do 9B foram copiadas. `context-guard` tem uma versão no diretório
local do 27B, que tem precedência sobre a versão global de 9B; as demais skills
compartilhadas, incluindo acompanhamento de jobs e mídia, continuam disponíveis.
A política global AGENTS.md distingue explicitamente as duas faixas.

Selecione **Local Robust 27B** para novas sessões. Um processo DSH iniciado antes
esta instalação precisa recarregar os plugins/configurações; os perfis configuram
reload no startup. Reinicie somente após encerrar os jobs relevantes. Esta mudança
não carrega/descarrega modelos nem altera a configuração de GPU do LM Studio.

## Fechamento antes da compactação

When the threshold is reached, the executor pauses normal work, waits for the interrupted turn to settle, asks the session model for a text-only state summary of the full balanced durable history (including the latest work), flushes that summary to storage, then replaces the history and resumes. No tools execute during the summary. Preserve job IDs, artifact/log paths, uncertain side effects, failed attempts and one next action. The executor prices the summary input plus instructions and schemas, reduces its output cap if necessary, and requires input + output cap + safety margin < context capacity. A missing, truncated, failed or unsaved summary never authorizes history replacement. Compaction does not reset logical execution budgets or anti-loop evidence.

A reserva inclui uma resposta normal que cruze o limiar: Ornith 91750 + 24576 + 8192 + 4096 = 128614 < 131072; Qwen 44800 + 12000 + 4000 + 2000 = 62800 < 64000. As instruções do resumo são precificadas novamente antes da chamada, além da margem. O orçamento de saída diminui se resultados tardios consumirem a reserva; se não houver espaço útil, a sessão para preservando o histórico. O guard usa checkpoint completo; a retenção de cauda da tabela é da política nativa, não se aplica ao checkpoint completo.
