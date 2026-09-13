---
name: acompanhamento
description: Check para acompanhar chamadas de ferramentas demoradas sem loops redundantes. Proba artefatos duraveis/estado de processo por classe de ferramenta diferente (mtime/tamanho, pgrep/ps) e prefere job_list/job_output em vez de tail de log — cada probe produz evidencia nova.
disable-model-invocation: false
user-invocable: false
---

# Acompanhamento (Check)

## Quando rodar

Depois de lanchar qualquer chamada longa ou background (download, snapshot, build,
job nohup/&, etc.), antes de repetir a mesma consulta. O objetivo e obter evidencia
nova do progresso/completude sem ler o mesmo log duas vezes.

## Regra central

Uma probe que usa a mesma classe de ferramenta que a chamada anterior nao conta como
evidencia nova. Trocar `tail` por `head`, ou `ls -l` por `wc -c`, sobre o mesmo
arquivo e leitura = loop redundante, proibido.

## Probar por classe de ferramenta (produz evidencia nova)

1. **Download / escrita de arquivo** → leia o ARTEFATO DURAVEL, nao o log:
   - `stat`/mtime/tamanho do target; compare com a leitura anterior para ver crescimento.
   - Tamanho final + mtime estavel = completude (evidencia nova), nao `tail`.

2. **Processo nohup/sem rastreamento** → identifique por assinatura, depois le o artefato:
   - `pgrep`/`ps` pela string de comando para achar PID e estado (running/finished).
   - Em seguida le UMA vez o artefato de saida que ele escreve.

3. **Jobs gerenciados pelo harness** → prefira sempre as ferramentas nativas:
   - `job_list` (ids/kinds/status) e `job_output` (stream final) — classe de ferramenta
     diferente do bash, portanto nao redundante.

## Transicao para conclusao

- Artefato finalizado ou processo finished = evidencia suficiente → conclua.
- Sem progresso mas sem falha = reporte estado duravel + proxima acao concreta; pare
  de probear o mesmo target ate haver crescimento ou erro novo.
- Se nenhuma classe acima puder resolver, declare o bloqueio e nao converta em mais
  leituras estaticas equivalentes.

## Integracao com quebra-de-loop

Se o probe redundante for negado pelo guard de contexto, mude de classe de ferramenta
(classe 1/2/3 acima) ou peca apenas dado faltante — nunca repita a consulta negada.
