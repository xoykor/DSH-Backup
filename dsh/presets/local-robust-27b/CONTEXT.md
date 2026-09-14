# Local Robust 27B

Clone do Local Robust 9B para `lmstudio/qwen3.8-27b-gsq-rco`, com janela de
**64000 tokens**, conforme a configuração solicitada no LM Studio.

| Limite | Local Robust 9B | Local Robust 27B |
| --- | ---: | ---: |
| Contexto | 131072 | 64000 |
| Economia | 65536 | 32000 |
| Checkpoint | 81920 | 40000 |
| Compactação automática (72%) | 94371 | 46080 |
| Retenção na compactação | 32000 | 15625 |
| Resumo da compactação | 16384 | 8000 |
| Resposta máxima do modelo | 24576 | 12000 |
| Instruções: máximo em bytes | 131072 | 64000 |
| Poda: limiar/caracteres iniciais/finais | 12000/6000/2000 | 5859/2929/976 |
| Fingerprint de resultado: caracteres | 8000 | 3906 |

Os limites de tokens, bytes e caracteres foram escalados por `64000/131072`,
com truncamento para inteiros. Os marcos de contexto seguem as mesmas proporções
(50%, 62,5%, 72%). Contagens de tentativas permanecem iguais: 48 chamadas/passos e diagnóstico de
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
