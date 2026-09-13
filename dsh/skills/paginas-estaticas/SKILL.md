---
name: paginas-estaticas
description: Criar ou ajustar uma página HTML/CSS local baseada em template e verificar links, assets e responsividade básica. Use para sites estáticos pequenos; publicação não faz parte da skill.
---

# Páginas estáticas

Inspecione o template e os assets existentes antes de editar. Mantenha a página autocontida e use caminhos relativos. Para mudanças de conteúdo ou estilo, preserve a estrutura pedida e confirme que arquivos referenciados existem.

Rode `scripts/check_site.py --root DIRETORIO --entry index.html`. O relatório verifica referências locais em `href`, `src` e `url(...)`, detecta caminhos que escapam da raiz e avisa quando falta uma meta viewport. Um relatório verde comprova integridade estrutural, não aparência.

Quando houver um navegador real registrado no DSH, sirva a pasta com o mecanismo de execução local disponível e inspecione a página em larguras desktop e móvel. Reutilize a skill `auditoria-visual` existente se a rota de captura/envio estiver funcional. Descubra as ferramentas antes de usá-las; se não houver navegador, documente a limitação e não invente uma inspeção visual. Não publique nem conecte serviços externos.

Use [fixtures/site/index.html](fixtures/site/index.html) para um teste mínimo.
