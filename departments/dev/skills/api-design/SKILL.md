---
name: dev/api-design
description: >
  Design REST or GraphQL APIs with versioning, documentation, and contracts.
  Follows OpenAPI spec for REST, SDL for GraphQL.
allowed-tools: [Read, Write, Edit, Bash, Grep, Glob, Agent]
---

# API Design — `/dev api-design <api>`

> **Agent:** Gabriel (Architect) + Andre (Backend)
> **Output:** OpenAPI spec or GraphQL SDL + endpoint documentation

## REST API Design Principles

1. **Resource-oriented** — URLs are nouns, not verbs (`/users`, not `/getUsers`)
2. **HTTP methods** — GET (read), POST (create), PUT (replace), PATCH (update), DELETE
3. **Status codes** — 200 OK, 201 Created, 400 Bad Request, 401 Unauthorized, 404 Not Found, 422 Unprocessable
4. **Pagination** — `?page=1&per_page=20` with Link headers or cursor-based
5. **Filtering** — `?status=active&role=admin`
6. **Versioning** — URL prefix (`/api/v1/`) or header (`Accept: application/vnd.api+json;version=1`)
7. **Consistent response** — `{ "data": ..., "meta": { "pagination": ... } }`
8. **Error format** — `{ "error": { "code": "VALIDATION_FAILED", "message": "...", "details": [...] } }`

## Output: OpenAPI Snippet

```yaml
openapi: 3.0.3
info:
  title: <API Name>
  version: 1.0.0
paths:
  /api/v1/<resource>:
    get:
      summary: List <resources>
      parameters:
        - name: page
          in: query
          schema: { type: integer, default: 1 }
      responses:
        '200':
          description: Success
          content:
            application/json:
              schema:
                type: object
                properties:
                  data:
                    type: array
                    items: { $ref: '#/components/schemas/<Resource>' }
```

## Laravel Convention

- Routes: `routes/api.php` with `apiResource()`
- Controllers: `App\Http\Controllers\Api\V1\<Resource>Controller`
- Requests: `App\Http\Requests\<Resource>\Store<Resource>Request`
- Resources: `App\Http\Resources\<Resource>Resource`
- Tests: `tests/Feature/Api/V1/<Resource>Test.php`
