# Executor de scratch tools

`run_scratch.py` é um executor de investigação local para scripts curtos. Ele exige Bubblewrap (`bwrap`) e falha fechado se o isolamento não puder ser criado.

## Interface

```text
python3 run_scratch.py --language {lua,bash,python} --script SCRIPT --root ROOT [opções] -- [argumentos]
```

- `--root` é montado como `/input`, somente leitura.
- `--script` é montado como `/runner/script`, somente leitura.
- `/scratch` é temporário e gravável apenas dentro da sandbox.
- `--timeout-ms` aceita 100–60000 ms; o padrão é 10000.
- `--output-limit-bytes` aceita 1024–1048576; o padrão é 1048576.
- `--memory-limit-mib` aceita 32–512; o padrão é 256.

O processo recebe um ambiente mínimo, `HOME=/tmp`, `PATH=/usr/bin:/bin` e locale UTF-8. Não recebe credenciais, rede ou acesso ao diretório pessoal.

## Resposta

A saída é um único objeto JSON compacto com `status`, `exit_code`, `signal`, `elapsed_ms`, `stdout`, `stderr`, bytes observados e `output_truncated`. `status` pode ser `completed`, `failed`, `timeout`, `output_limit` ou `cancelled`.

Um erro de sandbox é `failed`; o executor nunca tenta executar o script fora do isolamento. `stdout` e `stderr` são truncados para manter a resposta abaixo de 5.500 bytes, preservando o início e o fim.
