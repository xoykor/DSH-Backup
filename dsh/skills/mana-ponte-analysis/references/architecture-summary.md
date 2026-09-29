# ManaPonte Architecture Summary (from code analysis)

## Code Structure Overview
The project follows a modular Cloudflare Worker architecture with distinct components:

```
mana-ponte/
├── public/                 # Frontend (HTML/CSS/JS) - no framework
│   └── *.html / *.css / *.js
├── cloudflare-worker/       # API layer
│   ├── src/                # Worker source files
│   │   └── index.js        # Routing, healthcheck, Static Assets handling
│   ├── lib.js              # Shared utilities (JSON, cookies, crypto, session, CSRF)
│   ├── auth.js             # Authentication (signup, login, logout, rate limiting)
│   ├── catalog.js          # D1 database + Scryfall integration for cards metadata
│   ├── listings.js         # Anouncements search, pagination, CRUD of listings
│   ├── wants.js            # Desires, matching logic, public profiles
│   └── migrations/          # Cloudflare D1 schema migrations (D1 versioned)
├── cloudflare-worker/wrangler.jsonc      # Worker config: binding to D1, Static Assets setup
└── ...                       # Other configuration files
```

## Key Architectural Principles from Code Analysis

| Principle | Implementation Detail | Why It Matters |
|---|---|---|
| Single Origin | Frontend and API share same origin via Cloudflare Worker binding | Simplifies frontend/backend communication; no CORS issues for static assets vs API |
| Persistent Storage | All data lives in Cloudflare D1 database, not client or browser | Enables stateful matching (wants.js excludes self-matches), session management, and complex queries across listings/cards/users |
| Metadata Source | Primary card metadata from D1; fallback to Scryfall for MVP discovery | Keeps local D1 as authoritative source while gracefully handling limited Scryfall calls (max 100 cards per call) |
| Image Handling | No image storage; only stores external URL in `cards.image_url` | Reduces server load and cost; players provide their own card images via URLs |
| Authentication Flow | PBKDF2-SHA256 with 100k iterations, session cookie (`mp_session`), 7-day sessions, CSRF protection for mutations | Secure session management without storing raw tokens; rate limiting prevents brute force |
| Routing Pattern | Cloudflare Worker router separates `/api/*` API paths from static assets via `index.js` | Clean separation of concerns; static assets served directly without API overhead |
| Modular Design | Small single-responsibility modules with focused exports (catalog.js, listings.js, wants.js, auth.js) | Each module only imports what it needs from lib.js; business rules contained in their respective handlers |
| Database Interaction | Parameterized queries via worker's DB binding (`env.DB`); no string concatenation | Prevents SQL injection; consistent pattern across all modules |
| Business Rule Location | Complex logic (match-finding, ownership checks) lives entirely within listings/wants modules | Keeps handler implementations simple and testable; complex rules isolated where they belong |
| Error Handling Consistency | Central `errorResponse()` in index.js normalizes DB/internal errors to HTTP 500; module-level client-facing validation returns HTTP 400 | Uniform error responses across API routes; clear distinction between server vs client errors |

## Database Schema (inferred from SQL patterns)
```sql
-- Users table
CREATE TABLE users (...); -- session sessions, 7-day expiry cookies

-- Cards table  
CREATE TABLE cards (...); -- scryfall_id, oracle_id, name, image_url, etc.

-- Listings table (one-to-many with cards and users)
CREATE TABLE listings (...); -- references card_id, user_id; enforces ownership via JOIN conditions in update/delete queries

-- Wants table (unique(card_id, user_id))
CREATE TABLE wants (...);    -- references card_id, user_id; UNIQUE constraint prevents duplicate wishes
```

## Request Flow Pattern (consistency across modules)
1. Middleware (`requireSession()`) validates session cookie before processing authenticated requests
2. Input parsing uses `url.searchParams` consistently for query parameters (page, limit, filter values)
3. Modules normalize/validate inputs per their domain rules:
   - listings.js validates listing input; checks ownership via JOIN conditions in update/delete queries
   - wants.js validates want input with CARD_ID checks and condition enums; excludes self-matches (`AND l.user_id<>w.user_id`)
4. All handlers return structured JSON responses:
   - Success: `{ listings: [...], total, page, limit }` or result data with pagination metadata
   - Errors: HTTP 4xx for client validation errors; HTTP 5xx for server/DB errors via centralized errorResponse() in index.js

## Conclusion Beyond Documentation
The codebase implements a clean, modular Cloudflare Worker architecture where:
- Each API route/handler is isolated and focused (e.g., `getCards()` handles only card search logic; `getListings()` manages listing searches with complex filtering)
- Database interactions are centralized through parameterized queries via the worker's DB binding, avoiding string concatenation and SQL injection risks
- Business rules live in their respective modules (e.g., match-finding complexity lives entirely in wants.js, not mixed with listings logic)
- The router (`index.js`) delegates to specialized handlers, making routing and error handling centralized while keeping handler implementations simple and testable