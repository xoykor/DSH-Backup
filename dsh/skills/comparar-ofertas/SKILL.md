---
name: comparar-ofertas
description: Comparar ofertas atuais de um produto e recomendar a melhor opção pelo custo total, variante equivalente, entrega e confiabilidade. Use para achar o menor preço ou a melhor compra; não para histórico de preços ou planejamento de orçamento.
---

# Comparar ofertas

Encontre a melhor oferta verificável de um produto entre as fontes acessíveis no momento da consulta. A conclusão deve ser limitada às ofertas encontradas: não diga que é a melhor da internet inteira.

## Escopo antes da busca

Defina, a partir do pedido:

- produto exato, modelo, SKU/EAN/ISBN ou outra identificação;
- variante: capacidade, cor, voltagem, tamanho, kit e condição (novo, usado ou recondicionado);
- país, região ou CEP de entrega, quando o frete ou impostos dependerem disso;
- moeda, prazo máximo, preferência por loja oficial/marketplace e forma de pagamento.

Se faltar uma informação que possa mudar o vencedor, faça uma pergunta curta. Caso seja possível avançar, assuma explicitamente um valor razoável e marque a suposição no resultado. Nunca trate uma versão parecida como equivalente sem avisar.

## Busca e verificação

1. Use `web_search` para descoberta, em consultas pequenas e específicas. Ela aceita no máximo quatro consultas por chamada. Combine o nome exato do produto com termos como `preço`, `comprar`, a região e, quando útil, o identificador do modelo. Inclua varejistas relevantes e marketplaces, mas não presuma que um domínio é confiável só por aparecer primeiro.
2. Abra as páginas de produto com `web_fetch` quando essa ferramenta estiver registrada; se a página depender de conteúdo dinâmico, use a automação de navegador registrada. Snippets e títulos de resultados servem apenas para descoberta, nunca como prova suficiente do preço.
3. Para cada oferta, registre a URL direta, loja, vendedor e o horário/data da consulta. Confirme na página a variante, condição, disponibilidade, preço, frete e prazo sempre que possível. Se um campo não puder ser confirmado, escreva `não verificado` em vez de inferi-lo.
4. Não contorne login, CAPTCHA, paywall, robots.txt ou bloqueios. Não faça login, compra, cadastro ou contato com vendedores em nome do usuário.

## Comparabilidade e custo

Considere equivalentes apenas ofertas do mesmo modelo e da mesma variante. Verifique especialmente capacidade, voltagem, acessórios incluídos, idioma/região, condição, garantia e se o anúncio é do fabricante ou de terceiro. Separe ou exclua anúncios de acessórios, anúncios incompletos e variantes incompatíveis.

Calcule o custo comparável como:

`preço final = preço do item + frete + taxas/impostos obrigatórios - descontos incondicionais`

Mantenha separados, sem transformar em desconto garantido:

- cupom que exige ação ou elegibilidade;
- preço exclusivo para assinatura, cartão ou método de pagamento específico;
- cashback futuro, pontos e benefícios não monetários;
- parcelamento e juros;
- imposto ou frete calculado apenas após informar o destino.

Não converta moedas silenciosamente. Se a comparação entre moedas for necessária, informe a taxa e a data da conversão; se não houver base confiável, compare por moeda ou marque o total como não comparável.

## Critério de recomendação

O vencedor principal é a oferta equivalente, em estoque e verificável, com menor custo final entregue. Em empate ou diferença pequena, desempate nesta ordem: vendedor/loja mais confiável, garantia e devolução mais claras, entrega mais rápida e menor dependência de cupom ou condição especial.

Se o menor preço tiver uma desvantagem relevante, apresente também uma alternativa de “melhor equilíbrio” e explique o trade-off. Ofertas com dados incompletos podem aparecer como candidatas, mas não devem vencer com base em um total estimado.

## Formato da resposta

Informe primeiro a recomendação e a data/hora da verificação. Depois apresente uma tabela curta com, no mínimo:

`posição | loja/vendedor | variante e condição | preço | frete/taxas | custo final | entrega | garantia/devolução | fonte`

Inclua até três alternativas relevantes. Marque cada total como `confirmado`, `estimado` ou `não verificado`, e indique as condições do preço (cupom, assinatura, cartão ou região). Finalize com:

- por que a recomendação ganhou;
- suposições feitas;
- riscos e itens ainda não confirmados;
- a data da consulta, pois preço e estoque mudam.

Use linguagem como “melhor entre as ofertas verificadas”. Nunca invente preço, frete, estoque, prazo, reputação ou cupom para preencher lacunas.
