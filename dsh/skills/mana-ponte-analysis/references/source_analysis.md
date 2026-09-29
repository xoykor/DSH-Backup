# Source Code Analysis Reference (for mana-ponte)

This reference document will record findings from examining actual implementation files, moving beyond high-level documentation to concrete code patterns and choices.

## File Structure Overview (from real repo exploration)
- cloudflare-worker/src/index.js – Worker router that dispatches requests
- cloudflare-worker/src/catalog.js – Card metadata management (local D1 + Scryfall enrichment)
- cloudflare-worker/src/listings.js – Listing CRUD operations with complex business rules
- cloudflare-worker/src/wants.js – Wishlist management and matching engine
- cloudflare-worker/src/auth.js – Authentication flow implementation
- cloudflare-worker/src/lib.js – Shared utilities (JSON, cookies, crypto, session, CSRF)

## Analysis Methodology
For each module file, I will:
1. Read the actual source code
2. Identify concrete implementation patterns (query structures, error handling, business rules, validation)
3. Note specific choices made in the code that implement documented principles or reveal additional design decisions
4. Record findings about how modules interact and share state