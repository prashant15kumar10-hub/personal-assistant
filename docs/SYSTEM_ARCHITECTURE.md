# System Architecture

```text
Browser / Mobile Web
        │ HTTPS
        ▼
CDN + Web Application Firewall
        │
        ▼
Load Balancer / Reverse Proxy
        │
  ┌─────┴─────────────┐
  │ Application API  │  Authentication, permissions, rate limits, business rules
  └─────┬─────────────┘
        │
  ┌─────┼──────────┬───────────┐
  ▼     ▼          ▼           ▼
Cache  PostgreSQL Object      Notification service
Redis  database   storage     email/push/SMS
  │
  ▼
Logs, metrics and error tracking
```

The local edition uses one Python process and SQLite. The cloud design separates stateless application servers from shared data, caching, object storage and notification services.
