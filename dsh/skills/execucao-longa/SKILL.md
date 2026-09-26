---
name: execucao-longa
description: Execute comandos demorados no DSH com background gerenciado e recupere tarefas após timeout. Use antes de varreduras grandes, conversões em lote, builds, testes ou transferências que possam exceder o limite de uma chamada Bash, ou quando houver timeout do executor.
---

# Execução longa no DSH

## Escolher o modo antes de executar

Diferencie o timeout do comando em primeiro plano, o prazo de uma espera por job e o orçamento do context-guard. São limites distintos. Consulte o schema e a configuração efetivos; 60000 ms foi o limite observado nesta instalação, não uma constante universal.

Para uma operação potencialmente longa, use `bash` com `run_in_background: true` desde a primeira execução completa. Exemplos: percorrer centenas de milhares de arquivos, calcular hashes de um catálogo, converter mídia, transferir muitos dados ou executar uma suíte demorada. Comandos pequenos e previsíveis podem continuar em primeiro plano.

Quando útil, valide primeiro uma amostra pequena ou um teste isolado: argumentos, caminhos, formato dos dados, relatório e comportamento esperado. Use a escala e a medição para estimar duração; não execute todo o lote só para descobrir se cabe no timeout. Não remova validações nem enfraqueça critérios de aceitação para acelerar o teste.

## Lançar e acompanhar

Use o diretório absoluto confirmado em `workdir`. Um `cd` ou uma listagem em outra chamada não muda o diretório da sessão.

Exemplo de chamada `bash` — substitua caminho e comando pelo trabalho autorizado:

```json
{
  "command": "python3 scripts/processar.py --modo validacao",
  "description": "Validar o lote completo em job gerenciado",
  "workdir": "/caminho/absoluto/do/projeto",
  "run_in_background": true
}
```

Deixe o processo principal ligado ao executor: não acrescente `nohup`, `&`, `disown` nem outro mecanismo de destacamento. O próprio DSH gerencia o background. Nesta ferramenta, o timeout de primeiro plano não se aplica ao job gerenciado; cancelamentos e demais limites do ambiente continuam valendo.

Registre o `job_id` realmente retornado, o comando, o diretório e os caminhos dos relatórios. Não invente um ID e não repita o lançamento para consultar o andamento. Se a resposta do lançamento for incerta, localize o job com `job_list` antes de considerar uma nova execução.

Faça trabalho independente enquanto o job roda. Quando depender do resultado, use:

```json
{
  "job_id": "ID_REAL_RETORNADO",
  "wait": true,
  "timeout_ms": 30000
}
```

Essa é uma chamada a `job_output`, não a Bash. `waitExpired` com estado `running` ou `stopping` significa apenas que a espera terminou; não reinicie nem mate o job por isso. Use notificações quando disponíveis. Para acompanhamento detalhado e verificação final, carregue a skill `acompanhamento`, disponível no mesmo catálogo DSH.

Não substitua essa espera por Bash com `sleep`, nem por um loop de `sleep` e leitura de log. A espera consome o timeout do Bash; `sleep 60` em uma chamada com limite de 60000 ms pode ativar diagnóstico mesmo com o job saudável. Preserve stdout/stderr no job para o observador devolver progresso.

## Se já ocorreu timeout

Leia o resultado do executor: duração, sinal, código de saída, job associado e confirmação de encerramento, quando disponível. Um timeout não desfaz arquivos escritos e não prova, sozinho, que todos os processos filhos terminaram. Preserve saídas parciais e verifique efeitos antes de uma repetição.

Se o context-guard entrou em diagnóstico, respeite as capacidades explicitamente admitidas pelo executor. Use `job_output` ou `job_list` quando houver trabalho gerenciado a observar. Não suponha que `read`, `get_goal` ou um comando Bash de consulta estejam permitidos só pelo nome. Não tente edições, relançamentos, `nohup`, troca de ferramenta ou alteração do guard para escapar do diagnóstico.

Se a chamada era de primeiro plano e não gerou job, não invente um `job_id`. Quando não houver observador admitido que resolva a incerteza, relate o comando interrompido, o estado conhecido e o próximo passo. Após uma nova mensagem humana e a admissão de um novo turno pelo guard, confirme efeitos e ausência de execução duplicada pelos meios disponíveis; então corrija a causa ou relance o trabalho autorizado como job gerenciado. Retomada automática, notificação ou compactação não equivalem a essa autorização.

Se background não estiver disponível no schema, use divisão em lotes verificáveis ou um timeout suportado e adequado ao trabalho. Se nenhuma opção puder concluir a operação, relate a limitação concreta sem inventar parâmetros ou desativar proteções.

## Concluir

Colete o estado terminal e o resultado final. Só declare sucesso quando o executor indicar conclusão compatível e os artefatos atenderem aos critérios da tarefa. Confira contagens, integridade ou testes conforme o trabalho; processo encerrado ou arquivo existente não bastam. Preserve comando, `job_id`, caminhos, falhas e próxima ação em qualquer resumo de contexto.
