---
name: "mana-ponte-web-source"
description: "Fetch and analyze real source code from mana-ponte GitHub repository using web access"
author: "dsh-skill-curator"
version: "0.1.0"
---
# ManaPonte Web Source Analysis Skill v2

This skill fetches actual JavaScript/TypeScript source files directly from the mana-ponte GitHub repository via raw.githubusercontent.com URLs, then analyzes them to provide concrete architectural insights beyond documentation.

The approach:
1. Use web_fetch with known GitHub raw file paths to retrieve module implementations (catalog.js, listings.js, wants.js, auth.js, lib.js) and router files (index.js).
2. Parse the returned content to identify concrete implementation patterns:
   - Specific query structures and parameterization patterns using SQL queries or database access functions in the code.
   - Validation logic boundaries in each module (length limits, format checks, type validation shown in actual code blocks).
   - Error handling paths with actual error messages, conditions, or try/catch blocks from real file content.
   - Business rule enforcement locations: e.g., when Scryfall is called based on real conditional statements; ownership checks via JOIN conditions seen in actual SQL queries; self-match exclusion shown as `AND l.user_id <> w.user_id` condition in wants.js; UNIQUE constraint enforcement at DB level mentioned or implied by code patterns.
   - Database interaction patterns through parameterized query examples using placeholders (e.g., ?) or prepared statement usage visible in the fetched code.
   - Middleware and routing flow from index.js router based on actual route dispatching logic shown in the file content.
   - Authentication details including concrete PBKDF2 iteration count, cookie attributes names/attributes, rate limiting window values (e.g., 5 failed attempts within 15 minutes) as seen in auth.js code.
   - Scryfall integration specifics: which fields are fetched, parameter matching logic shown through actual API call patterns or query construction in catalog.js.
   - Match-finding SQL JOIN pattern in wants.js based on concrete JOIN conditions and WHERE clauses from real file content.
3. Produce detailed conclusions about how the code is actually structured and implemented, with direct examples extracted from fetched source files.