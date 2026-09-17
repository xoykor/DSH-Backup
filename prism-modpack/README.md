# Prism Modpack Workbench

Programa local e skill para o agente montar o pack completo e corrigir crashes pelos logs. Python 3.11+, Linux. Sem testes mod por mod nem testes de gameplay obrigatórios.

## Instância preparada

- Nome: **Modpack Lab**.
- Instância: `/home/x/.local/share/PrismLauncher/instances/Modpack-Lab`.
- Workspace: `/home/x/Documentos/DSH/prism-modpack/.modpack-work`.
- Manifesto: `/home/x/Documentos/DSH/prism-modpack/plano.json`.
- Minecraft 1.21.1, NeoForge 21.1.250, Java 21.0.7 selecionado no Prism.
- Conta Microsoft configurada; os scripts não precisam ler tokens.
- 17 JARs, incluindo Create Aeronautics, Gunsmithing e GeckoLib.

O agente toma as decisões. Os programas abaixo executam downloads, instalação, acompanhamento de processos e coleta. Não há modelo embutido nem agendamento instalado.

## Operação pelo agente

Execute os comandos no host, com acesso à rede, ao display e aos processos reais do usuário. Uma sandbox com namespace de PID isolado não consegue observar corretamente o Minecraft. Todos os caminhos abaixo são absolutos, para funcionar fora do diretório do projeto.

```bash
python3 /home/x/Documentos/DSH/prism-modpack/modpack.py --workspace /home/x/Documentos/DSH/prism-modpack/.modpack-work status
python3 /home/x/Documentos/DSH/prism-modpack/modpack.py --workspace /home/x/Documentos/DSH/prism-modpack/.modpack-work launch --observe-seconds 30
python3 /home/x/Documentos/DSH/prism-modpack/modpack.py --workspace /home/x/Documentos/DSH/prism-modpack/.modpack-work collect
python3 /home/x/Documentos/DSH/prism-modpack/modpack.py --workspace /home/x/Documentos/DSH/prism-modpack/.modpack-work diagnose
python3 /home/x/Documentos/DSH/prism-modpack/modpack.py --workspace /home/x/Documentos/DSH/prism-modpack/.modpack-work stop
```

`launch` observa por um período limitado; não fecha o jogo quando esse tempo acaba. `game_wrapper.py`, configurado como WrapperCommand desta instância, registra o PID do Java, a identidade do processo e seu código de saída. `status`/`collect` reconhecem o encerramento e liberam alterações automaticamente. `stop` envia SIGTERM somente ao processo identificado desta instância; não usa killall e não força SIGKILL. Se ele continuar vivo, preserve o bloqueio e investigue. Mundos abertos podem precisar de tempo para salvar.

`finish --game-stopped` é apenas uma recuperação manual para lançamentos anteriores ao wrapper ou falhas antes de iniciar Java. O comando recusa liberar a instância se detectar seu jogo rodando. Sem evento do wrapper, não conclua que o Java terminou apenas porque o launcher saiu.

## Corrigir uma dependência ausente

Exemplo real: o crash informou que NTGL exigia GeckoLib >= 4.8.2. A dependência não constava na resposta de dependências do catálogo. O agente leu o relatório e adicionou GeckoLib 4.9.3.

Após guardar logs e encerrar o jogo:

```bash
python3 /home/x/Documentos/DSH/prism-modpack/modpack.py --workspace /home/x/Documentos/DSH/prism-modpack/.modpack-work record --hypothesis 'NTGL exige GeckoLib >= 4.8.2 segundo o relatório FML' --change 'Instalar GeckoLib compatível com NeoForge 1.21.1'
python3 /home/x/Documentos/DSH/prism-modpack/fetch_mod.py --manifest /home/x/Documentos/DSH/prism-modpack/plano.json --project geckolib
python3 /home/x/Documentos/DSH/prism-modpack/modpack.py --workspace /home/x/Documentos/DSH/prism-modpack/.modpack-work build /home/x/Documentos/DSH/prism-modpack/plano.json
```

`fetch_mod.py` seleciona uma release do projeto para o Minecraft/loader do manifesto, baixa do CDN oficial do Modrinth, verifica SHA-512 e integridade ZIP e acrescenta/atualiza as entradas sem apagar os outros projetos. Resolve dependências obrigatórias declaradas pelo catálogo; as omitidas ainda precisam ser identificadas pelos logs. `--version-id ID` permite fixar outra versão. Ele não instala nada até chamar `build`. Somente JARs e Modrinth estão implementados; não substitua outro tipo de conteúdo silenciosamente.

`build` instala todos os JARs da lista em lote e cria backup. JARs ativos ausentes da lista são removidos: use sempre o manifesto completo. Não execute entre instalações individuais. Mantenha as fontes em `downloads/`, fora da instância.

## Backups e histórico

`snapshot --reason TEXTO` preserva `mods`, `config`, `defaultconfigs` e o lockfile. `rollback ID` verifica hashes e guarda uma cópia do estado atual antes de restaurar. Esses snapshots não incluem mundos, Java, loader ou configuração do Prism; faça backup específico desses itens antes de alterá-los.

Cada execução fica em `runs/ID`: inventário, logs novos/alterados, ciclo de vida e `diagnosis.json`. `attempts.json` registra hipóteses; a implementação bloqueia propostas idênticas no mesmo estado e tem limite inicial de cinco propostas por workspace. Não apague o histórico para contornar o limite. Ao atingi-lo, resuma as evidências e a decisão pendente.

Ausência de erros reconhecidos não comprova estabilidade. O escopo atual é instalar o pack e corrigir crashes observados na inicialização; não é explorar mundos, testar armas ou validar todas as mecânicas.

## Arquivos

- `plano.json`: seleção com versões, hashes e fontes.
- `MODPACK.md`: lista e situação atual.
- `skills/prism-modpack/SKILL.md`: instruções do agente; cópia instalada em `~/.codex/skills/prism-modpack`.
- `tests/`: testes do programa (14 passaram durante a implementação).

Referência: [CLI do Prism](https://prismlauncher.org/wiki/getting-started/command-line-interface/) e [WrapperCommand](https://prismlauncher.org/wiki/help-pages/custom-commands/).
