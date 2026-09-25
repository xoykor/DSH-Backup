---
name: sites-hosting
description: Preparar e hospedar um site quando a publicação foi pedida, usando somente uma ferramenta ou provedor descoberto e autorizado na sessão; não use para apenas criar arquivos locais.
---

# Hospedagem de sites

Use esta skill depois de construir um site quando a pessoa pedir publicar,
fazer deploy, colocar no ar ou configurar hospedagem. A disponibilidade de uma
ferramenta é uma hipótese a verificar: não presuma conector, CLI, credencial ou
provedor.

## Descobrir e preparar

1. Confirme o projeto e leia apenas manifests, configuração de hospedagem já
   existente e scripts relevantes. Não leia conteúdo de `.env`, tokens, chaves,
   cookies ou arquivos de credenciais.
2. Carregue `tool-first` para procurar ferramentas determinísticas. Confira
   comandos instalados e ferramentas DSH disponíveis com seus mecanismos de
   ajuda, sem executar publicação. Reutilize o provedor configurado no projeto.
   Se o destino continuar ambíguo e a escolha afetar custo ou acesso, peça a escolha antes da mutação externa. Se não
   houver ferramenta/provedor autorizado, informe o bloqueio e ofereça somente
   um artefato local ou instruções; nunca alegue que o site foi hospedado.
3. Carregue `verificacao-projeto` e execute somente os checks reais do projeto.
   Construa a saída conforme o script e o lockfile existentes. Para sites
   estáticos, siga `paginas-estaticas`; para pacote, build ou upload demorados,
   carregue `execucao-longa` e acompanhe o mesmo job.

## Empacotar com segurança

Use o diretório de saída produzido pelo build, ou os arquivos estáticos
explicitamente configurados. Confira a entrada esperada, referências locais e
um tamanho/contagem plausível. Exclua `.git`, `node_modules`, caches, arquivos
`.env*`, chaves, logs com dados sensíveis e symlinks que escapem do projeto.
Não altere dependências ou o lockfile só para satisfazer um provedor.

Mantenha a configuração de acesso, domínio, variáveis e bindings existentes.
Respeite a audiência solicitada e as operações de infraestrutura autorizadas.
Não amplie acesso, troque DNS ou remova versões além desse escopo. Valores secretos devem ser inseridos pelo mecanismo seguro do
provedor, se ele existir, sem aparecer em argumentos, arquivos temporários,
saída ou relatório.

## Publicar e verificar

Uma solicitação explícita de publicação autoriza a operação dentro do projeto,
mas ainda exige que o provedor seja realmente identificado e que seus comandos
sejam confirmados pela ajuda/documentação local. Use a interface nativa ou a CLI
descoberta; não invente flags, URLs, IDs ou etapas de autenticação. Antes de uma
ação destrutiva ou de mudança de audiência sem autorização, peça direção específica.
Não peça confirmação novamente para uma operação já explicitamente autorizada.

Após publicar, aguarde o estado terminal com o mecanismo nativo do provedor.
Registre provedor, projeto, versão/commit quando fornecidos, status e a URL
retornada literalmente. Se houver uma URL autorizada para verificar, use uma
requisição limitada ou `jornadas-navegador` com asserções; não transforme uma
resposta HTTP isolada em aprovação visual. Não siga redirecionamentos carregando
credenciais.

Se o build, upload, permissão ou status falhar, preserve a saída e relate o
erro concreto, o artefato produzido e o próximo passo seguro. Não repita uma
publicação incerta sem primeiro resolver seu estado.
