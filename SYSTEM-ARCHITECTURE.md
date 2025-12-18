# Python ERP System - Architecture Overview

## 🏗️ System Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           USER INTERFACE LAYER                           │
│                                                                          │
│  ┌───────────────────────────────────────────────────────────────────┐ │
│  │                        Vue 3 Frontend                              │ │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────────┐  │ │
│  │  │Dashboard │  │Projects  │  │Purchase  │  │  Global Search   │  │ │
│  │  │   (RT)   │  │ (Gantt)  │  │  (RFQ)   │  │ (Elasticsearch)  │  │ │
│  │  └──────────┘  └──────────┘  └──────────┘  └──────────────────┘  │ │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────────┐  │ │
│  │  │  Sales   │  │Inventory │  │ Finance  │  │  Notifications   │  │ │
│  │  │ (Invoice)│  │(Barcode) │  │(Currency)│  │   (WebSocket)    │  │ │
│  │  └──────────┘  └──────────┘  └──────────┘  └──────────────────┘  │ │
│  │                                                                    │ │
│  │  State Management: Pinia  |  Router: Vue Router  |  UI: Element+ │ │
│  └───────────────────────────────────────────────────────────────────┘ │
│                              ▲          ▲                               │
│                              │          │                               │
│                          HTTP/REST   WebSocket                          │
│                              │          │                               │
└──────────────────────────────┼──────────┼───────────────────────────────┘
                               │          │
