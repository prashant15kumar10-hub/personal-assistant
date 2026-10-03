# Engineering and System Design Guide

| Area | Included foundation | Production recommendation |
|---|---|---|
| Caching | Browser cache policy and cache-ready architecture | Redis for sessions and computed recommendations |
| CDN | Deployment guidance | Cloudflare, Fastly or cloud CDN for static assets |
| Authentication / permissions | PBKDF2 passwords, secure cookies, admin/student roles | Managed identity, email verification and password reset |
| Testing | Unit tests and CI test job | Integration, browser, load and security tests |
| System architecture | Architecture document | Stateless services behind a load balancer |
| Rate limiting | Per-IP in-memory limiter | Distributed Redis-backed limiter |
| Cloud hosting | Docker, Compose and Render blueprint | AWS, Azure, GCP, Render or Railway |
| Error tracking | Rotating error logs | Sentry or equivalent with release tracking |
| Logging | Structured server logs with rotation | Centralized OpenTelemetry logs |
| Frontend | Responsive HTML/CSS/JS and dark mode | Split static assets and use a component framework if needed |
| Scaling | Threaded server and stateless design path | Multiple replicas, queue workers and autoscaling |
| Databases | SQLite with indexes | Managed PostgreSQL, migrations and backups |
| Security | CSP, secure headers, hashed passwords and input checks | TLS, secrets manager, WAF and dependency scanning |
| Storage | Local database and logs | Object storage for uploads; encrypted database storage |
| CI/CD | GitHub Actions workflow | Add staging, approvals, migrations and rollback |
| Version control | `.gitignore` and repository-ready layout | Protected branches, pull requests and semantic releases |
| Monitoring | `/health` and authenticated `/metrics` | Prometheus/Grafana or managed monitoring |
| Notifications | Browser-ready client foundation | Push, email and SMS worker queue |
| API | JSON endpoints with authentication and status codes | Version under `/api/v1`, publish an OpenAPI contract |
| Backend logic | Routine, task, study-plan, health and assistant services | Split into service modules as the codebase grows |
| System design | Local and cloud target designs documented | Capacity planning, SLOs, disaster recovery and threat modeling |

## CDN
Move CSS and JavaScript to versioned files under `static/`, set immutable cache headers, and place a CDN in front of the app. HTML and authenticated API responses must not be publicly cached.

## Scaling path
1. Replace SQLite with PostgreSQL.
2. Move sessions and rate limits to Redis.
3. Store uploads in S3-compatible object storage.
4. Run multiple stateless application replicas behind a load balancer.
5. Move notifications and long-running AI work to a queue worker.

## Security limitations
This remains an educational starter. Before accepting real user data, add TLS, CSRF tokens, persistent server-side sessions, account recovery, email verification, secrets management, database-level user isolation, security scanning and professional review.
