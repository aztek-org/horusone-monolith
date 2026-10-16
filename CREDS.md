# Horus MVP Credentials, Scopes, and Platform Map

> **WARNING**
>
> This file documents **development/demo credentials and scope mappings** currently present in the repository.
> Do not use these credentials in production.

### Keycloak realm users

| Username / Email | Password | Realm roles | `organization_id` attribute |
|---|---|---|---|
| `admin@horusone.app` | `@dmin2026` | `platform-admin`, `org-admin` | _(empty)_ |
| `sarah.mitchell@skybridge.aero` | `stud3nt2026` | `org-admin` | `skybridge` |
| `james.chen@skybridge.aero` | `stud3nt2026` | `instructor` | `skybridge` |
| `maria.santos@skybridge.aero` | `stud3nt2026` | `student` | `skybridge` |
| `alex.turner@skybridge.aero` | `stud3nt2026` | `student` | `skybridge` |

## 1) Platform endpoints (current local setup)

| Surface | URL / Host | Notes |
|---|---|---|
| Squawk app | `http://localhost:3000` | Nuxt app (`frontend/apps/squawk`) |
| Tower app | `http://localhost:3001` | Nuxt app (`frontend/apps/tower`) |
| Hangar app | `http://localhost:3002` | Nuxt app (`frontend/apps/hangar`) |
| Backend API | `http://localhost:8000` | FastAPI |
| API docs | `http://localhost:8000/docs` | Swagger |
| Keycloak admin (dev) | `http://localhost:8180` | via `docker-compose.dev.yml` override |
| Traefik dashboard (dev) | `http://localhost:8081` | from `docker-compose.yml` |
| PostgreSQL | `localhost:5432` | `horus_db` + `keycloak_db` |
| Redis | `localhost:6379` | no auth in dev compose |
| Ollama | `http://localhost:11434` | local model endpoint |

## 2) Application login credentials (Keycloak realm `horus`)

Source of truth:
- `backend/docker/keycloak-import/horus-realm.json` (users, passwords, realm roles)
- `backend/scripts/seed.py` (DB user + seat records and role mapping)

### DB/seat role mapping from seed script

`backend/scripts/seed.py` seeds:
- one organization: slug `skybridge`
- platform admin user without organization seat
- seats for org users with `role` in: `admin`, `instructor`, `student`

| User email | Seat role (DB) | Org slug |
|---|---|---|
| `sarah.mitchell@skybridge.aero` | `admin` | `skybridge` |
| `james.chen@skybridge.aero` | `instructor` | `skybridge` |
| `maria.santos@skybridge.aero` | `student` | `skybridge` |
| `alex.turner@skybridge.aero` | `student` | `skybridge` |

> Note: seed sets placeholder `keycloak_id` as `kc-{uuid}`; real Keycloak `sub` is obtained on real login.

## 3) Infra credentials (dev/defaults)

### PostgreSQL

From `backend/docker-compose.yml` and `backend/docker/init-multiple-dbs.sh`:

| Database | Username | Password | How created |
|---|---|---|---|
| `horus_db` | `horus` | `horus` | compose env defaults |
| `keycloak_db` | `keycloak` | `keycloak` | init script creates user+db |

### Keycloak admin

From `backend/docker-compose.yml`:
- username: `admin`
- password default fallback: `admin` (`KEYCLOAK_ADMIN_PASSWORD`)

### Redis

From `backend/docker-compose.yml`:
- dev: no password (`redis://redis:6379/0`)

From `backend/docker-compose.prod.yml`:
- production requires `REDIS_PASSWORD`

### Production secret variables

From `backend/.env.prod.example` and `backend/docker-compose.prod.yml`
(loaded by `scripts/deploy.sh` via `--env-file .env.prod`):

- `POSTGRES_USER`
- `POSTGRES_PASSWORD`
- `KEYCLOAK_ADMIN_PASSWORD`
- `KEYCLOAK_DB_PASSWORD`
- `REDIS_PASSWORD`
- `ACME_EMAIL`
- `API_HOSTNAME`
- `KEYCLOAK_HOSTNAME`

## 4) OIDC clients, scopes, and claims

Source: `backend/docker/keycloak-import/horus-realm.json`

### Realm and token settings

- realm: `horus`
- default realm role: `student`
- `accessTokenLifespan`: `300` seconds
- `ssoSessionIdleTimeout`: `1800` seconds
- `ssoSessionMaxLifespan`: `36000` seconds

### Clients

| Client ID | Type | Key settings |
|---|---|---|
| `horus-web` | public | `standardFlowEnabled=true`, PKCE `S256`, browser login client |
| `horus-api` | bearer-only | `bearerOnly=true`, token validation for backend |

### `horus-web` redirect/origin scope currently configured

