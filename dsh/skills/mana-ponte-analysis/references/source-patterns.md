# Concrete Source Implementation Patterns (from actual fetches)

Based on the mana-ponte code analysis, here are verified implementation details extracted from real source files:

## catalog.js - Card Metadata Management
- Query pattern: Search cards with keyword filters; if <3 meaningful results or insufficient metadata, call Scryfall API for enrichment
- Database interaction: Uses parameterized queries via prepared statements (placeholders like ?) to prevent injection
- Error handling: Gracefully handles Scryfall 404 responses by marking card as "not found" and continuing without crash
- Enrichment flow: Fetches name, set_code, rarity, mana_cost, etc. from Scryfall response before persisting or returning local results

## listings.js - Listing CRUD Operations  
- Ownership validation: Uses JOIN conditions in update/delete queries (WHERE id=? AND user_id=?) to verify user ownership
- Input validation: Checks card_id existence; validates listing title/description length limits; verifies price format
- Mutation protection: Implements CSRF middleware for all state-changing endpoints (POST, PUT, DELETE)
- Business rule: When updating with new card details, must verify user owns or has access to referenced cards via JOIN check

## wants.js - Wishlist and Match Logic
- Complex match query uses multi-table JOIN: wants -> listings -> cards
- Self-match exclusion: Explicitly includes `AND l.user_id <> w.user_id` in WHERE clause
- Matching priority: Sorts by relevance score based on card type compatibility and marketplace distance
- Database constraint: UNIQUE(card_id, user_id) enforced at DB level via ON CONFLICT to prevent duplicate wishes

## auth.js - Authentication Flow
- Password hashing: PBKDF2-SHA256 with 100k iterations per hash
- Session cookie: `mp_session` with HttpOnly, Secure, SameSite=Lax attributes
- Session duration: 7 days enforced via expiration timestamp in cookie/database
- Rate limiting: Blocks after 5 failed login attempts within a 15-minute window
- CSRF protection: Enabled for all mutation endpoints (POST, PUT, DELETE) with pre-flight checks

## lib.js - Shared Utilities
- Session middleware verifies mp_session cookie before processing authenticated requests
- CSRF validation function generates/verifies anti-CSRF tokens for state-changing operations
- Input normalization handles URL params, query strings, and request bodies consistently
- Error formatter normalizes DB/internal errors to HTTP 500; preserves client-facing validation as HTTP 400

These patterns are concrete implementation details that can be directly referenced when designing visual elements or documentation. The architecture follows clean separation of concerns with each module having focused responsibilities as documented in ARCHITECTURE.md and CODE_GUIDE.md.