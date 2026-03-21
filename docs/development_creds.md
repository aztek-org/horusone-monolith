# Horus MVP — Development Credentials

> **⚠️ These credentials are for LOCAL DEVELOPMENT ONLY.**
> Never use these in production. All passwords below are pre-configured in
> Docker Compose and the Keycloak realm import.

---

## Quick Reference

| Service            | URL                             | Username / Email                 | Password     |
|--------------------|---------------------------------|----------------------------------|--------------|
| **Keycloak Admin** | http://localhost:8080            | `admin`                          | `admin`      |
| **Horus App**      | http://localhost:3000            | _(use any user below)_           |              |
| **Horus API**      | http://localhost:8000/docs       | _(Bearer token from Keycloak)_   |              |
| **PostgreSQL**     | `localhost:5432`                 | `horus` / `horus`                | `horus`      |
| **Keycloak DB**    | `localhost:5432`                 | `keycloak` / `keycloak_db`       | `keycloak`   |
| **Redis**          | `localhost:6379`                 | _(no auth)_                      |              |
| **Traefik**        | http://localhost:8080            | _(no auth — dashboard)_          |              |

---

## Application Users (Keycloak + Database)

All users below are pre-configured in the Keycloak realm import
(`backend/docker/keycloak-import/horus-realm.json`) and created in
PostgreSQL by the seed script (`backend/scripts/seed.py`).

### Platform Super Admin

| Field          | Value                          |
|----------------|--------------------------------|
| **Email**      | `admin@horusone.app`              |
| **Password**   | `@dmin2026`                     |
| **Role**       | `platform-admin` + `org-admin` |
| **Org**        | _(none — platform-level)_      |
| **Access**     | Full platform, all orgs        |

### Organization Admin (SkyBridge Flight Academy)

| Field          | Value                                |
|----------------|--------------------------------------|
| **Email**      | `sarah.mitchell@skybridge.aero`      |
| **Password**   | `stud3nt2026`                           |
| **Role**       | `org-admin` (Keycloak) / `admin` (Seat) |
| **Org**        | SkyBridge Flight Academy             |
| **Access**     | Manage org users, scenarios, settings|

### Instructor

| Field          | Value                                |
|----------------|--------------------------------------|
| **Email**      | `james.chen@skybridge.aero`          |
| **Password**   | `stud3nt2026`                           |
| **Role**       | `instructor`                         |
| **Org**        | SkyBridge Flight Academy             |
| **Access**     | Create scenarios, review sessions    |

### Students

| Field          | Value                                |
|----------------|--------------------------------------|
| **Email**      | `maria.santos@skybridge.aero`        |
| **Password**   | `stud3nt2026`                           |
| **Role**       | `student`                            |
| **Org**        | SkyBridge Flight Academy             |

| Field          | Value                                |
|----------------|--------------------------------------|
| **Email**      | `alex.turner@skybridge.aero`         |
| **Password**   | `stud3nt2026`                           |
| **Role**       | `student`                            |
| **Org**        | SkyBridge Flight Academy             |

---

## Role Hierarchy

```
platform-admin          ← Full platform access (all orgs, all settings)
  └── org-admin         ← Manage one organization (users, scenarios, billing)
        └── instructor  ← Create scenarios, review student sessions
              └── student  ← Participate in ATC training (DEFAULT role)
```

### Where Roles Live

| Layer      | Storage                          | Values                                      |
|------------|----------------------------------|----------------------------------------------|
| **Keycloak** | Realm roles → JWT `realm_access.roles` | `platform-admin`, `org-admin`, `instructor`, `student` |
| **Database** | `seats.role` column              | `admin`, `instructor`, `student`             |

- **Keycloak roles** control API access (JWT middleware checks)
- **Seat roles** control organization-level permissions (who can do what within an org)
- A user can have different seat roles in different organizations

---

## Infrastructure Credentials

### PostgreSQL

```
Host:     localhost (or postgres inside Docker network)
Port:     5432
```

| Database       | Username    | Password    | Purpose              |
|----------------|-------------|-------------|----------------------|
| `horus_db`     | `horus`     | `horus`     | Application data     |
| `keycloak_db`  | `keycloak`  | `keycloak`  | Keycloak identity    |

