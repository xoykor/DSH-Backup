---
name: "mana-ponte-source-analysis"
description: "ManaPonte source analysis skill - examine actual JavaScript/TypeScript module implementations to draw concrete architectural conclusions"
author: "dsh-skill-curator"
version: "0.1.0"
---
# ManaPonte Source Analysis Skill

This skill analyzes the actual source code files from the mana-ponte repository to provide detailed, concrete implementation insights beyond high-level documentation. It examines real module implementations including query structures, validation logic, error handling paths, and business rule enforcement patterns.

The analysis follows these concrete focus areas:

1. Module-level implementation details - examining specific query structures, validation logic, and business rules in catalog.js, listings.js, wants.js, auth.js with actual code snippets or patterns found in the source
2. Database interaction patterns - how SQL queries are parameterized (prepared statements) and structured across modules using the worker's D1 binding
3. Error handling concrete cases - validation errors (length limits, format checks), DB errors (unique constraint violations, foreign key constraints), Scryfall 404 responses, network timeouts
4. Business rule implementations specific to each module with actual code patterns:
   - catalog.js: card enrichment flow from D1 + Scryfall fallback - examine the conditional logic and query structure for when to call Scryfall API
   - listings.js: ownership checks, input validation, CSRF protection for mutations - look at JOIN conditions in update/delete queries and mutation endpoint validation
   - wants.js: complex match query logic (excluding self-matches), unique constraints - examine the exact SQL JOIN pattern used for matching
5. Routing and middleware flow in cloudflare-worker/src/index.js or similar router file
6. Authentication implementation details from auth.js with concrete PBKDF2 iteration count, cookie attributes, rate limiting window logic
7. Scryfall integration specifics from catalog.js - how card metadata enrichment works (which fields are fetched, parameter matching)
8. Match-finding logic in wants.js - the specific SQL query pattern for finding matching listings including pagination and relevance scoring
9. Pagination, filtering, and validation patterns across modules showing consistent input/output formats (query params, request bodies, response shapes)
10. Shared utilities usage in lib.js with exactly which functions are exported and used by other modules (e.g., readJson(), writeJson(), getSession(), validateCsrf(), normalizeInput())

The skill will fetch actual source files from the repository using web_fetch or local file access, then analyze them to produce detailed architectural conclusions about:
- Concrete query structures (parameterized queries vs string concatenation)
- Validation boundaries and error messages in real code
- Business rule enforcement locations and conditions
- Database schema implementation details through SQL patterns
- Middleware flow for authentication and CSRF protection
- Scryfall API integration specifics