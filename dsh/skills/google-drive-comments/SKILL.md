---
name: google-drive-comments
description: Criar, responder e resolver comentários em Drive, Docs, Sheets e Slides com evidência de localização, usando apenas capacidades de comentários descobertas e autenticadas no runtime DSH.
---

# Comentários Google no DSH

Use esta skill para comentários, revisão por comentários, respostas e
resoluções em arquivos Google. A skill instalada não confirma que a sessão
possui uma ferramenta de comentários ou acesso autenticado.

## Descoberta e alvo

Procure `Drive comments` ou `Google comments` no `dev_tool_search` se ele
estiver visível; desbloqueie apenas os nomes exatos retornados e leia os
esquemas. Se a busca não estiver disponível, use somente ferramentas visíveis.
Não invente `create_comment`, `reply`, `resolve`, campos de âncora, limite de
lote ou ID de comentário.

Resolva o arquivo por URL/ID ou busque candidatos. Leia metadata e identifique
se a superfície é Doc, Sheet, Slides ou arquivo genérico antes de redigir.
Depois leia o trecho que receberá o comentário: texto ao redor em Docs,
aba/faixa/células em Sheets e slide/texto ou thumbnail em Slides. Não use
snippet, memória, número de slide, aba ou célula presumidos.

## Evidência e mutação

1. Rascunhe todos os comentários, respostas e resoluções antes da escrita.
   Preserve texto, tom e escopo pedidos pelo usuário; não use comentário para
   editar o conteúdo do arquivo.
2. Cada comentário de topo precisa ter evidência legível no próprio corpo e,
   se o esquema suportar, o campo de localização correspondente:
   - Docs/texto: cite a frase, título ou trecho exato;
   - Sheets: nome da aba e faixa A1, como `Orçamento!C12` ou `Dados!A2:D10`,
     além do valor/cabeçalho quando útil;
   - Slides: número do slide e texto visível, título, rótulo ou gráfico;
   - arquivo genérico: nome do arquivo e seção/página/marca temporal
     observada, ou deixe claro que o comentário é de nível arquivo.
3. Rejeite comentários vagos como “nesta frase”, “nesta célula” ou “neste
   slide” sem evidência correspondente. Se não puder localizar o alvo,
   transforme-o em resumo explícito de nível arquivo ou não o envie.
4. Para resposta ou resolução, use IDs de threads/comentários lidos da sessão.
   Não adivinhe âncoras nem suponha que a UI mostrará uma âncora criada pela
   API. Se o runtime oferecer lote, use-o dentro do limite informado; caso
   contrário, execute chamadas individuais que o esquema suporte.

## Verificação e limites

Após cada escrita, releia threads ou metadata e informe quantos comentários
foram criados, respondidos e resolvidos. Confirme os IDs retornados e associe
os comentários de maior risco à evidência usada. Se só houver leitura, não
afirme que algo foi comentado.

Não leia tokens, cookies, credenciais ou armazenamento do navegador e não faça
OAuth manual. Ferramenta ausente, conta sem escopo, arquivo sem permissão,
limite de lote ou erro de API deve ser reportado como limite observável; não
tente um namespace alternativo inventado. A autorização explícita do usuário
para comentar, responder ou resolver já cobre a mutação pedida e não exige
confirmação extra.

