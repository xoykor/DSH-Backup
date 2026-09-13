---
name: quebra-de-loop
description: Check automatizado contra loops de investigacao redundante e guia para quebrar o loop. Antes de cada passo de investigacao, verifique se ha evidencia suficiente para a proxima acao autorizada; se nao, produza evidencia nova ou peca apenas os dados faltantes — nunca repita leituras equivalentes.
disable-model-invocation: false
user-invocable: false
---

# Quebra de Loop (Check)

## Regra central

Proibido repetir uma investigacao que ja respondeu a mesma pergunta sobre o mesmo
estado relevante, sem evidencia nova capaz de mudar a decisao. Trocar palavras da
busca, ferramenta, agente ou ordem de leitura nao torna a investigacao nova.

Quando houver evidencia suficiente para a proxima acao autorizada, execute-a.
Nao exija certeza sobre todo o sistema para fazer uma mudanca delimitada.

## O check (rodar antes de cada passo)

1. Identifique a pergunta ainda nao respondida e a decisao concreta que sua
   resposta pode alterar.
2. Confirme se as evidencias ja disponiveis na conversa/checkpoint respondem-na.
3. Se respondidas e o estado relevante nao mudou, reutilize a conclusao — pare.

## Transicao para execucao (evidencia suficiente)

Passe a implementacao quando estiver definidos: comportamento solicitado, local da
mudanca e uma validacao proporcional — sem bloqueio material de autorizacao ou
correcao pendente. Nao transforme incerteza de runtime em novas rodadas de leitura
estatica que nao podem resolvê-la.

## Quebrar o loop (quando falta informacao)

- Produza evidencia nova: artefato duravel (mtime/tamanho), `pgrep`/`ps` por
  assinatura, ou ferramenta diferente da que foi negada.
- Se faltar dado indispensavel para agir corretamente, peça APENAS esse dado — o
  que nao pode ser obtido dentro das restricoes vigentes. Nao devolva ao usuario
  trabalho que se poderia executar sozinho.
- Relate estado duravel + proxima acao concreta em vez de ler logs repetidamente.

## Validacao (nao e rediagnostico)

Execute a verificacao minima capaz de detectar a falha relevante. Se passar e os
requisitos estiverem atendidos, conclua. Nao alegue sucesso de runtime por inspecao
estatica sozinha; nao reabra buscas equivalentes para compensar um teste indisponivel.

## Encerramento

Informe o que foi alterado, como foi validado e limitacoes materiais restantes.
Nao encerre so porque parou de investigar se ainda houver implementacao autorizada
e viavel a fazer.
