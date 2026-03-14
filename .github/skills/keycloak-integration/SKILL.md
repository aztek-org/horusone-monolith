---
name: Keycloak Integration
description: >
  Step-by-step guide to add Keycloak-protected routes and resources to the
  Horus backend (FastAPI) and frontend (Nuxt), including JWT validation,
  role checks, and org-scoped data access.
---

# Add Keycloak-Protected Route

Use this skill when adding authentication/authorization to a new endpoint or page.

## Backend (FastAPI) — Protect an API Endpoint

### 1. Import Auth Dependencies

```python
from app.middleware.auth import get_current_user, require_role, get_org_id
```

### 2. Add Auth to Route

```python
# Public endpoint (no auth)
@router.get("/public-info")
async def get_public_info() -> dict:
    return {"message": "no auth required"}

# Authenticated endpoint (any valid user)
@router.get("/my-profile")
async def get_profile(
    user: dict = Depends(get_current_user),
) -> dict:
    return {"user_id": user["sub"], "email": user["email"]}

# Role-restricted endpoint
@router.post("/scenarios")
async def create_scenario(
    data: ScenarioCreate,
    user: dict = Depends(require_role("instructor")),
    session: AsyncSession = Depends(get_db_session),
) -> ScenarioResponse:
    ...

# Org-scoped endpoint
@router.get("/scenarios")
async def list_scenarios(
    org_id: str = Depends(get_org_id),
    session: AsyncSession = Depends(get_db_session),
) -> list[ScenarioResponse]:
    return await scenario_repo.get_by_org(session, org_id)
```

### 3. Update Config if Needed

Ensure `app/config.py` has Keycloak settings:
```python
keycloak_url: str = "http://keycloak:8080"
keycloak_realm: str = "horus"
keycloak_client_id: str = "horus-api"
keycloak_public_key: str = ""
```

### 4. Write Tests with Mocked Auth

```python
from unittest.mock import patch

@patch("app.middleware.auth.get_current_user")
async def test_protected_endpoint(mock_user, client):
    mock_user.return_value = {
        "sub": "test-uuid",
        "realm_access": {"roles": ["instructor"]},
        "organization_id": "org-uuid",
    }
    response = client.get("/api/v1/scenarios")
    assert response.status_code == 200
```

## Frontend (Nuxt) — Protect a Page

### 1. Use Auth Composable

```vue
<script setup lang="ts">
const { user, isAuthenticated, login } = useAuth()

if (!isAuthenticated.value) {
  login()
}
</script>
```

### 2. Role-Guard a Page

```vue
<script setup lang="ts">
const { user } = useAuth()

if (!user.value?.roles.includes('instructor')) {
  throw createError({ statusCode: 403, message: 'Instructors only' })
}
</script>
```

### 3. Pass JWT to API Calls

```typescript
const { token } = useAuth()
const config = useRuntimeConfig()

const { data } = useFetch(`${config.public.apiUrl}/api/v1/scenarios`, {
  headers: { Authorization: `Bearer ${token.value}` },
})
```

## Keycloak Admin — Add a New Role

1. Open Keycloak admin console → Realm `horus` → Realm roles
2. Click "Create role" → Enter role name (e.g., `fleet-manager`)
3. Create a protocol mapper if the role needs custom claims
4. Assign role to test users via Users → Role mappings
5. Update backend `require_role()` calls to use the new role
