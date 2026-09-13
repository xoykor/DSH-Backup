---
name: diagnostico-servicos-logs
description: Diagnosticar containers, serviços, URLs e arquivos de log locais com coleta limitada e evidências redigidas, sem reiniciar nem alterar serviços.
---

# Diagnóstico de serviços e logs

Use `scripts/diagnose.py` quando o alvo e o escopo forem fornecidos
explicitamente. Aceite `--container`, `--service`, `--url` e `--log-file` em
qualquer combinação. O helper verifica executáveis disponíveis, permissões do
daemon quando aplicável, portas, endpoints informados e logs limitados por
tempo e tamanho. Ele não reinicia, inicia, para ou modifica serviços.

```bash
python scripts/diagnose.py --container nome --url http://127.0.0.1:8080/health \
  --log-file /var/log/app.log --timeout 20 --output diagnostico.json
```

Leia [contract.json](references/contract.json) antes de adaptar a saída.
Separe os fatos coletados das hipóteses derivadas. A saída informa códigos de
saída, truncamento e assinaturas agrupadas com primeira e última ocorrência.
Valores de credencial, cookies, tokens, chaves e variáveis sensíveis são
redigidos antes de aparecerem no JSON. Nunca presuma systemd, Docker ou outro
runtime: o relatório deve registrar quando o executável ou a permissão não
estiver disponível.

O timeout de 0,1–600 segundos inclui DNS e leitura HTTP; subprocessos são encerrados com seus filhos quando o prazo acaba. Respostas 3xx não são seguidas. Somente arquivos regulares são lidos como logs, evitando bloquear em pipes. Até 32 alvos, 262144 bytes de log por coleta e 2000 linhas de Docker. `--output` exige um arquivo novo. Exit 0: coleta completa; 1: coleta incompleta; 2: entrada/execução inválida. Uma coleta completa pode constatar serviço indisponível: confira as observações, não só o código do helper.
