---
name: sites-building
description: Criar ou ajustar um site completo no projeto local DSH, com experiência responsiva, acessível e verificável; use quando o pedido é o site em si, não uma manutenção genérica de outro projeto.
---

# Construção de sites

Use esta skill quando a pessoa pedir uma página, site, landing page, portfólio,
dashboard, portal, rastreador ou ferramenta web completa. Trabalhe no diretório
autorizado e entregue uma experiência utilizável; não invente um provedor de
hospedagem, conector ou runtime que não esteja disponível nesta sessão.

## Preparar

1. Carregue `tool-first` antes de investigar arquivos. Localize o projeto,
   instruções, manifests, entrada da aplicação e assets com ferramentas
   determinísticas. Não abra `.env`, chaves, tokens, cookies ou outros arquivos
   de segredo; use apenas nomes de variáveis quando forem necessários.
2. Preserve a estrutura existente, o gerenciador de pacotes, o lockfile, os
   scripts e as integrações. Para HTML/CSS pequeno, carregue
   `paginas-estaticas`; para um projeto com framework, use os comandos reais
   descobertos no manifest. Não troque de stack apenas para padronizar.
3. Entenda o público, a tarefa principal e o menor escopo coerente. Implemente
   o produto solicitado na primeira tela: uma ferramenta deve abrir na área de
   trabalho, e uma página narrativa deve abrir no conteúdo pedido. Não acrescente
   rotas, autenticação, persistência, formulários, busca ou chamadas externas
   sem necessidade do pedido.

## Implementar

Faça uma passagem completa e coerente, incluindo estados vazios, carregamento,
erro e sucesso quando a funcionalidade exigir. O resultado deve:

- funcionar em celular e desktop sem recorte nem rolagem horizontal acidental;
- usar HTML semântico, foco visível, labels acessíveis, teclado e toque quando
  houver controles;
- manter texto legível com contraste, espaçamento e tamanhos que continuem
  utilizáveis ao ampliar a fonte;
- ter hierarquia visual, metadados básicos e conteúdo específico do pedido;
- usar apenas assets fornecidos ou criados de modo autorizado, com caminhos
  locais verificáveis e sem URLs inventadas ou placeholders pendentes.

Preserve a identidade visual de um site existente. Em um site novo, escolha uma
direção visual simples e aplique-a de modo consistente a layout, tipografia,
cores, superfícies e estados. Não transforme um pedido funcional em um mockup
ou em uma página que anuncia a própria aplicação.

## Verificar e visualizar

Depois de cada mudança significativa, valide o próximo risco real:

- Carregue `verificacao-projeto` e descubra os checks declarados antes de
  executá-los; não invente `lint`, `test` ou `build`. Execute os checks e o build
  apropriados ao projeto.
- Para site estático, siga `paginas-estaticas` para conferir a entrada, links,
  referências de assets, caminhos fora da raiz e meta viewport.
- Para builds, conversões ou servidores que possam exceder o limite, carregue
  `execucao-longa`; registre o `job_id`, acompanhe o mesmo job e só declare
  sucesso com estado terminal e artefato conferido.
- Se a tarefa exigir comportamento no navegador e houver ponte disponível,
  carregue `jornadas-navegador`, use uma jornada curta com asserções explícitas
  e guarde o relatório. Uma asserção DOM não substitui inspeção visual.

Abra um preview somente quando houver uma ferramenta local autorizada e uma
versão mínima coerente para mostrar. Use a URL exata informada pelo processo,
uma sessão/aba estável e um único servidor do projeto. Não escaneie portas nem
abra repetidamente o navegador. Falhas do preview seguem
`sites-preview-troubleshooting`; não mate processos desconhecidos.

## Encerrar

Se a pessoa pediu apenas implementação local, entregue os arquivos e as
verificações sem publicar. Se pediu publicação, passe o projeto pronto para
`sites-hosting`; essa skill decide se há ferramenta/provedor disponível e
autorizado. Ao relatar o trabalho, registre caminhos alterados, comandos de
verificação, resultados, limitações de preview e qualquer próximo passo. Não
apresente um preview local como site publicado.
