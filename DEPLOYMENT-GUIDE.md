# Python ERP System - Complete Deployment Guide

## 🚀 Quick Start (5 Minutes)

### Prerequisites
- Docker & Docker Compose
- Node.js 18+ (for frontend development)
- 4GB RAM minimum
- 10GB disk space

### One-Command Deployment
```bash
# Clone and start everything
cd /Users/zhengshan/Documents/toolsource/python-erp

# Start all backend services (includes Elasticsearch now!)
docker-compose up -d

# Build Elasticsearch indexes (first time only)
docker exec erp_backend python manage.py search_index --rebuild

# Start frontend
cd frontend && npm install && npm run dev
```

### Access Points
- **Frontend**: http://localhost:5173
- **Backend API**: http://localhost:8000/api/
- **API Docs**: http://localhost:8000/api/docs/
- **Admin**: http://localhost:8000/admin/
- **Elasticsearch**: http://localhost:9200

### Default Credentials
- **Username**: `admin`
- **Password**: `admin123`

---

## 📦 System Components

### Docker Services (6 Total)

| Service | Container | Port | Status Check |
|---------|-----------|------|--------------|
| PostgreSQL | erp_db | 5432 | `docker exec erp_db pg_isready` |
| Redis | erp_redis | 6379 | `docker exec erp_redis redis-cli ping` |
| Elasticsearch | erp_elasticsearch | 9200, 9300 | `curl http://localhost:9200/_cluster/health` |
| Django | erp_backend | 8000 | `curl http://localhost:8000/api/docs/` |
| Celery Worker | erp_celery | - | `docker logs erp_celery` |
| Celery Beat | erp_celery_beat | - | `docker logs erp_celery_beat` |

---

## 🔧 Environment Configuration

### Backend (.env)
Create `backend/.env`:
```env
# Database
DATABASE_URL=postgresql://erp_user:erp_password@db:5432/erp_db

# Django
SECRET_KEY=your-secret-key-here
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# Redis
REDIS_HOST=redis
CELERY_BROKER_URL=redis://redis:6379/0

# Elasticsearch
ELASTICSEARCH_HOST=elasticsearch:9200

# Email (optional)
EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend
DEFAULT_FROM_EMAIL=noreply@erp.local
```

---

## 📊 Database Setup

### Initial Migration
```bash
# Run migrations
docker exec erp_backend python manage.py migrate

# Create superuser (if not exists)
docker exec -it erp_backend python manage.py createsuperuser

# Load sample data (optional)
docker exec erp_backend python manage.py loaddata sample_data.json
```

### Backup & Restore
```bash
# Backup database
docker exec erp_db pg_dump -U erp_user erp_db > backup_$(date +%Y%m%d).sql

# Restore database
cat backup_20251124.sql | docker exec -i erp_db psql -U erp_user erp_db
```

---

## 🔍 Elasticsearch Setup

### Index Management

**Build Indexes (First Time):**
```bash
docker exec erp_backend python manage.py search_index --rebuild
```

**Update Indexes:**
```bash
docker exec erp_backend python manage.py search_index --populate
```

**Delete Indexes:**
```bash
docker exec erp_backend python manage.py search_index --delete
```

### Check Index Status
```bash
# List all indexes
curl http://localhost:9200/_cat/indices?v

# Check specific index
curl http://localhost:9200/items/_count

# View index mapping
curl http://localhost:9200/items/_mapping?pretty
```

### Rebuild Schedule (Optional)
Add to Celery Beat schedule for nightly rebuild:
```python
# config/celery.py
app.conf.beat_schedule = {
    'rebuild-search-indexes': {
        'task': 'apps.core.tasks.rebuild_search_indexes',
        'schedule': crontab(hour=3, minute=0),
    },
}
```

---

## 🌐 WebSocket Configuration

