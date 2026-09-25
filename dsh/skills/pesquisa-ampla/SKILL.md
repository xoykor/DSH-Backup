---
name: pesquisa-ampla
description: Planejar e executar pesquisas web amplas, cobrindo muitos domínios com consultas em lotes, deduplicação, verificação de fontes e métricas de cobertura. Use para levantamentos de mercado, panoramas, monitoramento e varreduras de centenas de sites; não para uma consulta externa simples.
---

# Pesquisa web ampla

Use esta skill quando a resposta depender de varrer muitas fontes externas e o usuário precisar de cobertura, comparação ou descoberta, não apenas de alguns links. A busca deste DSH usa `web_search`, normalmente fornecido pelo SearXNG local; use `web_fetch` para verificar páginas somente quando a ferramenta estiver registrada.

## Limites e interpretação

- “Todos os sites” só pode significar exaustividade se o universo estiver definido: lista de domínios, diretório, registro, país, setor ou outra fonte de cobertura. Sem universo definido, declare que o resultado é uma varredura ampla, não um censo da web.
- Diferencie URL, página, domínio registrável e organização. Espelhos, republicações e subdomínios da mesma organização não contam como sites independentes sem justificativa.
- Não contorne login, paywall, CAPTCHA, robots.txt, limites de taxa ou controles de acesso. Não colete conteúdo privado nem dispare requisições desnecessárias.
- Snippets de busca servem para descoberta, não para sustentar afirmações. Toda conclusão importante precisa de página aberta, fonte primária ou corroboracão independente registrada.
- O número de páginas deve ser proporcional ao objetivo. Prefira ampliar a diversidade de domínios antes de aprofundar várias páginas do mesmo domínio.

## Fluxo operacional

1. Delimite pergunta, data de corte, idiomas, regiões, tipos de fonte, exclusões, resultado esperado e meta de cobertura. Registre também o que não será possível inferir.
2. Monte uma matriz de consultas: termos centrais, sinônimos, variantes linguísticas, nomes de entidades, categorias de fonte, consultas temporais e consultas com `site:` quando houver um universo conhecido. `web_search` aceita no máximo quatro consultas por chamada; agrupe consultas relacionadas em ondas numeradas.
3. Faça uma fase de descoberta. Colete URL, título, data, domínio, consulta que encontrou o resultado, idioma aparente e uma classificação inicial (`primary`, `secondary`, `discovery`). Preserve também falhas e resultados excluídos com o motivo.
4. Normalize e deduplicate antes de abrir páginas: remova fragmentos, normalize host e esquema, identifique URLs canônicas quando a página informar uma, e agrupe por domínio registrável e organização. Mantenha a relação `duplicate_of` em vez de apagar silenciosamente.
5. Faça a triagem por relevância e diversidade. Em cada onda, priorize fontes primárias, entidades independentes, domínios ainda não cobertos e resultados que respondam a lacunas da matriz. Não conte páginas de uma única rede como cobertura ampla.
6. Verifique uma amostra suficiente de cada grupo. Use `web_fetch` para páginas prioritárias; registre título, editor/organização, data de acesso, trecho mínimo que sustenta a afirmação, limitações e claims associados. Se a abertura falhar, marque `failed` e não transforme o snippet em evidência.
7. Repita descoberta, deduplicação e verificação até atingir a meta ou saturação. Considere saturação quando duas ondas consecutivas trouxerem poucas fontes novas e relevantes, quando as novas fontes apenas repetirem fatos já vistos ou quando o orçamento de consultas/fetches for atingido. Informe qual condição encerrou a busca.
8. Gere relatório com cobertura e incerteza: consultas e ondas executadas, URLs candidatas, domínios únicos, organizações únicas, páginas verificadas, fontes primárias, duplicatas, falhas, distribuição por idioma/região/categoria, claims sustentados e lacunas restantes.

## Escala recomendada

Para pedidos que dizem “centenas de sites”, use um corpus persistente em lotes. Como ponto de partida, mire pelo menos 200 URLs candidatas e 100 domínios únicos; a meta de páginas verificadas pode ser menor quando a finalidade for descoberta, mas deve ser explícita. Se a finalidade for comparar afirmações, verifique mais páginas e reduza o peso de snippets.

Não tente fazer centenas de fetches em uma única sequência sem salvar progresso. Após cada onda, atualize o manifesto do corpus e, se o limite de ferramentas ou contexto for alcançado, entregue um checkpoint com o próximo lote de consultas. A busca só é “sistemática” se o manifesto permitir reproduzir o caminho de descoberta e explicar o que ficou de fora.

## Registro e saída

Para corpora ou pesquisas com mais de uma onda, use o formato descrito em [references/corpus-schema.md](references/corpus-schema.md). Valide o manifesto antes de concluir:

```bash
python3 scripts/validate_corpus.py --input CORPUS.json
```

O relatório final deve separar `fact` (a fonte declara explicitamente) de `inference` (dedução apoiada por uma ou mais fontes) e incluir, no mínimo:

- pergunta, escopo e data de consulta;
- método e matriz de consultas;
- contagens de cobertura e critérios de parada;
- fontes consultadas com URL, título, domínio, data e evidência;
- síntese sem extrapolar além do corpus;
- falhas, vieses de cobertura, conteúdo inacessível e o que não foi verificado.

Para uma pesquisa externa pequena, use `pesquisa-fontes`; esta skill existe para o modo amplo e rastreável.
