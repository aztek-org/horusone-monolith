---
description: Run backend API tests and analyze results
agent: api-expert
---

Run the API tests and show results:
!`cd backend && uv run pytest tests/ -v --tb=short 2>&1 | head -100`

Analyze any failures and suggest fixes. Check for:

**Test Failures:**
- Endpoint logic errors
- Request/response validation issues
- Status code mismatches
- Authentication/authorization problems

**Async Issues:**
- Improper async/await usage
- Blocking operations in async code
- Race conditions

**Integration Problems:**
- Database connection issues
- External service failures
- LangChain integration errors

**Data Validation:**
- Pydantic model validation failures
- Missing required fields
- Type mismatches

If tests are passing, provide a summary and check for:
- Test coverage gaps
- Edge cases not covered
- Integration test needs

If backend is not set up yet:
!`ls -la backend/`

Acknowledge that and wait for backend structure to be created.