┌──────────────────────────────┼──────────┼───────────────────────────────┐
│                           API GATEWAY LAYER                             │
│                               │          │                               │
│  ┌────────────────────────────▼──────────▼────────────────────────────┐ │
│  │                         Nginx (Port 80)                             │ │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐ │ │
│  │  │   Static     │  │    API       │  │     WebSocket            │ │ │
│  │  │   Files      │  │  /api/*      │  │      /ws/*               │ │ │
│  │  └──────────────┘  └──────────────┘  └──────────────────────────┘ │ │
│  └─────────────────────────────────────────────────────────────────────┘ │
└──────────────────────────────┬──────────┬───────────────────────────────┘
                               │          │
┌──────────────────────────────┼──────────┼───────────────────────────────┐
│                      APPLICATION LAYER                                  │
│                               │          │                               │
│  ┌────────────────────────────▼──────────▼────────────────────────────┐ │
│  │            Django Backend (Daphne ASGI + Gunicorn)                  │ │
│  │  Port: 8000                                                         │ │
│  │                                                                     │ │
│  │  ┌─────────────────────────────────────────────────────────────┐  │ │
│  │  │                    Django Apps (9)                           │  │ │
│  │  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌────────────┐  │  │ │
│  │  │  │  Core    │  │ Accounts │  │MasterData│  │  Projects  │  │  │ │
│  │  │  │(Audit)   │  │  (RBAC)  │  │(Items)   │  │   (PM)     │  │  │ │
│  │  │  └──────────┘  └──────────┘  └──────────┘  └────────────┘  │  │ │
│  │  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌────────────┐  │  │ │
│  │  │  │ Purchase │  │  Sales   │  │Inventory │  │  Finance   │  │  │ │
│  │  │  │  (RFQ)   │  │(Invoice) │  │ (Batch)  │  │(Currency)  │  │  │ │
│  │  │  └──────────┘  └──────────┘  └──────────┘  └────────────┘  │  │ │
│  │  │  ┌──────────┐                                               │  │ │
│  │  │  │Analytics │                                               │  │ │
│  │  │  │  (KPI)   │                                               │  │ │
│  │  │  └──────────┘                                               │  │ │
│  │  └─────────────────────────────────────────────────────────────┘  │ │
│  │                                                                     │ │
│  │  ┌─────────────────────────────────────────────────────────────┐  │ │
│  │  │                    Services Layer                            │  │ │
│  │  │  • Cost Calculation    • PDF Generation                      │  │ │
│  │  │  • WebSocket Notifier  • Barcode Generator                   │  │ │
│  │  │  • Email Service       • Analytics Service                   │  │ │
│  │  └─────────────────────────────────────────────────────────────┘  │ │
│  │                                                                     │ │
│  │  ┌─────────────────────────────────────────────────────────────┐  │ │
│  │  │                 WebSocket Consumers                          │  │ │
│  │  │  • NotificationConsumer   • DashboardConsumer                │  │ │
│  │  └─────────────────────────────────────────────────────────────┘  │ │
│  └─────────────────────────────────────────────────────────────────────┘ │
│                        ▲         ▲         ▲         ▲                  │
└────────────────────────┼─────────┼─────────┼─────────┼──────────────────┘
                         │         │         │         │
┌────────────────────────┼─────────┼─────────┼─────────┼──────────────────┐
│                  DATA & SERVICES LAYER                                  │
│                        │         │         │         │                  │
│  ┌─────────────────────▼──┐  ┌───▼────────▼─────┐  ┌▼───────────────┐  │
│  │   PostgreSQL 15        │  │      Redis 7      │  │Elasticsearch 8 │  │
│  │   Port: 5432           │  │    Port: 6379     │  │  Port: 9200    │  │
│  │                        │  │                   │  │                │  │
│  │  ┌──────────────────┐  │  │  ┌────────────┐  │  │ ┌────────────┐ │  │
│  │  │  40+ Tables      │  │  │  │   Cache    │  │  │ │   Items    │ │  │
│  │  │  • Projects      │  │  │  │ • Sessions │  │  │ │ Customers  │ │  │
│  │  │  • Items         │  │  │  │ • Cost     │  │  │ │ Suppliers  │ │  │
│  │  │  • Customers     │  │  │  └────────────┘  │  │ │ Projects   │ │  │
│  │  │  • Orders        │  │  │                   │  │ │ Tasks      │ │  │
│  │  │  • Stock         │  │  │  ┌────────────┐  │  │ └────────────┘ │  │
│  │  │  • Transactions  │  │  │  │  Channels  │  │  │                │  │
│  │  │  • Audit Logs    │  │  │  │  Layer     │  │  │  Full-text     │  │
│  │  │  • Batches       │  │  │  │(WebSocket) │  │  │  Search        │  │
│  │  │  • RFQs          │  │  │  └────────────┘  │  │  Fuzzy Match   │  │
│  │  │  • Currencies    │  │  │                   │  │  Auto-complete │  │
│  │  └──────────────────┘  │  │  ┌────────────┐  │  │                │  │
│  │                        │  │  │   Celery   │  │  └────────────────┘  │
│  │  ACID Transactions     │  │  │   Broker   │  │                     │  │
│  │  Foreign Keys          │  │  │   Queue    │  │  Relevance Scoring  │  │
│  │  Indexes               │  │  └────────────┘  │  Field Boosting     │  │
│  │  Constraints           │  │                   │  5 Indexes          │  │
│  └────────────────────────┘  └───────────────────┘  └──────────────────┘  │
│                                       │                                   │
└───────────────────────────────────────┼───────────────────────────────────┘
                                        │
┌───────────────────────────────────────▼───────────────────────────────────┐
│                     BACKGROUND PROCESSING LAYER                           │
│                                                                            │
│  ┌──────────────────────────────────────────────────────────────────────┐ │
│  │                     Celery Distributed Task Queue                     │ │
│  │                                                                        │ │
│  │  ┌────────────────────────────────┐  ┌──────────────────────────────┐│ │
│  │  │      Celery Worker             │  │      Celery Beat             ││ │
│  │  │                                 │  │    (Scheduler)               ││ │
│  │  │  • Low Stock Alerts            │  │                              ││ │
│  │  │  • Cost Recalculation          │  │  Scheduled Tasks:            ││ │
│  │  │  • Email Sending               │  │  • Nightly cost calc (3 AM)  ││ │
│  │  │  • PDF Generation              │  │  • Low stock check (hourly)  ││ │
│  │  │  • Batch Processing            │  │  • AR/AP aging (daily)       ││ │
│  │  │  • Report Generation           │  │  • Index rebuild (optional)  ││ │
│  │  │                                 │  │                              ││ │
│  │  │  Async, Distributed,           │  │  Cron-like Scheduling        ││ │
│  │  │  Retry Logic, Error Handling   │  │  Timezone-aware              ││ │
│  │  └────────────────────────────────┘  └──────────────────────────────┘│ │
│  └──────────────────────────────────────────────────────────────────────┘ │
└────────────────────────────────────────────────────────────────────────────┘
```

---

## 🔄 Data Flow Patterns

### Pattern 1: Standard CRUD Operation
```
User Action (Frontend)
    ↓
HTTP Request + JWT Token
    ↓
Nginx → Django API View
    ↓
Permission Check (RBAC)
    ↓
Serializer Validation
    ↓
Database Transaction (PostgreSQL)
    ↓
Post-save Signals:
  • Audit Log Entry
  • Elasticsearch Index Update
  • Cache Invalidation (Redis)
    ↓
HTTP Response (JSON)
    ↓
Frontend State Update
```

### Pattern 2: Real-time Notification
```
Backend Event (e.g., New Order)
    ↓
Create Notification Record (PostgreSQL)
    ↓
WebSocketNotifier.send_notification_to_user()
    ↓
Message → Redis Channel Layer
    ↓
NotificationConsumer receives
    ↓
WebSocket Send to Client(s)
    ↓
Frontend: Toast Notification
    ↓
Update Notification Center Badge
```

### Pattern 3: Global Search
```
User Types Query (2+ chars)
    ↓
Debounced API Call
    ↓
GlobalSearchViewSet.suggest()
    ↓
Query Elasticsearch
    ↓
Multi-field Match with Fuzzy
    ↓
Score & Sort Results
    ↓
Return Top N Suggestions
    ↓
Display in Autocomplete Dropdown
```

### Pattern 4: Background Processing
```
User Initiates Action (e.g., Bulk Import)
    ↓
API Enqueues Celery Task
    ↓
Return "Processing..." Response
    ↓
Celery Worker Picks Up Task
    ↓
Process Data (Long-running)
    ↓
Update Status in Database
    ↓
Send WebSocket Notification on Completion
    ↓
User Receives Real-time Update
```

### Pattern 5: Cost Calculation
```
Scheduled Job (Celery Beat - 3 AM)
    ↓
Trigger: recalculate_project_costs
    ↓
Query Active Projects
    ↓
For Each Project:
  • Material Cost (Stock Moves)
  • Labor Cost (Task Hours × Rate)
  • Expense Cost (Approved Expenses)
  • Revenue (Sales Orders)
    ↓
Calculate Profit & Margin
    ↓
Update Project Record
    ↓
Cache Results (Redis, 1 hour)
    ↓
Broadcast Dashboard Update (WebSocket)
```

---

## 🗄️ Database Schema Overview

### Core Tables (40+)

**Master Data:**
- `items` - Product/material master
- `customers` - Customer master
- `suppliers` - Supplier master
- `warehouses` - Warehouse locations
- `currencies` - Currency definitions
- `users` - System users
- `roles` - Role definitions
- `departments` - Organization structure

**Projects:**
- `projects` - Project master
- `project_members` - Project team
- `project_tasks` - WBS tasks
- `project_boms` - Material requirements

**Purchase:**
- `purchase_requests` - PRs
- `purchase_request_lines` - PR items
- `rfqs` - Request for Quotations
- `rfq_lines` - RFQ items
- `rfq_suppliers` - RFQ distribution
- `supplier_quotations` - Supplier quotes
- `purchase_orders` - POs
- `purchase_order_lines` - PO items
- `goods_receipts` - GR records
- `goods_receipt_lines` - GR items

**Sales:**
- `sales_quotations` - Sales quotes
- `sales_quotation_lines` - Quote items
- `sales_orders` - Sales orders
- `sales_order_lines` - SO items
- `delivery_orders` - Shipments
- `delivery_order_lines` - DO items

**Inventory:**
- `stock` - Current stock levels
- `stock_moves` - Inventory transactions
- `stock_adjustments` - Cycle counts
- `stock_adjustment_lines` - Adjustment items
- `batches` - Batch/lot tracking
- `batch_stock` - Batch inventory

**Finance:**
- `expenses` - Expense claims
- `account_receivables` - Customer AR
- `account_payables` - Supplier AP
- `payments` - Payment records
- `exchange_rates` - FX rates history

**System:**
- `audit_logs` - Change tracking
- `system_notifications` - In-app notifications

---

## 🔐 Security Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Security Layers                           │
│                                                              │
│  Layer 1: Network                                            │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  • HTTPS/TLS (Production)                            │   │
│  │  • CORS Configuration                                │   │
│  │  • Rate Limiting (optional)                          │   │
│  │  • Firewall Rules                                    │   │
│  └──────────────────────────────────────────────────────┘   │
│                          ↓                                   │
│  Layer 2: Authentication                                     │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  • JWT Token Authentication                          │   │
│  │  • Token Expiry & Refresh                            │   │
│  │  • Password Hashing (Django PBKDF2)                  │   │
│  │  • Session Management                                │   │
│  └──────────────────────────────────────────────────────┘   │
│                          ↓                                   │
│  Layer 3: Authorization                                      │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  • Role-Based Access Control (RBAC)                  │   │
│  │  • Menu Permissions                                  │   │
│  │  • API Endpoint Permissions                          │   │
│  │  • Data-Level Permissions (Own/Dept/All)            │   │
│  │  • Button-Level Permissions (Frontend)              │   │
│  └──────────────────────────────────────────────────────┘   │
│                          ↓                                   │
│  Layer 4: Data Protection                                    │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  • SQL Injection Prevention (ORM)                    │   │
│  │  • XSS Protection (Django templates)                 │   │
│  │  • CSRF Tokens                                       │   │
│  │  • Input Validation (Serializers)                    │   │
│  │  • Output Encoding                                   │   │
│  └──────────────────────────────────────────────────────┘   │
│                          ↓                                   │
│  Layer 5: Audit & Monitoring                                 │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  • Complete Audit Trail                              │   │
│  │  • User Action Logging                               │   │
│  │  • Failed Login Tracking                             │   │
│  │  • Security Event Alerts                             │   │
│  └──────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────┘
```

---

## 📊 Technology Stack Details

### Backend Stack
```
Python 3.11
├── Django 4.2 (Web Framework)
│   ├── Django REST Framework (API)
│   ├── Django Channels (WebSocket)
│   ├── Django Extensions
│   └── DRF Spectacular (API Docs)
│
├── ASGI/WSGI Servers
│   ├── Daphne (ASGI for WebSocket)
│   └── Gunicorn (WSGI for HTTP)
│
├── Database
│   ├── psycopg2 (PostgreSQL driver)
│   └── django-redis (Redis cache backend)
│
├── Search
│   ├── elasticsearch (Python client)
│   ├── django-elasticsearch-dsl
│   └── django-elasticsearch-dsl-drf
│
├── Task Queue
│   ├── Celery 5.3 (Task queue)
│   ├── celery-beat (Scheduler)
│   └── redis (Broker & Result backend)
│
├── Document Generation
│   ├── reportlab (PDF)
│   ├── python-barcode (Barcodes)
│   └── qrcode (QR codes)
│
├── Data Processing
│   ├── pandas (Analytics)
│   └── openpyxl (Excel import/export)
│
└── Utilities
    ├── python-decouple (Config)
    ├── Pillow (Image processing)
    └── requests (HTTP client)
```

### Frontend Stack
```
Node.js 18+
├── Vue 3 (Framework)
│   ├── Composition API
│   ├── Script Setup
│   └── Reactive System
│
├── Build Tool
│   └── Vite 5 (Fast builds)
│
├── State Management
│   └── Pinia (Vuex replacement)
│
├── Routing
│   └── Vue Router 4
│
├── HTTP Client
│   └── Axios (with interceptors)
│
├── UI Framework
│   ├── Element Plus (Components)
│   └── @element-plus/icons-vue
│
├── Charts & Visualization
│   ├── ECharts 5
│   ├── vue-echarts
│   └── @toast-ui/vue-gantt
│
└── Utilities
    ├── dayjs (Date handling)
    ├── xlsx (Excel export)
    └── Native WebSocket API
```

### Infrastructure Stack (Ubuntu Native)
```
Ubuntu Server
├── PostgreSQL 15
│   ├── Port: 5432
│   └── Systemd Service: postgresql
│
├── Redis 7
│   ├── Port: 6379
│   └── Systemd Service: redis-server
│
├── Django Backend
│   ├── Gunicorn (WSGI)
│   ├── Port: 8000
│   └── Systemd Service: erp-backend
│
├── Celery Worker
│   ├── Concurrency: auto
│   └── Systemd Service: erp-celery
│
├── Celery Beat
│   ├── Scheduler daemon
│   └── Systemd Service: erp-celery-beat
│
└── Nginx
    ├── Port: 80, 443
    ├── Serves: Frontend static files
    ├── Proxy: Backend API
    └── Systemd Service: nginx
```

---

## 🚀 Deployment Architectures

### Option 1: Single Server (Development/Small)
```
Single Ubuntu Server
├── All services on one machine
├── Requirements: 4GB RAM, 2 CPU, 40GB disk
└── Suitable for: <100 users, dev/test
```

### Option 2: Multi-Server (Production)
```
App Server (Backend)
├── Django + Daphne + Gunicorn
├── Celery Workers (3+)
└── Celery Beat

DB Server
├── PostgreSQL (Primary)
└── PostgreSQL (Replica for reads)

Cache Server
├── Redis (Primary)
└── Redis (Replica)

Search Server
├── Elasticsearch Cluster (3 nodes)
└── Coordinating + Data nodes

Web Server
├── Nginx (Load Balancer)
└── Frontend Static Files
```

### Option 3: Kubernetes (Enterprise)
```
K8s Cluster
├── Deployments
│   ├── backend (replicas: 3+)
│   ├── celery-worker (replicas: 5+)
│   ├── celery-beat (replicas: 1)
│   └── frontend (replicas: 2+)
│
├── StatefulSets
│   ├── postgresql (replicas: 3)
│   ├── redis (replicas: 3)
│   └── elasticsearch (replicas: 3)
│
├── Services
│   ├── backend-service (ClusterIP)
│   ├── db-service (ClusterIP)
│   └── nginx-ingress (LoadBalancer)
│
├── Ingress
│   └── TLS termination, routing
│
├── Persistent Volumes
│   ├── db-pv (50GB)
│   └── es-pv (100GB)
│
└── ConfigMaps & Secrets
    ├── app-config
    └── db-credentials
```

---

## 📈 Scalability Considerations

### Horizontal Scaling
- **Backend:** Stateless, scale to N instances behind load balancer
- **Celery Workers:** Add workers for increased task throughput
- **Elasticsearch:** Add nodes for more data & queries
- **Redis:** Redis Cluster for high availability
- **PostgreSQL:** Read replicas for query load distribution

### Performance Optimization
- **Database:** Indexes on frequent queries, partitioning large tables
- **Cache:** Redis for expensive queries, 1-hour TTL for aggregations
- **Search:** Elasticsearch for full-text, offload from PostgreSQL
- **CDN:** Serve static assets from CDN (Cloudflare, AWS CloudFront)
- **Connection Pooling:** PgBouncer for PostgreSQL connections

---

## 🎯 Conclusion

This architecture provides:
- ✅ **Scalability** - Horizontal scaling at every layer
- ✅ **Performance** - Caching, search optimization, async processing
- ✅ **Reliability** - Health checks, retries, error handling
- ✅ **Security** - Multi-layer security, audit trails, RBAC
- ✅ **Real-time** - WebSocket for instant updates
- ✅ **Maintainability** - Modular structure, comprehensive docs
- ✅ **Extensibility** - RESTful API, pluggable Django apps

**A modern, enterprise-grade ERP architecture ready for production deployment!**

