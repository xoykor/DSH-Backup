# Plano de jornada

```json
{
  "timeout_seconds": 90,
  "step_timeout_seconds": 8,
  "allow_interactions": true,
  "steps": [
    {"action": "goto", "url": "http://app-de-teste:8000/"},
    {"action": "fill", "selector": "#nome", "value": "Pessoa de teste"},
    {"action": "click", "selector": "button[type=submit]"},
    {"action": "assert-text", "selector": "#resultado", "contains": "Salvo"},
    {"action": "assert-visible", "selector": "#resultado", "visible": true}
  ]
}
```

O endereço da aplicação deve ser acessível de dentro do container da ponte. `127.0.0.1` em uma página representa o container, não necessariamente o host. `--endpoint` muda o endereço da ponte, não da aplicação. O padrão é `http://127.0.0.1:8731`.

São aceitas 1–40 etapas, com pelo menos uma asserção. `goto` aceita HTTP, HTTPS ou `data:text/html` para fixtures autocontidas. `fill` e `click` exigem `allow_interactions: true`. Seletores são CSS; uma asserção de elemento exige correspondência única, exceto `assert-visible` com `visible: false`, que também aceita ausência. `assert-text` e `assert-value` usam exatamente um de `equals`/`contains`; `assert-title` e `assert-url` também usam esses campos, sem seletor. Não existe execução de JavaScript arbitrário no plano.

As asserções aguardam por uma condição até o timeout da etapa, consultando apenas o estado. Uma condição não atendida sai com código 1; infraestrutura ou plano inválido, 2; todas as asserções atendidas, 0. Timeout global: 1–600 segundos, padrão 120; timeout por etapa: 0,2–60 segundos, padrão 10. Limites incluem a limpeza e a captura de falha; se não houver tempo, essas operações ficam pendentes no relatório.

A pasta de saída precisa ser nova. `report.json` contém etapas, duração, código e caminhos de evidência. Valores preenchidos, textos de página e URLs completas não são copiados para o relatório. Screenshots podem conter conteúdo da aplicação; mantenha-os na pasta autorizada. Não execute duas jornadas em paralelo na mesma ponte.
