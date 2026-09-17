# Operação do Prism Modpack

Os comandos abaixo usam a instalação live do DSH. Em uma restauração, os
marcadores `__DSH_HOME__` e `__HOME__` são materializados automaticamente.

Os únicos programas desta skill são `scripts/modpack.py`,
`scripts/fetch_mod.py` e `scripts/game_wrapper.py`. Nomes como `status`,
`configure-wrapper`, `build`, `launch`, `collect`, `diagnose` e `stop` são
subcomandos de `modpack.py`, não arquivos `.sh`. Não chame `status.sh` nem
`configure-wrapper.sh`: esses arquivos não existem.

```bash
SKILL=__DSH_HOME__/skills/prism-modpack
WORK=__HOME__/.local/share/prism-modpack/Modpack-Lab
PLAN="$WORK/plano.json"

python3 "$SKILL/scripts/modpack.py" --workspace "$WORK" status
python3 "$SKILL/scripts/modpack.py" --workspace "$WORK" configure-wrapper
python3 "$SKILL/scripts/fetch_mod.py" --manifest "$PLAN" --project geckolib
python3 "$SKILL/scripts/modpack.py" --workspace "$WORK" build "$PLAN"
python3 "$SKILL/scripts/modpack.py" --workspace "$WORK" launch --observe-seconds 30
python3 "$SKILL/scripts/modpack.py" --workspace "$WORK" collect
python3 "$SKILL/scripts/modpack.py" --workspace "$WORK" diagnose
python3 "$SKILL/scripts/modpack.py" --workspace "$WORK" stop
```

O agente pode substituir `geckolib` por slug ou ID de outro projeto Modrinth e
usar `--version-id ID` para fixar uma versão. `fetch_mod.py` somente atualiza o
manifesto e o diretório `downloads/`; `build` efetiva a instalação.

Para registrar uma correção:

```bash
python3 "$SKILL/scripts/modpack.py" --workspace "$WORK" record \
  --hypothesis 'causa sustentada pelo relatório FML' \
  --change 'alteração exata aplicada ao manifesto ou configuração'
```

Crie outra vinculação somente com uma instância de teste fechada:

```bash
python3 "$SKILL/scripts/modpack.py" --workspace /caminho/estado init \
  --instance /caminho/PrismLauncher/instances/MinhaInstancia
python3 "$SKILL/scripts/modpack.py" --workspace /caminho/estado configure-wrapper
```

Workspace e instância devem ser diretórios separados. O programa gerencia
`mods`, `config` e `defaultconfigs`; mundos, loader, Java e preferências do
Prism não fazem parte dos snapshots. Antes de alterar esses itens, crie backup
específico.

Cada execução fica em `runs/ID`, com inventário, ciclo de vida, logs coletados
e `diagnosis.json`. `snapshot --reason TEXTO` cria um ponto de restauração;
`rollback ID` valida hashes e salva o estado atual antes de restaurar.

Se o diretório de dados do Modpack Lab não existir após uma restauração do DSH,
use `assets/modpack-lab-plan.json` como manifesto de recuperação. Os JARs não
são distribuídos com a skill; baixe novamente cada projeto pelo Modrinth antes
de executar `build`.

O launcher pode encerrar enquanto o Minecraft continua ativo. Considere o
evento do wrapper e `status`, não apenas o código de saída do Prism. Se `stop`
não encerrar o processo com SIGTERM, preserve o bloqueio e investigue; o helper
não força SIGKILL.
