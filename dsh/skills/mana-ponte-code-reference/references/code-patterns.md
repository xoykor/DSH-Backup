# ManaPonte Module Patterns (from actual source code)

## catalog.js - Card Metadata Management
Key patterns:
- Uses parameterized queries via worker's DB binding (`env.DB`)
- Implements upserts with ON CONFLICT for cards table (CREATE TABLE ... ON CONFLICT DO UPDATE/INSERT)
- Scryfall integration: calls `/api/cards` → if local search insufficient (<3 chars or few results), makes Scryfall API call, persists enriched metadata back to D1
- Graceful fallback handling when Scryfall returns 404 ("nenhuma carta encontrada")

## listings.js - Listing CRUD Operations
Key patterns:
- Complex ownership checks via JOIN conditions in update/delete queries (e.g., `WHERE id=? AND user_id=?`)
- Multi-table JOIN queries across listings, cards, and users for filtering and validation
- Input normalization before database operations
- Defensive row checking: `if (!listing) return json({ error: "Anúncio não encontrado" }, 404);`
- Pagination with configurable page/limit from query params
- CSRF validation on mutations (POST/PUT/DELETE listings actions)

## wants.js - Wishlist Management & Matching Logic
Key patterns:
- UNIQUE constraint on (`card_id`, `user_id`) table to prevent duplicate wishes
- Complex match query explicitly excludes self-matches via `AND l.user_id<>w.user_id`
- Business rule (matching logic) lives entirely in this module, not mixed with listings/catalog logic
- Input validation for want parameters using CARD_ID checks and condition enums
- Uses parameterized queries consistently; no string concatenation

## auth.js - Authentication Flow
Key patterns:
- Session cookie (`mp_session`) with HttpOnly/Secure/SameSite=Lax flags
- PBKDF2-SHA256 hashing with 100k iterations per new hash (token never stored in plain text)
- Rate limiting blocks after 5 failed logins in a 15-minute window
- CSRF protection for all mutations; separate token validation middleware

## lib.js - Shared Utilities
Key patterns:
- Centralized JSON handling functions
- Cookie reading/writing with proper cookie attributes (HttpOnly, Secure)
- Session middleware that reads and validates the `mp_session` cookie
- Error response normalization helper function
- CSRF validation utility shared across modules
- Input sanitization helpers for consistent parameter handling