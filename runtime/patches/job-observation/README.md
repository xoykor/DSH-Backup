# Observação de jobs e context guard

Patch local para `@deepseek-ai/dsh-tool-jobs@0.1.2-rc.1`, usado pelo runtime
DSH `0.1.5-rc.2`. O payload preserva o executor original e sua licença MIT.

`job_output` e `job_list` publicam uma capacidade de leitura na definição real
registrada (`Symbol.for('dsh.executor.jobObservation.v1')`). O guard resolve essa
definição no escopo do agente; nomes e argumentos fornecidos pelo modelo não
concedem a capacidade. A observação consulta o registro com isolamento de sessão
e não consome saída. `job_kill` e edições de objetivos não ganham essa capacidade.

`job_output(wait:true)` retorna `waitExpired:true` se a espera expirar com o job
ainda `running`/`stopping`. Isso é uma consulta bem-sucedida de estado pendente,
não um timeout de execução. Cancelar a espera não cancela o job gerenciado.

O guard reconhece esperas bloqueantes de pelo menos 1000 ms (normalmente use
30000 ms) por jobs ativos e a primeira coleta terminal de cada job. Essas
observações são neutras para a detecção de investigação repetida: não criam
progresso, não apagam falhas anteriores e não renovam orçamento. Consultas rápidas
e releituras de resultados finais continuam limitadas. Os limites totais de
chamadas, tempo e tokens e os limites diagnósticos continuam valendo entre
continuações automáticas. Uma notificação não reabre um turno encerrado pelo guard.

## Aplicação e verificação

O `restore-dsh.sh restore` aplica este patch ao runtime que acabou de instalar;
`restore-dsh.sh verify` exige o hash corrigido. Para um runtime já instalado:

```sh
node runtime/patches/job-observation/apply-job-observation.mjs
node runtime/patches/job-observation/apply-job-observation.mjs --check
```

O aplicador resolve o pacote a partir de `dsh` no PATH. Use `--target` com o
diretório do pacote ou `lib/index.js` para escolher outra instalação. Somente os
hashes base e corrigido do manifesto são aceitos; alterações externas causam
recusa. A aplicação é atômica, cria backup do original uma vez e é idempotente.
`--check` não escreve: código 0 = corrigido, 2 = original, 1 = incompatível/erro.

Um processo DSH já iniciado mantém os módulos carregados em memória. Reinicie-o
somente quando os jobs relevantes puderem terminar: reiniciar o host perde o
registro de jobs em memória. Instalar estes arquivos não reinicia o DSH.

## Testes

Na raiz do repositório, com o runtime instalado:

```sh
node --test --test-isolation=none dsh/plugins/dsh-context-guard/tests/job-observation.test.mjs
node --test --test-isolation=none runtime/patches/job-observation/tests/runtime.test.mjs
```

A segunda suíte usa `ToolRuntime`, `defineTool` e `LocalJobRegistry` reais e um job
sintético isolado. `DSH_JOBS_TEST_TARGET` permite escolher o runtime;
`DSH_GUARD_TEST_TARGET` permite escolher o arquivo do guard a validar.