**Connection strings:**
```bash
# Application (async)
DATABASE_URL=postgresql+asyncpg://horus:horus@localhost:5432/horus_db

# psql direct access
psql -h localhost -U horus -d horus_db
# password: horus
```

### Keycloak Admin Console

```
URL:      http://localhost:8080  (or http://auth.localhost via Traefik)
Username: admin
Password: admin
Realm:    horus
```

After logging in:
1. Switch to the **horus** realm (top-left dropdown)
2. Users → see all pre-configured users
3. Realm Roles → see `platform-admin`, `org-admin`, `instructor`, `student`
4. Clients → `horus-web` (SPA) and `horus-api` (bearer-only)

### Redis

```
Host:     localhost (or redis inside Docker network)
Port:     6379
Database: 0
No auth required (dev mode)
```

```bash
# Connect
redis-cli -h localhost -p 6379

# Check session keys
KEYS session:*
KEYS prefs:*
```

---

## Keycloak OIDC Settings (for frontend/backend config)

| Setting                | Value                                                    |
|------------------------|----------------------------------------------------------|
| **Issuer URL**         | `http://localhost:8080/realms/horus`                     |
| **Auth endpoint**      | `http://localhost:8080/realms/horus/protocol/openid-connect/auth` |
| **Token endpoint**     | `http://localhost:8080/realms/horus/protocol/openid-connect/token` |
| **JWKS URI**           | `http://localhost:8080/realms/horus/protocol/openid-connect/certs` |
| **Client ID (SPA)**    | `horus-web`                                              |
| **Client ID (API)**    | `horus-api`                                              |
| **PKCE method**        | `S256`                                                   |
| **Token lifespan**     | 300s (5 min)                                             |
| **SSO idle timeout**   | 1800s (30 min)                                           |

---

## Seed Data Summary

The seed script (`uv run python -m scripts.seed`) creates:

| Entity             | Count | Details                                        |
|--------------------|-------|------------------------------------------------|
| **Organizations**  | 1     | SkyBridge Flight Academy (slug: `skybridge`)   |
| **Users**          | 5     | 1 platform-admin + 1 org-admin + 1 instructor + 2 students |
| **Seats**          | 4     | All org users get a seat (platform-admin has none) |
| **Scenarios**      | 6     | KJFK, KLAX, EGLL, KATL, OMDB, LFPG            |
| **Sessions**       | 3     | 2 completed + 1 active                         |
| **Voice Logs**     | 12    | Realistic ATC ↔ Pilot exchanges                |

### Running the seed

```bash
cd backend

# First run migrations
uv run alembic upgrade head

# Seed (idempotent — safe to run multiple times)
uv run python -m scripts.seed

# Reset and re-seed (destructive)
uv run python -m scripts.seed --reset
```

---

## Token Claims (JWT Access Token)

When a user logs in, the JWT access token contains:

```json
{
  "sub": "keycloak-user-uuid",
  "email": "user@example.com",
  "preferred_username": "user@example.com",
  "realm_access": {
    "roles": ["student", "default-roles-horus"]
  },
  "organization_id": "skybridge",
  "exp": 1710000000
}
```

The backend `get_current_user` middleware extracts:
- `sub` → `keycloak_id` (used to look up the DB user)
- `realm_access.roles` → authorization checks
- `organization_id` → org context (custom claim)

---

## Troubleshooting

### "Cannot log in with seed users"

The Keycloak realm import creates users on **first startup only**. If you
already had a Keycloak volume from before adding users:

```bash
# Remove Keycloak data and re-import
docker compose down -v
docker compose up -d
```

### "Seed fails with keycloak_id conflict"

If you previously seeded with `dev-{uuid}` format IDs and the realm now
has real Keycloak IDs:

```bash
cd backend
uv run python -m scripts.seed --reset
```

### "User logged in but API returns 401"

The seed `keycloak_id` values (`kc-{uuid}`) are **placeholders**. On first
real login, the backend receives the actual Keycloak `sub` claim. To sync:

1. Log in via the frontend (http://localhost:3000)
2. The `keycloak_id` in the `users` table will need to match the Keycloak
   `sub` value. For dev with `auth_enabled=False`, this is bypassed.

### "Keycloak admin console shows no users in horus realm"

Make sure you're viewing the **horus** realm, not the **master** realm.
Switch realms using the dropdown in the top-left of the Keycloak admin UI.
