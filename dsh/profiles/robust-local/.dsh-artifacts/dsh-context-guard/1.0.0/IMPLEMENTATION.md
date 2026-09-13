# Guard DSH — implementação

Escopo: cópia de desenvolvimento em `work/dsh-improvement/guard`. A instalação em `__HOME__/.local/lib/node_modules/@deepseek-ai/dsh` não foi modificada.

API revisada: DSH `0.1.2-rc.1`, com `tools.guard`, `tools/post-execute`, `agent/pre-step`, `agent/turn-stopping`, `session/event` e `Agent.cancel(cause, { keepInbox: true })`. O contrato de `TokenMeter.measure()` foi confirmado no pacote local: `totalTokens` é pressão atual da superfície medida.

## Alterações

- A identidade de uma chamada ordena apenas chaves de objetos, preserva o conteúdo literal de strings (inclusive espaços), e exclui `description` dos argumentos de identidade.
- Resultados de erro são classificados por família (`parse`, `type`, `timeout`, `permission`, `network` e `other`) e recurso referenciado. Falhas de comandos com `exitCode !== 0`, sinal, aborto ou negação explícita do sandbox entram nessa classificação mesmo com `isError: false`. Texto variável, posições e stack trace não renovam o progresso. Falhas equivalentes são contidas por `noProgressLimit`.
- Uma observação bem sucedida diferente para a mesma ação conta como progresso. Reteste depois de mutação só limpa bloqueios quando o executor relata evidência estruturada (`changed`, `modified`, `written`, `changedFiles`, revisão ou `before`/`after` diferente); uma mensagem `ok` isolada não é tratada como alteração.
- Todas as chaves de configuração são verificadas antes dos defaults. Limites de chamadas, passos, tempo e tokens continuam sendo aplicados no guard e a reserva de chamadas é síncrona, cobrindo lotes concorrentes; membros já reservados de um lote não são cancelados prematuramente quando outro membro termina.
- `assistant/message.usage` é somado por requisição para o limite de tokens e permanece correto quando compaction reduz a pressão atual. Quando o provider não reporta uso, o guard usa o maior valor observado por `tokenMeter.measure().totalTokens`; isso é um fallback de pressão, não consumo acumulado.
- Após timeout, o diagnóstico informa que o status de limpeza do processo é desconhecido. O modo de diagnóstico exige metadata explícita de capacidade read-only (`readOnly`, `capabilities.readOnly`, `capability.readOnly` ou `definition.readOnly`); nomes e regex de comandos não concedem acesso.
- Estado anti-loop e orçamento é mantido entre turnos automáticos, compaction e reconnects que reutilizam o mesmo `session.id`. Uma mensagem consumida com `source.kind === "user"` inicia nova autorização e limpa a janela. `agent/disposed` solta a referência do agente; `session/disposed` libera o estado da sessão.

## Verificação

```text
npm test -- --test-isolation=none
15 passed, 0 failed (Node v26.8.2)
```

Os testes exercitam diretamente os callbacks `tools.guard`, `tools/post-execute`, `agent/pre-step`, `session/event`, `agent/disposed` e `session/disposed` com agentes, resultados nativos Bash, concorrência, reconnect, turnos automáticos, autorização humana e uso reportado sintéticos. Não constituem teste de inferência do Ornith, cancelamento real de subprocessos, compaction real ou distribuição do plugin no perfil.

## Riscos e limites

O guard não possui API pública para reabrir automaticamente um turno cancelado nem para persistir seu estado após a própria sessão ser descartada; `cancel(..., { keepInbox: true })` preserva a inbox quando o driver suportar essa semântica, mas a continuação depende de um novo wake do agente. Se `Agent.cancel()` lançar, o guard mantém o bloqueio e anota que o cancelamento não pôde ser confirmado. O estado de contadores é reiniciado apenas por nova autorização humana. A metadata read-only precisa ser anexada pelo host porque o `ToolExecution` desta versão não a define; sem ela, o diagnóstico após timeout fecha todas as chamadas. A detecção de efeitos arbitrários em transportes externos continua fora do alcance do guard.
