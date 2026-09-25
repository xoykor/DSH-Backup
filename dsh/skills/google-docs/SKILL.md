---
name: google-docs
description: Criar, ler, preencher, adaptar e editar Google Docs preservando estrutura, estilo, links, tabelas e controles; usar somente ferramentas descobertas e autenticadas no runtime DSH.
---

# Google Docs no DSH

Use esta skill quando o artefato observado é um Google Doc ou quando o usuário
pede um documento nativo Google. A instalação desta skill não fornece acesso a
Google Docs: primeiro descubra ferramentas e depois prove a autenticação com
uma leitura. Não substitua silenciosamente um Doc por Markdown ou DOCX local.

## Descoberta e estado

Antes de ler ou escrever, procure `Google Docs` no `dev_tool_search` quando ele
estiver disponível e desbloqueie apenas nomes exatos retornados. Se ele não
estiver visível, use apenas as ferramentas presentes no turno. Mapeie as
operações aos esquemas reais: localizar/metadata, ler documento, copiar,
criar, atualizar conteúdo, exportar ou comentar. Não invente `batchUpdate`,
IDs de aba, campos ou parâmetros que o runtime não mostrou.

Registre em notas de trabalho o ID/URL observado, revisão se houver, abas e
ordem, estrutura relevante, ferramenta usada e estado da verificação. Uma
leitura bem-sucedida confirma a conta e o alvo; não confunda isso com a skill
ou a ferramenta estar instalada.

## Roteamento

- Documento existente: leia metadados e o conteúdo/estrutura atual antes da
  primeira escrita. Faça uma cópia nativa antes de adaptar um template ou
  documento de referência; edite no lugar somente quando o usuário pediu isso.
- Template ou referência: enumere todas as abas, títulos, pais e ordem antes
  de ler uma aba em profundidade. Preserve a topologia, cabeçalhos, rodapés,
  tabelas, listas, estilos, links, imagens, chips e controles observados,
  salvo instrução explícita para removê-los. Conteúdo de um projeto passado é
  referência de forma; não carregue nomes, datas, métricas, pessoas, links ou
  afirmações antigas sem autoridade atual.
- Documento novo: pergunte apenas dimensões realmente ausentes para uma
  decisão material, como tema, público ou finalidade de uma grande redação.
  Com essas dimensões claras, prossiga e use placeholders visíveis para fatos
  ausentes; não invente fatos.
- Ao escrever em nome do usuário, carregue
  [write-like-me](../write-like-me/SKILL.md) e aplique-a ao texto.
  Ela orienta voz e redação; não substitui a leitura, a preservação estrutural
  nem a verificação nativa desta skill.

## Autoria e edição

1. Derive a cobertura da solicitação, das fontes autorizadas e das instruções
   do template. Planeje cada requisito, destino e estado antes de escrever.
2. Releia a região alvo e seus estilos atuais imediatamente antes da mutação.
   Faça a menor atualização que resolve o pedido; não reconstrua o documento
   inteiro para uma edição local.
3. Preserve estilos e papéis semânticos de títulos, corpo, tabelas e listas.
   Em caixas ou parágrafos com múltiplos estilos, substitua os trechos
   correspondentes mantendo as divisões; não aplique um estilo único por
   conveniência. Use listas nativas quando a ferramenta expuser essa operação.
4. Só use datas, pessoas, links ricos, dropdowns ou outros elementos nativos
   quando o esquema descoberto realmente os suportar. Para uma data incompleta,
   email não verificado ou URL não confirmada, mantenha o texto/placeholder e
   declare a limitação; nunca adivinhe. Não emule um controle nativo com texto
   se a semântica foi solicitada.
5. Use precondição de revisão se o runtime oferecer uma e ela for relevante
   para colaboração. Divida atualizações grandes em lotes pequenos e
   verificáveis, mantendo os índices vivos após inserções ou remoções.

Não copie uma pessoa, chip, link, aprovação, instrução ou seção de uma
referência apenas para preencher espaço. Não remova conteúdo histórico se o
usuário pediu preservação. Se a ferramenta de cópia, leitura estrutural ou
controle exato não existir, pare antes de uma mutação destrutiva e explique o
que não pode ser provado.

## Verificação

Após criar ou editar, releia o documento com a ferramenta descoberta e confirme:

- ID/URL e revisão do destino;
- abas e ordem preservadas, quando aplicável;
- requisitos e fontes autorizadas cobertos;
- texto, títulos, tabelas, listas, links, imagens e controles no local pedido;
- nenhum fato de referência, placeholder ou conteúdo de exemplo vazou;
- estilos e formatação observáveis continuam coerentes.

Para trabalho sensível a paginação ou visual, procure no catálogo uma rota de
exportação/renderização e verifique o resultado se ela existir. Sem essa
ferramenta, declare que a verificação foi estrutural, não visual. Não afirme
que o Doc foi salvo apenas porque uma chamada não deu erro: exija readback.

## Autenticação e limites

Não leia credenciais, cookies, tokens ou armazenamento do navegador, nem faça
OAuth manual. Não exponha URLs autenticadas, bearer tokens ou base64. Erros de
login, escopo, permissão, quota ou ferramenta ausente são limites do runtime;
relate-os sem tentar nomes alternativos inventados. A autorização explícita do
usuário para criar ou editar já cobre a mutação pedida; não peça confirmação
adicional, apenas pare se faltar uma capacidade técnica ou uma informação que
mude materialmente o resultado.
