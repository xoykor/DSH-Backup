---
name: configuracoes-estruturadas
description: Editar configurações locais JSON, YAML e TOML por caminhos e valores explícitos, com pré-condições, validação de tipos e saída separada.
---

# Configurações estruturadas

Use `scripts/config_edit.py` para produzir uma configuração nova. A origem é preservada; a saída não pode existir. Python 3.11+; YAML requer PyYAML. O escritor TOML não precisa de pacote adicional.

1. Converta a alteração solicitada em `operations`, usando arrays de chaves/índices em `path` (índices começam em zero).
2. Para chave existente, declare `expected`, `expected_type`; para criar uma chave de objeto, use `expected_absent: true`. `set` exige `value` e `value_type`; `delete` remove uma chave ou elemento existente. Não cria caminhos intermediários nem acrescenta elementos de arrays.
3. Execute `python3 scripts/config_edit.py --input app.toml --spec alteracoes.json --output app.novo.toml`.
4. Confira `status`, `changes` e `roundtrip_validated`. O resumo mostra caminhos e tipos; nunca mostra valores. A ativação/substituição da configuração fica fora deste helper e depende do escopo autorizado pelo usuário.

Exemplo de especificação:

```json
{"operations":[{"op":"set","path":["server","port"],"expected":8080,"expected_type":"integer","value":8081,"value_type":"integer"},{"op":"set","path":["server","enabled"],"expected_absent":true,"value":true,"value_type":"boolean"}]}
```

Tipos editáveis: `string`, `integer`, `number` (float), `boolean`, `object`, `array`, `null` (não existe em TOML). Comparação distingue booleano de inteiro e inteiro de float. Datas/horários TOML/YAML existentes são preservados quando não alterados; as operações aceitam valores JSON. Arquivos até 8 MiB, até 128 operações, profundidade 64. `--format json|yaml|toml` substitui detecção da extensão e mantém o mesmo formato na saída.

Comentários, ancoragens e apresentação do documento não são preservados. TOML reescreve tabelas como objetos inline e valida o resultado por `tomllib`. YAML rejeita chaves duplicadas, chaves não textuais e estruturas cíclicas. O helper valida novamente a serialização, verifica que a origem não mudou e cria a saída com permissão 0600. Código 0 indica sucesso; 2 indica erro sem aplicação do patch à origem. Não despeje conteúdo de configuração no chat para diagnosticar erros; examine somente os campos necessários.
