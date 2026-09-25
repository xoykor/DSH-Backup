---
name: sites-preview-troubleshooting
description: Diagnosticar e recuperar falhas de preview local ou supervisionado de um site com evidência delimitada, sem matar processos desconhecidos nem confundir preview com publicação.
---

# Diagnóstico de preview

Use somente depois que o projeto foi preparado por `sites-building` e o preview
falhou ao iniciar, encerrou, expirou ou ficou inacessível. Este fluxo cobre o
runtime local/supervisionado disponível no DSH; não pressupõe um daemon,
comando, navegador ou endereço específico.

## Coletar evidência

1. Preserve a saída completa da última tentativa, incluindo o trecho final do
   servidor, código de saída e tempo limite. Oculte tokens, cookies, chaves,
   valores de ambiente e URLs com credenciais antes de registrar qualquer coisa.
2. Consulte o status do mesmo preview, se a ferramenta oferecer `status`.
   Confirme a raiz canônica, a existência do manifest, o script de
   desenvolvimento, o lockfile e a configuração relevante sem ler segredos.
3. Quando a falha mencionar porta, identifique o dono com uma consulta
   delimitada (`ss`/`lsof` ou equivalente). Pare apenas a sessão, job ou PID do
   servidor que esta tarefa iniciou e que foi registrado; nunca use `pkill`,
   `killall`, `kill -9` amplo ou elimine processos de outro projeto.

Carregue `tool-first` para a investigação. Use `verificacao-projeto` para
dependências e checks, `execucao-longa` se o servidor/build for gerenciado como
job, e `jornadas-navegador` somente quando existir uma ponte disponível e o
comportamento precisar ser conferido. Não faça varredura repetida de portas nem
abra o navegador em cada tentativa.

## Classificar e corrigir

Classifique a evidência antes de editar:

- **Ferramenta/daemon ausente ou indisponível:** não instale, recrie ou altere
  o daemon por conta própria; registre a limitação e siga para o build local.
- **Raiz inválida:** use o checkout autorizado, com caminho real dentro do
  projeto e manifest presente. Não copie o site para contornar a regra.
- **Porta ocupada:** consulte o processo, encerre somente o preview próprio se
  houver identificação inequívoca e faça uma nova tentativa. Não troque a porta
  às cegas nem mate um processo desconhecido.
- **Servidor encerra ou expira:** confira dependências instaladas pelo lockfile,
  script de desenvolvimento e se os argumentos encaminhados (`host`, `port` e
  modo estrito, quando aplicável) chegam ao servidor. Faça o menor reparo de
  configuração compatível com o stack; não substitua um framework funcionando
  por outro.
- **Navegador não alcança o preview:** confirme que o servidor está `running` e
  use somente o endereço exato fornecido pela ferramenta no contexto autorizado.
  Não navegue para produção, HTTPS, loopback de outro contexto ou outra porta.
- **Página carrega com erro:** trate como defeito do projeto, corrija a fonte,
  aguarde o reload do mesmo servidor e valide a interação que falhou.

Faça no máximo duas tentativas de início, contando a original. A segunda exige
um reparo concreto ou recuperação plausível do ambiente; repetir o mesmo
comando não é diagnóstico. Preserve dependências, arquitetura, scripts e
configuração de hospedagem do projeto.

## Encaminhar o resultado

Se o preview funcionar, registre comando, raiz, URL interna sem expor detalhes
desnecessários, verificação realizada e reparo aplicado. Se permanecer
indisponível por infraestrutura, navegador, porta ou runtime restrito, pare as
tentativas e continue com checks/build local; `sites-hosting` pode receber um
artefato validado se a publicação tiver sido pedida. Relate separadamente fatos,
hipóteses, tentativas, código de saída, artefatos e a limitação restante. Nunca
declare o site publicado por ele ter compilado ou por existir um arquivo de
preview.
