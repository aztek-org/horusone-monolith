---
name: Security Review
description: >
  Checklist for reviewing code changes against OWASP best practices,
  data isolation requirements, dependency vulnerabilities, and secure
  coding patterns for the Horus platform.
---

# Security Review Checklist

Use this skill when reviewing code changes for security issues.

## 1. Data Isolation (Critical)

- [ ] All database queries filter by `organization_id`
- [ ] No endpoint returns data from other organizations
- [ ] `get_org_id` dependency is used on all org-scoped routes
- [ ] No raw SQL without parameterized queries
- [ ] API responses do not leak internal IDs or cross-org references

## 2. Authentication

- [ ] All new endpoints require `get_current_user` (except `/health`)
- [ ] WebSocket connections validate JWT on upgrade
- [ ] No hardcoded tokens, API keys, or credentials in source code
- [ ] Token validation checks issuer, audience, and expiration

## 3. Authorization

- [ ] Role checks via `require_role()` on admin/instructor-only routes
- [ ] Students cannot access instructor or admin endpoints
- [ ] Platform-admin routes are distinguished from org-admin routes

## 4. Input Validation

- [ ] All request bodies use Pydantic models with field constraints
- [ ] Query parameters have `ge`, `le`, `max_length` constraints
- [ ] File uploads validate MIME type and size (max 10MB audio)
- [ ] No user input used in SQL, file paths, or shell commands

## 5. Secrets & Configuration

- [ ] No secrets in source code (search for API keys, passwords, tokens)
- [ ] `.env` files are in `.gitignore`
- [ ] Secrets use environment variables, not config files
- [ ] Error messages do not expose internal details or stack traces

## 6. Dependencies

```bash
# Run these scans
cd backend && pip-audit --strict
cd frontend && pnpm audit --audit-level=high
# If Rust services exist:
cd realtime/<service> && cargo audit
# Docker images:
docker scout cves <image>
```

- [ ] No known critical or high vulnerabilities
- [ ] Dependencies are pinned to specific versions
- [ ] No unnecessary dependencies added

## 7. Docker & Infrastructure

- [ ] Containers run as non-root user
- [ ] Images use pinned versions (not `:latest`)
- [ ] Only necessary ports are exposed
- [ ] No `--privileged` or elevated capabilities
- [ ] Health checks are defined

## 8. Headers & CORS

- [ ] CORS whitelist includes only `horusone.app` domains
- [ ] Security headers are set (CSP, HSTS, X-Frame-Options, etc.)
- [ ] No wildcard (`*`) in CORS allowed origins

## 9. Logging

- [ ] Security events are logged (login, failed auth, admin actions)
- [ ] Logs do not contain passwords, tokens, or PII
- [ ] Error handling does not swallow exceptions silently

## 10. WebSocket Security

- [ ] JWT validated on connection upgrade
- [ ] Message size limits enforced
- [ ] Connection rate limiting per IP
- [ ] Idle connection timeout configured
