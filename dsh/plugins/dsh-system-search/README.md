# dsh-system-search

Plugin local e somente leitura que registra a ferramenta `system_search`.

Ela localiza por nome arquivos, diretórios, executáveis, aplicativos instalados e
dados de aplicativos. O escopo `smart` procura no workspace, no `PATH`, em locais
ocultos do usuário (`~/.local/share`, `~/.config`, `~/.cache`) e em diretórios
comuns de aplicativos do sistema. A ferramenta não lê conteúdo nem modifica o
sistema de arquivos.

O caso de regressão que motivou o plugin é a busca por “Prism Launcher” sem um
caminho previamente conhecido: o resultado deve identificar
`~/.local/share/PrismLauncher` como diretório oculto, evitando usar `which` para
dados de usuário ou enviar um diretório à ferramenta de leitura de arquivos.

Exemplo:

```json
{"query":"Prism Launcher","kind":"any","scope":"smart"}
```

Raízes explícitas aceitam `~`, `$HOME`, `$XDG_DATA_HOME`, `$XDG_CONFIG_HOME` e
`$XDG_CACHE_HOME`. Tempo, profundidade, número de entradas examinadas e resultados
são limitados e informados na resposta.