### Connection Test
```javascript
// Browser console
const ws = new WebSocket('ws://localhost:8000/ws/notifications/')
ws.onopen = () => console.log('✅ Connected')
ws.onmessage = (e) => console.log('📨 Message:', JSON.parse(e.data))
ws.onerror = (e) => console.error('❌ Error:', e)
```

### Production WebSocket
For production with Nginx:
```nginx
# nginx.conf
location /ws/ {
    proxy_pass http://backend:8000;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_read_timeout 86400;
}
```

---

## 🎨 Frontend Setup

### Development
```bash
cd frontend

# Install dependencies
npm install

# Start dev server
npm run dev

# Access at http://localhost:5173
```

### Production Build
```bash
cd frontend

# Build for production
npm run build

# Output in frontend/dist/

# Serve with Nginx (already configured in docker-compose)
```

---

## 🔐 Security Checklist

### Production Deployment

- [ ] Change `SECRET_KEY` in `.env`
- [ ] Set `DEBUG=False`
- [ ] Update `ALLOWED_HOSTS`
- [ ] Configure proper CORS origins
- [ ] Enable HTTPS with SSL certificates
- [ ] Set strong database password
- [ ] Configure firewall rules
- [ ] Enable Elasticsearch security (X-Pack)
- [ ] Set up Redis password
- [ ] Configure rate limiting
- [ ] Enable Django security middleware
- [ ] Set secure cookies (SESSION_COOKIE_SECURE)
- [ ] Configure CSP headers

### .env Template (Production)
```env
SECRET_KEY=<generate-with-django-secret-key-generator>
DEBUG=False
ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com
CORS_ALLOWED_ORIGINS=https://yourdomain.com

DATABASE_URL=postgresql://erp_user:<strong-password>@db:5432/erp_db
REDIS_PASSWORD=<redis-password>
ELASTICSEARCH_PASSWORD=<es-password>

# SSL
SECURE_SSL_REDIRECT=True
SESSION_COOKIE_SECURE=True
CSRF_COOKIE_SECURE=True
```

---

## 📊 Monitoring & Logs

### View Logs
```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f backend
docker-compose logs -f elasticsearch
docker-compose logs -f celery

# Last 100 lines
docker-compose logs --tail=100 backend
```

### Health Checks
```bash
# Check all services
docker-compose ps

# Backend health
curl http://localhost:8000/api/docs/

# Elasticsearch health
curl http://localhost:9200/_cluster/health?pretty

# Redis health
docker exec erp_redis redis-cli ping

# Database health
docker exec erp_db pg_isready -U erp_user
```

### Performance Monitoring
```bash
# Django queries (in development)
docker exec erp_backend python manage.py debugsqlshell

# Elasticsearch stats
curl http://localhost:9200/_stats?pretty

# Redis info
docker exec erp_redis redis-cli info stats
```

---

## 🔄 Maintenance Tasks

### Daily
- [ ] Check service health: `docker-compose ps`
- [ ] Monitor disk space: `df -h`
- [ ] Review error logs: `docker-compose logs --tail=50 backend`

### Weekly
- [ ] Backup database
- [ ] Update search indexes: `docker exec erp_backend python manage.py search_index --populate`
- [ ] Check slow queries
- [ ] Review Celery task logs

### Monthly
- [ ] Update dependencies (security patches)
- [ ] Rebuild Docker images
- [ ] Vacuum database: `docker exec erp_db vacuumdb -U erp_user erp_db`
- [ ] Clear old logs
- [ ] Review and optimize indexes

---

## 🚨 Troubleshooting

### Backend Won't Start
```bash
# Check logs
docker-compose logs backend

# Common fixes:
docker-compose down
docker-compose build --no-cache backend
docker-compose up -d backend
```

### Elasticsearch Out of Memory
```bash
# Increase heap size in docker-compose.yml
environment:
  - "ES_JAVA_OPTS=-Xms1g -Xmx1g"  # Increase from 512m

# Or reduce memory usage
docker-compose restart elasticsearch
```

