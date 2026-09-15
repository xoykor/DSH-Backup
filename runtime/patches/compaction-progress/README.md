# Progresso de compactação

Patch do chat DSH 0.1.5-rc.2. Exibe duas barras acessíveis assim que recebe
`compaction/start`: leitura e resumo; compactação e gravação. A primeira
termina em `compaction/summary`; a segunda permanece ativa até o checkpoint
e `compaction/end` bem-sucedido. Erros encerram a animação e exibem a mensagem.
O resumo final continua expansível. Funciona com compactação automática e manual.

As barras ativas são indeterminadas: o protocolo DSH não transmite o percentual
de prefill registrado pelo LM Studio. Não há percentual estimado nem leitura de
logs globais que possa atribuir progresso de outra sessão. A leitura normal fora
da compactação não é alterada. Qwen e Ornith usam os mesmos eventos de ciclo.

Aplicação: `node apply-compaction-progress.mjs --target PACKAGE_DIRECTORY`.
Verificação somente leitura: acrescente `--check`. O instalador valida hashes,
preserva backup e recusa versões desconhecidas. Integrado a `restore-dsh.sh`.
O servidor guarda o módulo cliente em memória. Reinicie o DSH quando o trabalho
atual terminar e recarregue a página para carregar a interface atualizada.

Testes: `node --test tests/progress.test.mjs`.
