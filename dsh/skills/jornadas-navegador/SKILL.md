---
name: jornadas-navegador
description: Executar jornadas funcionais curtas no navegador local a partir de passos e verificações explícitos, com relatório por etapa e captura de falhas.
---

# Jornadas de navegador

Use para verificar comportamento: preencher um formulário, clicar e conferir texto, URL, título ou estado de um elemento. Aparência continua sendo tarefa da `auditoria-visual`; uma asserção de DOM não comprova layout.

Prepare um JSON conforme [references/contrato.md](references/contrato.md) e execute `python3 scripts/run_journey.py --spec jornada.json --output-dir evidencias-novas`. URLs e interações devem pertencer ao escopo autorizado. Ações que enviam formulários ou alteram dados precisam de `allow_interactions: true` no plano; use dados de teste adequados. O executor não repete cliques ou envios após timeout.

O helper usa a ponte HTTP existente em `http://127.0.0.1:8731`, sem recriar um driver CDP/WebSocket. A versão atual dessa ponte usa uma aba ativa compartilhada: o helper exige uma ponte sem abas abertas, cria uma aba e a fecha ao terminar. Use-a de forma exclusiva durante a jornada; se houver outra sessão, escolha outra instância da ponte ou conclua a sessão existente. O script não fecha abas alheias para liberar o serviço.

O relatório distingue falha de asserção, infraestrutura e entrada inválida. Em falha, tenta uma captura delimitada da própria aba. Captura salva não significa inspeção visual. Verifique o código de saída e `status`; uma jornada sem asserções é recusada. Dependência: Python padrão e a ponte DSH funcional.
