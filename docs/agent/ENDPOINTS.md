# Operator Console MVP - API Endpoints

## Existing Endpoints (Pre-Phase 10)

### Content API
| Method | Path | Purpose | Auth |
|--------|------|---------|------|
| GET | /api/content/opportunities/ | Find content opportunities | AllowAny* |
| POST | /api/content/draft/ | Generate draft from articles | AllowAny* |
| GET | /api/content/articles/top/ | Get top 10 scored articles | AllowAny* |

*Will be changed to IsAuthenticated in Phase 10.1

### Observability
| Method | Path | Purpose | Auth |
|--------|------|---------|------|
| GET | /health/ | Full health check | AllowAny |
| GET | /health/{check_name}/ | Specific health check | AllowAny |
| GET | /livez/ | Kubernetes liveness probe | AllowAny |
| GET | /readyz/ | Kubernetes readiness probe | AllowAny |
| GET | /metrics/ | Prometheus metrics | AllowAny |
| GET | /status/ | System status JSON | AllowAny |

### Admin
| Method | Path | Purpose | Auth |
|--------|------|---------|------|
| * | /admin/ | Django admin interface | Admin |
| GET | /api/ | DRF browsable API | Session |

---

## Phase 10.1: Auth Endpoints (NEW)

| Method | Path | Purpose | Auth | Request | Response |
|--------|------|---------|------|---------|----------|
| POST | /api/auth/login/ | Obtain JWT tokens | AllowAny | `{username, password}` | `{access, refresh}` |
| POST | /api/auth/refresh/ | Refresh access token | AllowAny | `{refresh}` | `{access}` |
| GET | /api/auth/me/ | Get current user info | JWT | - | `{id, username, email, profile}` |
| POST | /api/auth/logout/ | Blacklist refresh token | JWT | `{refresh}` | `{}` |

---

## Phase 10.2: Runs Endpoints (IMPLEMENTED)

| Method | Path | Purpose | Auth | Status |
|--------|------|---------|------|--------|
| GET | /api/sources/runs/ | List all runs | JWT | ✅ |
| GET | /api/sources/runs/{id}/ | Get run details | JWT | ✅ |
| POST | /api/sources/runs/start/ | Start new run | JWT | ✅ |
| POST | /api/sources/runs/{id}/cancel/ | Cancel running job | JWT | ✅ |
| GET | /api/sources/ | List sources for runs | JWT | ✅ |

---

## Phase 10.3: Schedules Endpoints (IMPLEMENTED)

| Method | Path | Purpose | Auth | Status |
|--------|------|---------|------|--------|
| GET | /api/sources/schedules/ | List all schedules | JWT | ✅ |
| POST | /api/sources/schedules/ | Create schedule | JWT | ✅ |
| GET | /api/sources/schedules/{id}/ | Get schedule details | JWT | ✅ |
| PUT | /api/sources/schedules/{id}/ | Update schedule | JWT | ✅ |
| DELETE | /api/sources/schedules/{id}/ | Delete schedule | JWT | ✅ |
| POST | /api/sources/schedules/{id}/toggle/ | Toggle enabled state | JWT | ✅ |
| POST | /api/sources/schedules/{id}/run-now/ | Trigger immediate run | JWT | ✅ |
| POST | /api/sources/schedules/pause-all/ | Pause/resume all | JWT | ✅ |
| POST | /api/sources/schedules/bulk/ | Bulk enable/disable/delete | JWT | ✅ | |

---

## Phase 10.4: Seeds Endpoints (IMPLEMENTED)

| Method | Path | Purpose | Auth | Status |
|--------|------|---------|------|--------|
| GET | /api/seeds/ | List all seeds | JWT | ✅ |
| POST | /api/seeds/ | Add single seed | JWT | ✅ |
| GET | /api/seeds/{id}/ | Get seed details | JWT | ✅ |
| PUT | /api/seeds/{id}/ | Update seed | JWT | ✅ |
| DELETE | /api/seeds/{id}/ | Delete seed | JWT | ✅ |
| POST | /api/seeds/import/ | Bulk import seeds | JWT | ✅ |
| POST | /api/seeds/{id}/validate/ | Validate seed URL | JWT | ✅ |
| POST | /api/seeds/{id}/promote/ | Promote to Source | JWT | ✅ |
| POST | /api/seeds/{id}/reject/ | Reject seed | JWT | ✅ |
| POST | /api/seeds/promote-batch/ | Batch promote seeds | JWT | ✅ |
| GET | /api/seeds/stats/ | Seed statistics | JWT | ✅ |
| GET | /api/seeds/batches/ | List import batches | JWT | ✅ |
| GET | /api/seeds/batches/{id}/ | Batch details | JWT | ✅ |

---

## Phase 10.5: Articles Endpoints (IMPLEMENTED)

