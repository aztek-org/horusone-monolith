---
name: OWASP Security
description: >
  Use for deep security reviews, secure endpoint design, and AI-agent security checks.
  Covers OWASP Top 10:2025, ASVS 5.0, and agentic-AI threat patterns.
---

# OWASP Security Skill

This skill is installed from and adapted for Horus from:
`https://github.com/agamm/claude-code-owasp` (commit `460fdf4917a3d7b7a62bed020bb37faf990c25b8`).

Apply this when writing or reviewing backend/frontend/infrastructure code with security impact.

## OWASP Top 10:2025 Quick Map

| ID | Risk | Primary Control |
|---|---|---|
| A01 | Broken Access Control | Server-side authorization checks and deny-by-default policies |
| A02 | Security Misconfiguration | Harden defaults, disable unused features, restrict exposure |
| A03 | Supply Chain Failures | Pin dependencies, audit frequently, verify integrity |
| A04 | Cryptographic Failures | TLS 1.2+, modern ciphers, strong key/secret handling |
| A05 | Injection | Parameterized queries, no string-built commands/queries |
| A06 | Insecure Design | Threat model early, enforce security controls in architecture |
| A07 | Auth Failures | Strong session/token handling, MFA for sensitive actions |
| A08 | Integrity Failures | Verify signatures/artifacts, protect CI/CD and build chain |
| A09 | Logging Failures | Security events logged, monitored, and actionable |
| A10 | Exception Handling | Fail closed, hide internals, retain forensic context in logs |

## Secure Review Checklist

### 1) Input and Data Flow
- [ ] All externally controlled input is validated server-side
- [ ] Length/range/format constraints are explicit
- [ ] Allowlist validation is used where possible
- [ ] User input is never directly used in SQL, shell, file paths, or dynamic code

### 2) Authentication and Session Security
- [ ] Auth is required for non-public endpoints
- [ ] JWT/session validation covers expiry/issuer/audience/signature
- [ ] Logout/session revocation paths are enforced
- [ ] Sensitive flows require stronger auth where applicable (step-up / MFA)

### 3) Authorization and Tenancy
- [ ] Every read/write operation enforces role and ownership checks
- [ ] Organization boundaries are enforced on all org-scoped data
- [ ] Access checks happen server-side (not UI-only)
- [ ] Unauthorized accesses do not leak object existence details

### 4) Secrets and Crypto
- [ ] No secrets committed in code or repository docs
- [ ] Environment variables or secret stores are used
- [ ] Passwords use Argon2/bcrypt (never MD5/SHA1/plain)
- [ ] Transport security is enforced for all external communication

### 5) Error Handling and Logging
- [ ] No stack traces or internals exposed to clients
- [ ] Errors fail closed when authorization/validation checks fail
- [ ] Security-significant actions are logged with traceable metadata
- [ ] Logs avoid token/credential/PII leaks

### 6) Dependencies and Build Chain
- [ ] Dependencies are pinned and reviewed
- [ ] Vulnerability scans are run on backend/frontend/runtime stacks
- [ ] Third-party packages/plugins are trusted and reviewed
- [ ] Build/deploy pipeline integrity is protected

## Agentic AI Security (OWASP Agentic Risks)

For LLM/agent flows (STT → orchestration → TTS/tools), verify:

- [ ] Prompt/input sanitization for untrusted content
- [ ] Tool permissions are least-privilege and scoped
- [ ] No unrestricted code execution from model output
- [ ] Agent memory/context storage is integrity-protected
- [ ] Inter-agent/tool messages are authenticated and validated
- [ ] Circuit breakers and kill-switch controls exist
- [ ] Human approval gates exist for sensitive operations

## ASVS 5.0-Oriented Baseline

### L1 (all apps)
- Strong password and session/token requirements
- Rate limiting for authentication-sensitive endpoints
- HTTPS/TLS everywhere

### L2 (sensitive data/workloads)
- MFA or stronger verification for sensitive operations
- Robust security logging and auditability
- Comprehensive input validation and output handling

### L3 (critical workloads)
- Strong key management controls (HSM/KMS where applicable)
- Threat modeling and attack-path documentation
- Monitoring, anomaly detection, and response playbooks

## Secure Coding Examples

### SQL injection prevention
```python
# Unsafe
session.execute(f"SELECT * FROM users WHERE id = {user_id}")

# Safe
session.execute(text("SELECT * FROM users WHERE id = :id"), {"id": user_id})
```

### Command injection prevention
```python
# Unsafe
os.system(f"convert {filename} out.png")

# Safe
subprocess.run(["convert", filename, "out.png"], shell=False, check=True)
```

### Fail-closed authorization
```python
def can_access_resource(user, resource) -> bool:
    try:
        return authz_service.check(user, resource)
    except Exception:
        logger.exception("Authorization check failed")
        return False
```

## Horus-Specific Security Focus

When applying this skill in Horus, prioritize:

1. **Org isolation first**: no cross-org visibility in sessions, analytics, modules, badges, users, or seats.
2. **Role boundary enforcement**: platform-admin vs org-admin vs instructor vs student.
3. **Audio/session safety**: payload limits, replay access checks, transcript confidentiality.
4. **Prompt/tool hardening**: prevent agent/tool misuse in orchestration paths.
5. **Operational security**: dependency scanning, pinned runtime/tooling, secure defaults in Docker/Traefik.

## Recommended Security Validation Commands (Horus)

```bash
# Backend
cd backend
uv run ruff check app/
uv run pytest tests/ -v

# Frontend
cd frontend
pnpm test
pnpm build
pnpm audit --audit-level=high
```