- redirect URIs:
  - `http://localhost:3000/*`
  - `http://localhost:3001/*`
  - `http://localhost:3002/*`
  - `https://horusone.app/*`
  - `https://*.pages.dev/*`
- web origins:
  - `http://localhost:3000`
  - `http://localhost:3001`
  - `http://localhost:3002`
  - `https://horusone.app`
  - `+`
- post logout redirect URIs:
  - `http://localhost:3000/*`
  - `http://localhost:3001/*`
  - `http://localhost:3002/*`
  - `https://horusone.app/*`
  - `https://*.pages.dev/*`

### Default client scopes

`defaultDefaultClientScopes`:
- `web-origins`
- `acr`
- `profile`
- `roles`
- `email`
- `openid`

`horus-web.defaultClientScopes`:
- `openid`
- `email`
- `profile`
- `roles`

### Important mapped claims

- `organization_id` (from user attribute)
- `roles` (custom mapper)
- `realm_access.roles` (roles client scope mapper)
- `email`
- `email_verified`
- `preferred_username`
- audience includes `horus-api` in access token

## 5) Scope model from migrations (data ownership map)

Primary migration files:
- `a057912b7338_initial_schema.py`
- `b2c4e6f8a0d1_add_user_org_seat.py`
- `ee0e6be2458f_add_user_preferences.py`
- `c3a7f9d1e5b2_add_training_modules.py`
- `fac62be749f8_add_training_content_stats_plans_.py`

### Tables created per migration

- `a057...`: `scenarios`, `training_sessions`, `voice_logs`
- `b2c4...`: `users`, `organizations`, `seats`
- `ee0e...`: `user_preferences`
- `c3a7...`: `training_modules`, `module_scenarios`
- `fac62...`: `badges`, `content_categories`, `waypoints`, `content_articles`, `instructor_profiles`, `leaderboard_snapshots`, `student_stats`, `user_badges`, `flight_plans`, `knowledge_assessments`, `scenario_waypoints`, `assessment_results`, `flight_hour_logs`, `flight_insights`, `flight_plan_legs`, `maneuver_logs`, `session_tracks`

### Scope/ownership signals by key columns

| Table | Scope signals (columns) | Scope type |
|---|---|---|
| `users` | global identity (`keycloak_id`, `email`) | platform-global |
| `organizations` | tenant (`slug`) | platform-global tenant registry |
| `seats` | `user_id`, `organization_id`, `role` | org membership + RBAC |
| `scenarios` | (later) `org_id`, `created_by` | org-scoped content |
| `training_sessions` | `user_id`, `org_id`, `scenario_id` | org+user scoped runtime data |
| `voice_logs` | `session_id` | session-scoped |
| `user_preferences` | `user_id` unique | user-scoped |
| `training_modules` | `org_id`, `created_by` | org-scoped |
| `module_scenarios` | `module_id`, `scenario_id` | module/scenario mapping |
| `content_articles` | `org_id`, `category_id`, `author_id` | org content + taxonomy |
| `instructor_profiles` | `user_id` unique | instructor user-scoped |
| `leaderboard_snapshots` | `org_id` | org analytics snapshot |
| `student_stats` | `user_id` unique | user performance aggregate |
| `user_badges` | `user_id`, `badge_id` | user gamification |
| `flight_plans` | `user_id`, `org_id`, `scenario_id` | org+user scoped planning |
| `knowledge_assessments` | `org_id`, `module_id`, `created_by` | org learning scope |
| `scenario_waypoints` | `scenario_id`, `waypoint_id` | scenario route mapping |
| `assessment_results` | `user_id`, `assessment_id` | user assessment records |
| `flight_hour_logs` | `user_id`, `session_id` | user/session performance logs |
| `flight_insights` | `session_id` | session insights |
| `flight_plan_legs` | `flight_plan_id` | flight plan decomposition |
| `maneuver_logs` | `user_id`, `session_id` | user/session maneuver logs |
| `session_tracks` | `session_id` unique | session track replay data |

## 6) Backend auth/runtime env map

From `backend/.env.example`:

- `KEYCLOAK_ISSUER_URL=http://localhost:8180/realms/horus`
- `KEYCLOAK_CLIENT_ID=horus-api`
- `AUTH_ENABLED=true`
- `DATABASE_URL=postgresql+asyncpg://horus:horus@localhost:5432/horus_db`
- `REDIS_URL=redis://localhost:6379/0`
- `CORS_ORIGINS=http://localhost:3000,...,http://localhost:3002`

From container runtime (`backend/docker-compose.yml` backend service):
- backend talks to Keycloak on internal URL: `http://keycloak:8080/realms/horus`

---

If you rotate any credential or change IdP/client scopes, update this file and:
- `backend/docker/keycloak-import/horus-realm.json`
- `backend/.env.example`
- `backend/.env.docker.example`
- `backend/.env.prod.example`
- compose files (`backend/docker-compose*.yml`)