### WebSocket Not Connecting
```bash
# Check if Channels is running
docker logs erp_backend | grep -i "daphne"

# Check Redis connection
docker exec erp_redis redis-cli ping

# Verify ASGI app
docker exec erp_backend python -c "from config.asgi import application; print('OK')"
```

### Search Not Working
```bash
# Check Elasticsearch is running
curl http://localhost:9200/_cluster/health

# Rebuild indexes
docker exec erp_backend python manage.py search_index --rebuild

# Check index exists
curl http://localhost:9200/_cat/indices
```

### Database Connection Errors
```bash
# Check PostgreSQL is running
docker exec erp_db pg_isready

# Check credentials
docker exec erp_backend python manage.py dbshell

# Restart database
docker-compose restart db
```

---

## 📈 Scaling & Performance

### Horizontal Scaling

**Add More Workers:**
```yaml
# docker-compose.yml
celery_2:
  <<: *celery
  container_name: erp_celery_2

celery_3:
  <<: *celery
  container_name: erp_celery_3
```

**Add Backend Replicas:**
```bash
docker-compose up -d --scale backend=3
```

### Database Optimization
```sql
-- Add indexes for frequently queried fields
CREATE INDEX idx_item_sku ON items(sku);
CREATE INDEX idx_project_status ON projects(status);
CREATE INDEX idx_created_at ON audit_log(created_at DESC);

-- Analyze tables
ANALYZE;
```

### Redis Optimization
```bash
# Increase max memory in docker-compose.yml
command: redis-server --maxmemory 512mb --maxmemory-policy allkeys-lru
```

---

## 🎯 Production Checklist

### Before Go-Live

**Infrastructure:**
- [ ] All services running and healthy
- [ ] Database migrations applied
- [ ] Search indexes built
- [ ] SSL certificates installed
- [ ] Backups configured
- [ ] Monitoring tools set up
- [ ] Log aggregation configured

**Security:**
- [ ] All default passwords changed
- [ ] DEBUG=False
- [ ] Security headers configured
- [ ] CORS properly configured
- [ ] Rate limiting enabled
- [ ] Firewall rules set

**Testing:**
- [ ] All critical workflows tested
- [ ] WebSocket connections working
- [ ] Search functionality verified
- [ ] Celery tasks running
- [ ] Email notifications working
- [ ] PDF generation tested
- [ ] Multi-currency calculations verified

**Documentation:**
- [ ] User manuals created
- [ ] API documentation reviewed
- [ ] Admin procedures documented
- [ ] Disaster recovery plan
- [ ] Escalation procedures

---

## 📞 Support & Resources

### Documentation
- Quick Start: `QUICK-START-GUIDE.md`
- Phase 1 Summary: `README.md`
- Phase 2A Summary: `PHASE2-FINAL-SUMMARY.md`
- Phase 2B Summary: `PHASE2B-COMPLETION-SUMMARY.md`
- API Docs: http://localhost:8000/api/docs/

### Useful Commands Cheat Sheet
```bash
# Start system
docker-compose up -d

# Stop system
docker-compose down

# Restart service
docker-compose restart backend

# View logs
docker-compose logs -f backend

# Run migrations
docker exec erp_backend python manage.py migrate

# Rebuild search
docker exec erp_backend python manage.py search_index --rebuild

# Django shell
docker exec -it erp_backend python manage.py shell

# Database backup
docker exec erp_db pg_dump -U erp_user erp_db > backup.sql

# Check services
docker-compose ps
```

---

## 🎊 Success!

Your Python ERP system is now fully deployed with:
- ✅ Real-time notifications (WebSocket)
- ✅ Advanced search (Elasticsearch)
- ✅ Analytics dashboards
- ✅ Automated workflows
- ✅ Multi-currency support
- ✅ Complete audit trail
- ✅ PWA support
- ✅ And 30+ more enterprise features!

**System Status: 🚀 Production Ready**

For questions or issues, refer to the troubleshooting section above or check the API documentation.

**Happy ERP-ing! 🎉**

