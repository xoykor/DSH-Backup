---
name: organizacao-arquivos
description: Planejar e aplicar cópias ou renomeações em lote por mapeamentos explícitos, detectando colisões e duplicatas, verificando hashes e registrando recuperação parcial.
---

# Organização de arquivos

Use Python 3 e `scripts/file_manifest.py`. O helper trabalha em um `root` existente, com arquivos regulares e diretórios de destino já existentes. Converta regras solicitadas de nomes/pastas em mapeamentos explícitos; não invente exclusões. Operações suportadas: `copy` e `rename`.

```json
{"root":"/caminho/absoluto/lote","operations":[{"op":"copy","source":"foto.jpg","destination":"copia/foto.jpg"},{"op":"rename","source":"recibo.pdf","destination":"2026-recibo.pdf"}]}
```

Gere o plano, que não altera os arquivos do lote:

```bash
python3 scripts/file_manifest.py plan --spec pedido.json --output plano.json
```

Revise origens/destinos e `duplicates_by_content` no plano conforme o pedido. A autorização já dada pelo usuário pode abranger a aplicação; o helper não exige uma segunda confirmação. Aplique o plano autorizado usando um diário novo:

```bash
python3 scripts/file_manifest.py apply --spec plano.json --output execucao.jsonl
```

O plano fixa SHA-256, tamanho, inode e data de modificação. Antes de aplicar, todas as entradas são revalidadas. Destino existente, caminho fora de root, symlink em qualquer componente, hardlinks na origem, colisões e ciclos são recusados. Pastas não são criadas implicitamente. `rename` requer Linux/glibc com `renameat2` para recusar sobrescrita atomicamente; cópias criam arquivos 0600 e preservam conteúdo, não permissões/metadados.

O diário registra cada início antes da operação e cada hash conferido depois. Em falha parcial, pare e leia o diário; uma entrada `started` sem `completed` exige inspecionar ambos os caminhos. Para renomeação concluída, a recuperação proposta move o destino de volta somente após conferir hash e ausência da origem. Cópias parciais ficam disponíveis para inspeção; nenhum rollback ou exclusão é executado automaticamente. Não reaplique o plano inteiro após sucesso parcial: gere plano para os itens restantes.

Limites: até 1.000 operações, especificação até 4 MiB, `--timeout` de 1 a 3.600 segundos (120 padrão) incluindo hashes. Tempo expira entre blocos de leitura; I/O travado pelo sistema pode excedê-lo. Execute em lote sem escritores concorrentes: alterações são detectadas, mas o helper não bloqueia processos externos. Código 0: planejado/concluído; 2: erro ou execução parcial. Confira `completed`, `verified` e o caminho do diário antes de relatar sucesso.
