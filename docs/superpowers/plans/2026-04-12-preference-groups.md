# Preference Groups Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Allow authenticated users to create personal preference groups and associate MCP services and skills to them.

**Architecture:** New `users` table (auto-created on first Google login), `preference_groups` table with user FK, and two M2M junction tables. New FastAPI router for CRUD. Frontend: dedicated /groups page + inline dropdown on service/skill detail pages.

**Tech Stack:** SQLAlchemy async, FastAPI, React + TanStack Query, Tailwind CSS

---

## File Structure

### Backend
- **Modify:** `backend/mcp_manager/db/models.py` — Add `User`, `PreferenceGroup`, junction tables
- **Modify:** `backend/mcp_manager/api/routers/auth.py` — Upsert user on callback, add `require_authenticated` dep
- **Create:** `backend/mcp_manager/api/routers/preference_groups.py` — Full CRUD router
- **Modify:** `backend/mcp_manager/api/app.py` — Register new router
- **Modify:** `backend/scripts/init.sql` — Add table DDL for fresh installs

### Frontend
- **Create:** `frontend/src/api/preference-groups.ts` — React Query hooks
- **Create:** `frontend/src/pages/GroupsPage.tsx` — List + create groups
- **Create:** `frontend/src/pages/GroupDetailPage.tsx` — Group detail with services + skills
- **Create:** `frontend/src/components/domain/GroupPicker.tsx` — Reusable dropdown for service/skill detail pages
- **Modify:** `frontend/src/pages/ServiceDetailPage.tsx` — Add GroupPicker
- **Modify:** `frontend/src/pages/SkillDetailPage.tsx` — Add GroupPicker
- **Modify:** `frontend/src/App.tsx` — Add routes
- **Modify:** `frontend/src/layouts/MainLayout.tsx` — Add nav link

---

### Task 1: Database Models

**Files:**
- Modify: `backend/mcp_manager/db/models.py`
- Modify: `backend/scripts/init.sql`

- [ ] Add `User` model (id UUID PK, email unique, name, picture, created_at)
- [ ] Add `preference_group_services` junction table (group_id FK, mcp_service_id FK, PK composite)
- [ ] Add `preference_group_skills` junction table (group_id FK, skill_id FK, PK composite)
- [ ] Add `PreferenceGroup` model (id UUID PK, user_id FK→users, name, description nullable, created_at, updated_at)
- [ ] Add relationships on PreferenceGroup (services, skills, user)
- [ ] Add SQL DDL to init.sql for fresh installs
- [ ] Run CREATE TABLE manually on LXC 113 for existing DB

### Task 2: Auth — Upsert User on Login

**Files:**
- Modify: `backend/mcp_manager/api/routers/auth.py`

- [ ] Add `_upsert_user(email, name, picture)` async function using `INSERT ... ON CONFLICT(email) DO UPDATE`
- [ ] Call it in `auth_callback` after getting Google user info
- [ ] Add `require_authenticated` dependency (like `require_admin` but any logged-in user)
- [ ] Return `user_id` (UUID) in the JWT payload and in `/auth/me` response

### Task 3: Backend Router — Preference Groups CRUD

**Files:**
- Create: `backend/mcp_manager/api/routers/preference_groups.py`
- Modify: `backend/mcp_manager/api/app.py`

- [ ] `GET /preference-groups` — list current user's groups with service_count + skill_count
- [ ] `POST /preference-groups` — create group (body: `{name, description?}`)
- [ ] `GET /preference-groups/{id}` — detail with services list + skills list
- [ ] `PUT /preference-groups/{id}` — update name/description
- [ ] `DELETE /preference-groups/{id}` — delete group + cascade associations
- [ ] `POST /preference-groups/{id}/services/{service_id}` — add service
- [ ] `DELETE /preference-groups/{id}/services/{service_id}` — remove service
- [ ] `POST /preference-groups/{id}/skills/{skill_id}` — add skill
- [ ] `DELETE /preference-groups/{id}/skills/{skill_id}` — remove skill
- [ ] `GET /services/{service_id}/groups` — list groups containing this service (for the detail page)
- [ ] `GET /skills/{skill_id}/groups` — list groups containing this skill
- [ ] Register router in `app.py`

### Task 4: Frontend API Hooks

**Files:**
- Create: `frontend/src/api/preference-groups.ts`

- [ ] `usePreferenceGroups()` — GET /preference-groups
- [ ] `usePreferenceGroup(id)` — GET /preference-groups/{id}
- [ ] `useCreateGroup()` — POST mutation
- [ ] `useUpdateGroup(id)` — PUT mutation
- [ ] `useDeleteGroup(id)` — DELETE mutation
- [ ] `useAddServiceToGroup()` — POST mutation
- [ ] `useRemoveServiceFromGroup()` — DELETE mutation
- [ ] `useAddSkillToGroup()` — POST mutation
- [ ] `useRemoveSkillFromGroup()` — DELETE mutation
- [ ] `useServiceGroups(serviceId)` — GET /services/{id}/groups
- [ ] `useSkillGroups(skillId)` — GET /skills/{id}/groups

### Task 5: Groups Page + Detail Page

**Files:**
- Create: `frontend/src/pages/GroupsPage.tsx`
- Create: `frontend/src/pages/GroupDetailPage.tsx`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/layouts/MainLayout.tsx`

- [ ] GroupsPage: list groups as cards, each showing name + service/skill counts + badge
- [ ] Inline creation: text input + button "Créer"
- [ ] Click on group → navigate to /groups/{id}
- [ ] GroupDetailPage: group name editable, description, two lists (services + skills), remove button per item
- [ ] Delete group button
- [ ] Add routes in App.tsx
- [ ] Add "Groups" nav link (for authenticated users, not admin-only)

### Task 6: GroupPicker Component + Integration

**Files:**
- Create: `frontend/src/components/domain/GroupPicker.tsx`
- Modify: `frontend/src/pages/ServiceDetailPage.tsx`
- Modify: `frontend/src/pages/SkillDetailPage.tsx`

- [ ] GroupPicker: button "+ Groupe" → dropdown with user's groups + "Créer un groupe" option
- [ ] On select: POST to add service/skill to group, invalidate queries
- [ ] On "Créer": inline input to name new group, then auto-add
- [ ] Group badges displayed below service/skill title (click badge → remove with confirm)
- [ ] Integrate GroupPicker on ServiceDetailPage
- [ ] Integrate GroupPicker on SkillDetailPage

### Task 7: Deploy + Test

- [ ] Build frontend
- [ ] Deploy to LXC 113 (backend + frontend)
- [ ] Create tables on existing DB
- [ ] Test: login → create group → add service → add skill → view group → remove → delete group
