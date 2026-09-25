---
name: google-slides
description: Editar, adaptar, reparar e verificar apresentações Google Slides preservando template, hierarquia, mídia e legibilidade, com ferramentas descobertas e autenticadas no runtime DSH.
---

# Google Slides no DSH

Use esta skill quando o artefato é uma apresentação Google Slides existente ou
quando o usuário fornece um deck nativo como template/referência. A presença
da skill não significa que o DSH tenha integração Google ou renderizador;
confirme cada capacidade no catálogo e no readback.

## Descoberta e rota

Antes de operar, procure `Google Slides` no `dev_tool_search` quando ele estiver
visível e desbloqueie apenas ferramentas com nomes exatos retornados. Leia seus
esquemas para descobrir leitura de apresentação, cópia, atualização, mídia,
exportação e comentários. Não invente `presentations.batchUpdate`, IDs de
slide, layouts, campos ou parâmetros.

- Deck existente: leia metadata e o texto/estrutura atual antes de escrever.
- Template ou referência: copie o deck nativamente quando possível e confirme
  um ID diferente antes de editar. Enumere todos os slides, ordem, IDs,
  layouts, placeholders, notas e mídias; um link profundo não limita o escopo.
- Criação do zero: use uma skill local de apresentações ou uma ferramenta
  nativa somente se ela for encontrada no runtime e o usuário tiver pedido
  essa rota. Não transforme um pedido de Google Slides em PPTX local sem
  declarar a substituição e obter a escolha do usuário quando ela for
  material.

## Construção e edição

1. Derive o papel narrativo, conteúdo obrigatório e densidade de cada slide.
   Ao seguir um template, escolha um exemplar por papel, hierarquia, evidência
   e densidade; não por quantidade de objetos.
2. Reaproveite estrutura, estilos, caixas, tabelas, rodapés, links e mídia do
   exemplar. Mapeie cada imagem/vídeo para manter, substituir ou remover;
   nunca deixe placeholder ou fotografia de exemplo sem decisão.
3. Preserve fontes, pesos, tamanhos, cores, estilos de parágrafo e geometria.
   Em caixas com estilos mistos, substitua os trechos mantendo os runs e
   intervalos. Use bullets nativos quando expostos; não digite `-` ou `•` para
   imitar uma lista e não deixe bullets vazios.
4. Preserve a proporção intrínseca de imagens, vídeos, screenshots e gráficos.
   Ajuste crop/fit somente após observar dimensões e significado da mídia;
   conteúdo informativo deve caber inteiro. Não rasterize texto editável para
   conservar aparência.
5. Remova conteúdo stale do exemplar e slides de biblioteca somente depois de
   conferir o conjunto final e a ordem. Faça uma mutação de reordenação
   separada quando o esquema exigir IDs únicos.

Não reduza corpo narrativo a tamanho ilegível para salvar um exemplar errado.
Se o conteúdo não couber, encurte apenas texto flexível sem perder requisitos,
escolha um exemplar adequado ou declare o conflito.

## Verificação estrutural e visual

Após escrita, releia a apresentação e confirme IDs, contagem, ordem, títulos,
texto, links, mídia e estilos observáveis. Procure no catálogo uma ferramenta
de exportação/renderização para PDF ou imagens e, se existir, inspecione todas
as páginas/slides; corrija erros de overflow, placeholders, bullets, mídia
esticada ou slides vazios antes da entrega. Sem renderizador descoberto,
declare que a verificação é somente estrutural e não afirme qualidade visual.

Faça no máximo as passagens de reparo necessárias ao defeito observado; cada
mudança estrutural exige novo readback e invalida uma renderização anterior.
Não remova slides ou mídia com base apenas em memória ou em um snippet de
busca.

## Autenticação e limites

Não leia credenciais, tokens, cookies ou armazenamento do navegador e não faça
OAuth manual. URL/ID devolvido por uma ferramenta autenticada é a única forma
aceitável de reportar um destino. Falhas de conta, escopo, permissão, quota,
exportação ou renderização são limites desta sessão; não tente uma API ou
namespace inventado. A autorização explícita para editar já autoriza a
mutação solicitada; não peça confirmação extra, mas pare antes de destruir
estrutura que não possa ser lida ou verificada.

