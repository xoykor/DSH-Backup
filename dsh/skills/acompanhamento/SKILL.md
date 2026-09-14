---
name: acompanhamento
description: Acompanhe tarefas gerenciadas de longa duração com espera nativa e critérios reais de conclusão, sem duplicar jobs nem transformar indícios em sucesso.
---

# Acompanhamento

Use o background gerenciado da ferramenta quando ele existir. Ao lançar uma tarefa,
registre o `job_id` e reutilize-o; não lance uma segunda cópia para consultar o
progresso.

Quando não houver trabalho independente para fazer, aguarde pela ferramenta nativa:
`job_output({"job_id":"ID_RECEBIDO", "wait":true, "timeout_ms":30000})`. Use intervalos nativos de 30–60 segundos
e nunca `bash sleep`. A saída incremental pode ser vazia. Use notificações de
conclusão quando disponíveis.

`pending`, `running`, `stopping` e `waitExpired` são estados intermediários. Eles não
significam falha, conclusão ou timeout da execução. `job_list` serve apenas para
localizar uma vez um `job_id` perdido; depois, continue usando o ID encontrado.

O job encerrou quando seu status for `completed`, `failed` ou `killed`. Só relate
sucesso com `completed`, `detail`/`exit` compatíveis quando disponíveis e artefato
validado pelos critérios reais da tarefa. Preserve e relate qualquer falha. Mtime, tamanho estável e desaparecimento de PID são apenas indícios;
isoladamente não provam sucesso.

Se o orçamento do guard acabar, encerre o turno declarando claramente que o job está
pendente e preserve-o para um novo turno autorizado. Uma notificação não autoriza
reset nem garante continuação depois de um limite duro; conclusão automática normal
só ocorre enquanto o guard admite continuação e um wakeup foi configurado.

O guard permite leitura explicitamente verificada de `job_output`/`job_list` e uma
espera neutra legítima. Consultas rápidas repetidas continuam bloqueadas. Não edite
goals durante diagnóstico, não crie skill e não troque de ferramenta ou classe para
contornar o guard.
