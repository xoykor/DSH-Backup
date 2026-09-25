---
name: google-drive
description: Roteiar tarefas de Google Drive, Docs, Sheets e Slides no runtime DSH, descobrindo as ferramentas disponíveis e verificando identidade, metadados e resultado antes de qualquer mutação.
---

# Google Drive no DSH

Use esta skill como ponto de entrada para localizar, ler, organizar, copiar,
exportar ou editar arquivos Google. Ela contém instruções instaladas; isso não
prova que há um conector Google instalado ou autenticado nesta sessão.

## Descoberta obrigatória

1. Antes de uma operação Google, procure no catálogo atual por ferramentas com
   `dev_tool_search` (se essa ferramenta estiver visível), usando consultas
   como `Google Drive`, `Google Docs`, `Google Sheets`, `Google Slides` ou
   `Drive comments`.
2. Desbloqueie somente os nomes exatos retornados pelo catálogo. Leia a
   descrição e o esquema de cada ferramenta antes de montar argumentos; o
   verbo desta skill é uma intenção, não um nome de ferramenta garantido.
3. Se `dev_tool_search` não estiver disponível, use ferramentas Google
   visíveis ou uma CLI instalada cuja ajuda e autenticação tenham sido verificadas
   para o escopo autorizado. Não adivinhe nomes, namespaces,
   parâmetros, IDs, URLs ou rotas HTTP. A ausência de `gws` ou `rclone` no
   PATH não é evidência sobre o conector DSH.
4. Uma ferramenta listada ainda precisa ser testada com uma leitura segura:
   confirme que a conta autenticada consegue acessar Drive e o arquivo alvo.
   Para um arquivo novo, use uma leitura de conta ou pasta disponível; não exija
   a leitura de um arquivo que ainda não existe.
   Diferencie no resultado: skill instalada, ferramenta descoberta,
   autenticação confirmada e operação verificada.

## Roteamento

- Use esta skill para busca, metadados, arquivos recentes, pastas, cópia,
  movimentação, compartilhamento, revisões e exportação/download quando a
  tarefa ainda é de ciclo de vida do arquivo.
- Depois de identificar o MIME type e o arquivo exato, carregue a skill
  específica: [Docs](../google-docs/SKILL.md), [Sheets](../google-sheets/SKILL.md),
  [Slides](../google-slides/SKILL.md) ou
  [comentários](../google-drive-comments/SKILL.md). Se o pedido diz “encontre
  e edite”, faça a descoberta aqui e a edição na skill de superfície.
- Para uma solicitação ambígua, deixe o tipo observado do arquivo decidir:
  documento vai para Docs, planilha para Sheets e apresentação para Slides.
  Não peça ao usuário para escolher uma integração antes de consultar o
  arquivo e o catálogo.

## Fluxo seguro

1. Resolva o alvo por URL ou ID fornecido. Se houver apenas título, nome ou
   palavras-chave, pesquise e liste candidatos com nome, MIME type, pais,
   proprietário quando exposto, data e ID; peça desambiguação se restar mais
   de um candidato plausível.
2. Leia metadados antes de buscar bytes ou exportar. Para mover um arquivo,
   leia os pais atuais e o ID da pasta destino; acrescente o novo pai e remova
   somente os pais confirmados que o usuário quer retirar, preservando os
   demais.
3. Para copiar um template ou referência, copie primeiro e edite a cópia.
   Para revisões, leia a revisão atual, descubra se existem operações de
   listagem/obtenção de revisões no catálogo e compare somente revisões que a
   ferramenta devolver. Nunca diga que histórico não existe sem uma tentativa
   de capacidade observável.
4. Escolha exportação ou download conforme o MIME type e o esquema descoberto.
   Não envie um arquivo nativo Google para uma operação que só aceita arquivo
   armazenado, nem o inverso. Respeite limites indicados pelo resultado da
   ferramenta e não prometa streaming, PDF ou base64 sem evidência.
5. Após qualquer escrita, releia metadados ou conteúdo e confirme o ID, a
   URL, a pasta, a revisão ou o estado que mudou. Use somente URLs e IDs
   retornados pela ferramenta; nunca os sintetize.

## Autenticação e limites

Não leia `__DSH_HOME__/.credentials.yaml`, tokens, cookies, cabeçalhos,
armazenamento do navegador ou variáveis de segredo. Não faça OAuth manual,
não peça um bearer token ao usuário e não exponha URLs autenticadas, base64 ou
conteúdo de credencial. Se a ferramenta indicar login ausente, escopo
insuficiente, arquivo sem permissão, quota ou erro do provedor, pare a
mutação, preserve o que já foi feito e reporte o erro literal em forma
resumida. Uma falha de autenticação não autoriza tentar uma ferramenta
alternativa desconhecida.

Preserve organização, permissões, compartilhamento, conteúdo e pais não
abrangidos pelo pedido. Não delete, mova, compartilhe ou sobrescreva por
conveniência. Se a operação de escrita específica não estiver descoberta, a
resposta correta é “indisponível nesta sessão”, com a leitura já verificada e
uma alternativa local somente se o usuário a pedir.

## Verificação final

Antes de concluir, informe de forma curta:

- alvo confirmado e evidência usada;
- ferramenta(s) realmente descoberta(s) e se a autenticação foi verificada;
- ação executada ou limite encontrado;
- leitura de retorno que prova o novo estado, ou a razão objetiva de não haver
  verificação.

Não declare que um arquivo foi criado, alterado, exportado ou compartilhado
apenas porque uma chamada foi aceita: o resultado precisa confirmar a operação.
