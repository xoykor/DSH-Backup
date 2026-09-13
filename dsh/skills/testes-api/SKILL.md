---
name: testes-api
description: Verificar endpoints HTTP autorizados com uma especificação JSON limitada, asserções de status, cabeçalhos e corpo, sem repetir requisições nem vazar segredos.
---

# Testes de API

Use `scripts/api_check.py` para executar uma lista explícita de requisições
HTTP contra um alvo autorizado. Leia [contract.json](references/contract.json)
para o formato. GET e HEAD são os métodos padrão; métodos mutáveis exigem
`allow_mutations: true` no spec e `--allow-mutations` na linha de comando.
Não use retries, replay ou comandos arbitrários.

```bash
python scripts/api_check.py --spec requests.json --output evidence.json
```

O runner aplica timeout individual e orçamento total, limita o corpo, separa
falha de transporte de falha de asserção e trata `HTTPError` como resposta
testável. Asserções podem verificar `status`, `headers` e campos JSON do
`body` com `equals` e `contains`. A evidência redige URLs, cabeçalhos, corpos e
erros com credenciais, cookies, tokens ou chaves. As asserções usam os valores originais em memória, antes da redação do relatório.

O timeout inclui DNS, conexão e leitura do corpo em um processo delimitado. Não segue redirecionamentos: o status 3xx é testável e não reenvia credenciais a outro destino. Sem `expect`, exige status 200. JSON declarado na resposta deve ser válido; corpo truncado não aprova uma asserção de conteúdo. Até 32 casos; `--total-timeout` entre 0,05 e 600 segundos; `--body-max-bytes` entre 1 e 262144 (12000 padrão).

Use um caminho novo para `--output`. Exit 0: todas as asserções passaram; 1: falha de transporte/asserção; 2: plano inválido, mutação sem opt-in ou falha ao escrever relatório. O hash de corpo informa se representa o corpo inteiro ou somente o prefixo capturado.
