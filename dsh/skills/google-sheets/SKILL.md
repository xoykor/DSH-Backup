---
name: google-sheets
description: Analisar, criar e editar Google Sheets com intervalos, abas, fórmulas, validações e gráficos delimitados, usando apenas ferramentas descobertas e autenticadas no runtime DSH.
---

# Google Sheets no DSH

Use esta skill para tarefas nativas de planilhas Google. A skill instalada não
é uma integração: confirme no turno que há ferramenta Google descoberta e que
a conta consegue ler a planilha alvo.

## Descoberta e alvo

1. Procure `Google Sheets` no `dev_tool_search` quando ele estiver disponível;
   desbloqueie somente os nomes exatos devolvidos. Caso a busca não exista,
   use apenas ferramentas visíveis. Inspecione os esquemas para saber se a
   sessão oferece busca, metadata, leitura de intervalo, escrita, importação,
   fórmula, validação, gráfico ou comentários. Não presuma nomes como
   `get_values`, `batch_update` ou `upload`.
2. Resolva a planilha por URL/ID fornecido. Para título ou palavras-chave,
   busque candidatos e mostre nome, MIME type, ID e proprietário quando
   expostos. Não escolha silenciosamente entre candidatos parecidos.
3. Leia metadata antes das células: registre spreadsheet ID, nomes e IDs das
   abas, ordem, dimensões e revisão se houver. Use os nomes de aba observados;
   nunca adivinhe `Sheet1`, `gid`, coluna, linha ou intervalo.

## Rotas

- Edição de planilha existente: leia as células, fórmulas, formatação e
  validações da faixa exata antes de escrever. Preserve dados fora do alvo.
- Template ou referência: copie o arquivo nativamente se a operação existir e
  confirme que o ID da cópia é diferente antes de alterar. Um link profundo
  para uma aba não reduz automaticamente o escopo da referência.
- Arquivo local XLSX/CSV/TSV: se o usuário pediu importação para Sheets,
  descubra uma ferramenta de upload/conversão ou uma skill local disponível;
  use-a apenas se o esquema confirmar o modo nativo. Sem essa capacidade,
  explique o limite e não finja que uma cópia local virou um Sheet.
- Criação, fórmula, tabela, validação ou gráfico: planeje primeiro a aba e a
  faixa. Se a operação nativa específica não for descoberta, entregue apenas
  as partes verificáveis ou pare antes de degradar a semântica para texto
  simples.

## Leitura, escrita e fórmulas

1. Trabalhe com faixas limitadas e cabeçalhos reais. Para busca de linhas,
   use o intervalo observado e uma consulta suportada pelo esquema; não varra
   a grade inteira nem repita uma busca grande depois de erro de tamanho.
2. Antes de cada passe de escrita, releia a faixa e confirme dimensões,
   fórmulas, tipos, validações, chips, filtros e estilos que possam ser
   afetados. Escreva apenas células/linhas/colunas pedidas e mantenha uma
   lista curta das faixas alteradas.
3. Ao inserir linhas ou colunas, preserve fórmulas, validações, formatação e
   elementos nativos vizinhos conforme a ferramenta permitir. Não substitua
   dropdown, rich link ou fórmula por seu texto visível sem declarar a perda.
4. Trate fórmulas como fórmulas somente quando o runtime confirmar que aceita
   esse tipo. Não altere separadores, locale ou referências sem observar o
   padrão da planilha. Um write aceito não prova que o valor foi recalculado.
5. Para gráficos, leia a configuração/intervalo existente antes de reparar.
   Preserve série, eixo, legenda, posição e estilo quando observáveis; não
   recrie um gráfico por aproximação se a ferramenta não expuser o modelo.

## Verificação

Depois de cada mutação, releia as células e metadata relevantes. Confirme:

- ID, URL, aba e faixa corretos;
- valores, fórmulas, formatos e validações pedidos;
- linhas/colunas fora do alvo preservadas;
- fórmulas recalculadas somente quando a leitura de retorno provar o resultado;
- gráficos ou tabelas nativos presentes, se solicitados e suportados;
- planilha copiada ou importada com o ID esperado.

Se houver uma rota de renderização ou visualização descoberta, use-a para uma
checagem visual de tabelas e gráficos. Sem ela, diga que a verificação foi de
estrutura e valores. Não declare recálculo, chart repair ou importação nativa
sem readback observável.

## Autenticação e limites

Não leia credenciais, cookies, tokens ou variáveis secretas e não faça OAuth
manual. Uma ferramenta visível pode ainda falhar por conta, escopo, permissão,
quota ou arquivo inexistente; informe essa evidência e pare a escrita afetada.
Uma CLI só é alternativa quando estiver instalada, autenticada e autorizada
para o mesmo escopo; confirme seus comandos pela ajuda real e não suponha que
ela edita conteúdo nativo apenas porque lista arquivos. A autorização explícita para editar cobre a ação
solicitada e não exige uma confirmação extra; peça esclarecimento somente se
alvo, faixa ou conteúdo ausente mudar materialmente o resultado.
