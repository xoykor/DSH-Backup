# Manifesto de corpus para pesquisa ampla

O manifesto é um JSON persistente, atualizado após cada onda. Ele permite retomar a busca sem repetir consultas equivalentes e torna a cobertura auditável.

## Estrutura mínima

```json
{
  "question": "Pergunta que o corpus deve responder",
  "consulted_at": "2026-09-25",
  "scope": {
    "cutoff": "2026-09-25",
    "languages": ["pt", "en"],
    "regions": [],
    "include": [],
    "exclude": []
  },
  "targets": {
    "candidate_urls": 200,
    "unique_domains": 100,
    "verified_pages": 40
  },
  "queries": [
    {
      "id": "q01",
      "wave": 1,
      "query": "termos de busca usados",
      "purpose": "descoberta ampla"
    }
  ],
  "records": [
    {
      "url": "https://example.org/page",
      "canonical_url": "https://example.org/page",
      "domain": "example.org",
      "organization": "Example",
      "title": "Título da página",
      "published_at": null,
      "retrieved_at": "2026-09-25",
      "query_ids": ["q01"],
      "wave": 1,
      "status": "verified",
      "kind": "primary",
      "relevance": "high",
      "evidence": "Trecho curto que sustenta a afirmação.",
      "claims": ["claim-001"],
      "duplicate_of": null,
      "failure": null
    }
  ],
  "claims": [
    {
      "id": "claim-001",
      "text": "Afirmação sintetizada",
      "kind": "fact",
      "record_urls": ["https://example.org/page"]
    }
  ],
  "waves": [
    {
      "wave": 1,
      "queries": ["q01"],
      "new_urls": 120,
      "new_domains": 70,
      "verified_pages": 12,
      "stopped_because": null
    }
  ],
  "limitations": []
}
```

## Regras dos campos

- `status` deve ser `candidate`, `verified`, `failed`, `excluded` ou `duplicate`.
- `kind` deve ser `primary`, `secondary` ou `discovery`.
- `relevance` deve ser `high`, `medium` ou `low`.
- Um registro `verified` precisa ter título, data de acesso e evidência. Um registro `failed` precisa explicar `failure`.
- Uma duplicata deve apontar para `duplicate_of`; não a conte como domínio independente.
- `fact` exige apoio explícito em `record_urls`. `inference` deve descrever a ligação entre as fontes e a dedução.
- `limitations` deve registrar universo indefinido, idiomas ausentes, bloqueios, atraso de indexação, fontes inacessíveis e qualquer viés de seleção.