| Method | Path | Purpose | Auth | Status |
|--------|------|---------|------|--------|
| GET | /api/articles/ | List articles (filterable) | JWT | ✅ |
| GET | /api/articles/{id}/ | Get full article detail | JWT | ✅ |
| GET | /api/articles/{id}/info/ | Tab 1: Article info | JWT | ✅ |
| GET | /api/articles/{id}/raw_capture/ | Tab 2: Raw capture | JWT | ✅ |
| GET | /api/articles/{id}/extracted/ | Tab 3: Extracted text | JWT | ✅ |
| GET | /api/articles/{id}/scores/ | Tab 4: Score breakdown | JWT | ✅ |
| GET | /api/articles/{id}/llm_artifacts/ | Tab 5: LLM artifacts | JWT | ✅ |
| GET | /api/articles/{id}/images/ | Tab 6: Images | JWT | ✅ |
| GET | /api/articles/{id}/usage/ | Tab 7: Usage history | JWT | ✅ |
| GET | /api/articles/llm_artifacts/{id}/ | LLM artifact detail | JWT | ✅ |
| GET | /api/articles/stats/ | Article statistics | JWT | ✅ |

### Article List Filters
- `?status=` - Filter by processing status
- `?source=` - Filter by source ID
- `?quality=high|medium|low|unscored` - Filter by quality category
- `?topic=` - Filter by primary topic (contains)
- `?region=` - Filter by primary region
- `?ai_detected=true|false` - Filter by AI detection
- `?used=true|false` - Filter by usage status
- `?search=` - Search title/URL

---

## Phase 10.6: LLM Settings Endpoints (IMPLEMENTED)

| Method | Path | Purpose | Auth | Status |
|--------|------|---------|------|--------|
| GET | /api/settings/llm/ | Get LLM settings | JWT | ✅ |
| PATCH | /api/settings/llm/ | Update LLM settings | JWT | ✅ |
| GET | /api/settings/llm/usage/ | Get usage stats | JWT | ✅ |
| GET | /api/settings/llm/usage/by-prompt/ | Usage by prompt | JWT | ✅ |
| GET | /api/settings/llm/usage/by-model/ | Usage by model | JWT | ✅ |
| GET | /api/settings/llm/budget/ | Get budget status | JWT | ✅ |
| GET | /api/settings/llm/models/ | List available models | JWT | ✅ |
| POST | /api/settings/llm/reset-budget/ | Reset budget | JWT | ✅ |
| GET | /api/settings/llm/logs/ | Recent usage logs | JWT | ✅ |

### LLM Settings Fields
- `default_model` - Primary model to use
- `fallback_model` - Fallback when primary fails
- `temperature` - Generation temperature (0.0-1.0)
- `max_tokens` - Maximum output tokens
- `daily_budget_usd` - Daily spending limit
- `monthly_budget_usd` - Monthly spending limit
- `budget_alert_threshold` - Alert at % of budget
- `enforce_budget` - Block requests when exceeded
- `caching_enabled` - Enable response caching
- `cache_ttl_hours` - Cache time-to-live
- `ai_detection_enabled` - Enable AI detection feature
- `content_analysis_enabled` - Enable content analysis
- `requests_per_minute` - Rate limiting

### Usage Query Parameters
- `?period=day|week|month` - Time period for usage stats
- `?days=N` - Number of days for by-prompt/by-model

### Budget Status Response
```json
{
  "daily_budget_usd": "50.00",
  "monthly_budget_usd": "500.00",
  "daily_used_usd": 12.50,
  "monthly_used_usd": 125.00,
  "daily_remaining_usd": 37.50,
  "monthly_remaining_usd": 375.00,
  "daily_percent_used": 25.0,
  "monthly_percent_used": 25.0,
  "budget_exceeded": false,
  "alert_triggered": false
}
```

---

## HTMX UI Routes (Templates)

| Path | Template | Purpose |
|------|----------|---------|
| / | index.html | Dashboard home |
| /login/ | auth/login.html | Login form |
| /runs/ | runs/list.html | Runs list + start modal |
| /runs/{id}/ | runs/detail.html | Run detail view |
| /schedules/ | schedules/list.html | Schedules management |
| /schedules/{id}/ | schedules/detail.html | Schedule detail + history |
| /seeds/ | seeds/list.html | Seeds list + import wizard |
| /seeds/{id}/ | seeds/detail.html | Seed detail + promote |
| /articles/ | articles/list.html | Article listing |
| /articles/{id}/ | articles/detail.html | Article viewer (7 tabs) |
| /settings/llm/ | settings/llm.html | LLM settings page |

---

## Response Formats

### Success Response
```json
{
  "id": "uuid",
  "field": "value",
  ...
}
```

### List Response
```json
{
  "count": 100,
  "next": "/api/resource/?page=2",
  "previous": null,
  "results": [...]
}
```

### Error Response
```json
{
  "error": "error_code",
  "message": "Human readable message",
  "details": {...}
}
```
