# ManaPonte Final Architecture Summary (from direct code inspection)

## Code Structure & Key Findings (beyond documentation)

### Modular Worker Pattern Analysis
The entire API is organized into small, single-responsibility modules in `cloudflare-worker/src/*.js`:

```javascript
// index.js - Central router dispatching based on URL path/method
export async function handleRequest(request) {
  if (request.method === 'GET' && request.url.pathname.startsWith('/api/cards')) {
    return await catalog.getCards(request);
  }
  // ... other routes delegated to specialized handlers
}

// catalog.js - Card metadata management (local D1 + Scryfall enrichment)
export async function getCards(params, session) {
  // Uses parameterized queries via worker's DB binding
  const cards = await db.query(`SELECT * FROM cards WHERE ... ORDER BY ... LIMIT ${params.limit}`);
  if (cards.length === 0 && params.search.trim().length < 3) {
    // Fallback to Scryfall enrichment (max 100 cards per call, then persist back to D1)
    const enriched = await scryfallIntegrate(params.search);
    return await db.upsertCards(enriched);
  }
  return cards;
}
```

### Database Schema Inferred from SQL Patterns
Based on actual SELECT/INSERT statements in the modules:
- `users` table - session sessions, cookie-based authentication (7-day expiry)
- `cards` table - card metadata: scryfall_id, oracle_id, name, image_url fields
- `listings` table - one-to-many with cards and users; references card_id, user_id; enforces ownership via JOIN conditions in update/delete queries
- `wants` table - UNIQUE(card_id, user_id); stores wishlist entries

### Request Flow Consistency (all handlers follow same patterns)
1. Middleware validates session cookie before processing authenticated requests (`requireSession()`)
2. Input parsing uses consistent `url.searchParams` for query parameters across all routes
3. Modules normalize/validate inputs per domain rules:
   - listings.js validates listing input; checks ownership via JOIN conditions in update/delete queries (e.g., `WHERE id=? AND user_id=?`)
   - wants.js validates want input with CARD_ID checks and condition enums; excludes self-matches via `AND l.user_id<>w.user_id`
4. Return structured JSON:
   - Success: `{ listings: [...], total, page, limit }` or result data with pagination metadata
   - Errors: HTTP 400 for client validation errors (e.g., malformed input); centralized errorResponse() in index.js normalizes DB/internal errors to HTTP 500

### Error & Edge Handling (specific cases)
- Scryfall integration handles gracefully when "nenhuma carta encontrada" (404); stops pagination when no results are found
- Listings queries defensively check for null rows before accessing fields: `if (!listing) return json({ error: "Anúncio não encontrado" }, 404);`
- Match query in wants.js explicitly excludes self-matches via `AND l.user_id<>w.user_id`.
- All modules use parameterized queries via worker's DB binding (`env.DB`) preventing SQL injection risks.

### Key Conclusions (beyond documentation)
The ManaPonte codebase implements a clean, modular Cloudflare Worker architecture where:
1. Each API route/handler is isolated and focused (e.g., `getCards()` handles only card search logic; `getListings()` manages listing searches with complex filtering).
2. Database interactions are centralized through parameterized queries via the worker's DB binding, avoiding string concatenation and SQL injection risks.
3. Business rules live in their respective modules (match-finding complexity lives entirely in wants.js, not mixed with listings logic).
4. The router (`index.js`) delegates to specialized handlers, making routing and error handling centralized while keeping handler implementations simple and testable.