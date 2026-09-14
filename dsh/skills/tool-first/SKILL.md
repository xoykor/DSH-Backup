---
name: tool-first
description: Investigar arquivos, repositórios e dados usando ferramentas determinísticas antes de ler grandes volumes; escolher ferramenta pronta, Bash simples, Lua scratch ou Python conforme a complexidade.
---

# Tool-first

Use esta skill para investigar o ambiente local, localizar evidências ou processar conteúdo antes de raciocinar sobre o resultado.

## Política de escolha

1. Use uma ferramenta pronta que já resolva a operação (`rg`, `fd`, `find`, `jq`, `git`, `sed`, `awk`, `sort`, `uniq`, `cut`, `wc`, `diff`, `sqlite3` ou helper especializado).
2. Use Bash para uma composição curta de ferramentas existentes.
3. Use uma scratch tool Lua quando a solução exigir loops ou condicionais aninhados, transformação estruturada, agregação ou escaping difícil.
4. Use Python quando uma biblioteca ou formato especializado justificar seu custo.
5. Leia diretamente apenas o trecho necessário quando a consulta já for pequena ou quando a interpretação depender do contexto.

Não crie um script para substituir uma ferramenta pronta. Um `$(...)` simples ou um pipeline curto continua sendo Bash. Troque para Lua quando a lógica deixar de ser clara ou determinística no shell.

## Investigação

Defina a pergunta e o conjunto de evidências antes de executar. Comece com uma consulta barata e refine-a se houver muitos resultados. Retorne localizações, contagens, amostras e pequenos intervalos de contexto, em vez de despejar arquivos inteiros.

Declare o escopo da busca e seus limites. Uma correspondência textual não prova uma referência semântica; use parser, LSP ou outra ferramenta apropriada quando a pergunta exigir estrutura. Trate saída truncada, erro e resultado incompleto como parte da evidência.

Para scripts temporários, use o executor abaixo:

```bash
python3 __DSH_HOME__/skills/tool-first/scripts/run_scratch.py \
  --language lua --script /tmp/query.lua --root . --timeout-ms 10000 -- \
  argumento
```

O executor usa leitura somente no root, rede desabilitada, escrita temporária em `/scratch`, limite de tempo e saída estruturada. Leia [references/executor.md](references/executor.md) quando precisar criar ou depurar uma scratch tool.

## Resultado para o modelo

Prefira evidência pequena e acionável: caminho, linha, símbolo ou registro, contexto limitado e contagem total. Se o limite for atingido, informe o que foi examinado, o que foi devolvido e como refinar a consulta. Não transforme uma falha de ferramenta em uma conclusão sobre os dados.

Respeite as skills `anti-investigacao-redundante`, `acompanhamento` e `context-guard` quando estiverem ativas. Esta skill não amplia permissões, não autoriza rede e não substitui os mecanismos de sandbox do DSH.
