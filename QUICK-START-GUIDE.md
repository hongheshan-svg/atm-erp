# 🚀 Python ERP System - Quick Start Guide

## ⚡ **5-Minute Setup**

### 1. Start the System
```bash
cd /Users/zhengshan/Documents/toolsource/python-erp

# Start backend services (Database, Redis, Django, Celery)
docker-compose up -d

# Start frontend (in a new terminal)
cd frontend
npm run dev
```

### 2. Access the System
- **Frontend:** http://localhost:5173
- **Backend API:** http://localhost:8000/api/
- **API Documentation:** http://localhost:8000/api/docs/

### 3. Login
- **Username:** `admin`
- **Password:** `admin123`

---

## 🎯 **Key Features to Try**

### 📊 **1. Executive Dashboard**
**Path:** Dashboard (first page after login)

**What You'll See:**
- Total Revenue, Active Projects, Inventory Value, Cash Position
- Cash flow forecast chart (30 days)
- Project completion pie chart
- Recent system alerts

**Try:** Refresh to see real-time KPI updates

---

### 📈 **2. Project Analytics**
**Path:** Analytics → Project Analytics

**Features:**
- Project status distribution chart
- Profit margin analysis
- Cost structure breakdown (material/labor/expense)
- Top 10 projects performance table

**Try:** Sort by profit margin to see most profitable projects

---

### 📦 **3. Inventory Analytics**
**Path:** Analytics → Inventory Analytics

**Features:**
- Inventory value by warehouse
- Turnover rate calculation
- Slow-moving items list
- ABC analysis

**Try:** View 90-day slow-moving items

---

### 📋 **4. Project Gantt Chart**
**Path:** Projects → Project Gantt

**Features:**
- Visual project timeline
- Color-coded task status
- Task progress tracking
- Interactive bars

**Try:** Select an active project from dropdown

---

### 💰 **5. Multi-Currency Finance**
**Path:** Finance → Currencies

**Features:**
- Add/edit currencies
- Update exchange rates
- View rate history
- Set base currency

**Try:** Add USD, EUR, CNY with exchange rates

---

### 📄 **6. Generate PDF Invoice**
**Path:** Sales → Sales Orders → Select Order → Actions

**Features:**
- Professional PDF invoice
- Company branding
- Line items with totals
- Downloadable PDF

**Try:** Select any confirmed sales order and click "Generate Invoice"

---

### 🔍 **7. Barcode/QR Code Generation**
**Path:** Master Data → Items → Select Item → Actions

**Features:**
- Generate barcode (CODE128)
- Generate QR code (JSON data)
- Downloadable PNG images
- Ready for printing/scanning

**Try:** Select any item and click "Generate Barcode"

---

### 📦 **8. Batch Tracking**
**Path:** Inventory → Batches

**Features:**
- Create batches with expiry dates
- View expiring items (alert threshold)
- Track batch movements
- Quality status management
- FEFO (First Expiry, First Out)

**Try:** 
1. Create a batch with expiry date
2. View "Expiring Soon" (30 days)
3. Adjust batch quantity

---

### 📬 **9. RFQ System**
**Path:** Purchase → RFQs

**Features:**
- Create request for quotation
- Send to multiple suppliers
- Receive and compare quotes
- Accept best quote
- Convert to purchase order

**Try:** 
1. Create new RFQ
2. Add line items
3. Send to suppliers
4. (Suppliers respond)
5. Compare quotes
6. Accept and convert to PO

---

### 🔔 **10. Notification Center**
**Path:** Bell Icon (top right)

**Features:**
- System notifications
- Unread count badge
- Mark as read/unread
- Filter by type (All/Unread/Read)
- Time-based display

**Try:** Check for system alerts (stock levels, overdue payments)

---

### 🔍 **11. Audit Log Viewer**
**Path:** System → Audit Log

**Features:**
- Complete system change history
- Filter by user, action, date
- View detailed changes (JSON)
- IP address tracking
- Action badges (CREATE, UPDATE, DELETE)

**Try:**
1. Filter by today's date
2. Find your login action
3. View change details

---

## 🛠️ **Common Tasks**

### Create a New Project
1. Projects → Create Project
2. Fill in: Name, Customer, Manager, Dates, Budget
3. Add project members
4. Add BOM (Bill of Materials)
5. Create tasks (WBS structure)
6. View in Gantt chart

### Purchase Flow
1. **Purchase Request** → Create PR with items
2. **Convert to PO** → Select supplier
3. **Goods Receipt** → Receive items
4. **Stock Move** → Auto-created (items in warehouse)

### Sales Flow
1. **Quotation** → Create and send to customer
2. **Convert to SO** → Customer accepts
3. **Delivery Order** → Ship items
4. **Invoice** → Generate PDF
5. **AR** → Auto-created

### Inventory Management
1. **Stock Query** → Check availability
2. **Stock Adjustment** → Physical count
3. **Stock Transfer** → Between warehouses
4. **Batch Tracking** → Expiry management

---

## 📱 **Mobile Access (PWA)**

### Install as App
**On Mobile (iOS/Safari):**
1. Open http://localhost:5173 in Safari
2. Tap Share button
3. Tap "Add to Home Screen"
4. App icon appears on home screen

**On Mobile (Android/Chrome):**
1. Open http://localhost:5173 in Chrome
2. Tap "..." menu
3. Tap "Install App" or "Add to Home Screen"

**On Desktop (Chrome):**
1. Open http://localhost:5173
2. Click install icon in address bar (+ icon)
3. App installs like native app

### Offline Mode
- PWA caches pages for offline access
- Service worker handles network failures
- Works without internet connection

---

## 🔧 **System Management**

### Check Service Status
```bash
docker-compose ps
```

**Expected Services:**
- ✅ erp_backend (healthy)
- ✅ erp_db (healthy)
- ✅ erp_redis (healthy)
- ✅ erp_celery (up)
- ✅ erp_celery_beat (up)

### View Logs
```bash
# Backend logs
docker-compose logs -f backend

# Celery worker logs
docker-compose logs -f celery

# All logs
docker-compose logs -f
```

### Restart Services
```bash
# Restart all
docker-compose restart

# Restart specific service
docker-compose restart backend
```

### Stop System
```bash
# Stop all containers
docker-compose down

# Stop and remove volumes (WARNING: deletes data)
docker-compose down -v
```

---

## 📊 **API Exploration**

### Swagger UI
Visit: http://localhost:8000/api/docs/

**Features:**
- Interactive API documentation
- Try API calls directly
- View request/response schemas
- Test authentication

### Example API Calls

**Get Dashboard KPIs:**
```bash
curl -H "Authorization: Bearer YOUR_TOKEN" \
  http://localhost:8000/api/analytics/analytics/dashboard/
```

**Create Item:**
```bash
curl -X POST http://localhost:8000/api/masterdata/items/ \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"sku":"ITEM001","name":"Test Item","unit":"PCS"}'
```

---

## 🎓 **Learning Path**

### Day 1: Basics
1. ✅ Login and explore dashboard
2. ✅ Create master data (items, customers, suppliers)
3. ✅ Check inventory

### Day 2: Operations
1. ✅ Create project with tasks
2. ✅ Generate purchase request
3. ✅ Create sales order
4. ✅ Process goods receipt

### Day 3: Advanced
1. ✅ Use RFQ system
2. ✅ Setup multi-currency
3. ✅ Generate reports
4. ✅ Track batches

### Day 4: Management
1. ✅ View project Gantt chart
2. ✅ Analyze project profitability
3. ✅ Check inventory analytics
4. ✅ Review audit logs

### Day 5: Automation
1. ✅ Configure notifications
2. ✅ Set up scheduled tasks
3. ✅ Generate barcodes
4. ✅ Install PWA

---

## 🆘 **Troubleshooting**

### Frontend Not Loading
```bash
cd frontend
npm install
npm run dev
```

### Backend Error
```bash
docker-compose restart backend
docker-compose logs backend
```

### Database Connection Error
```bash
docker-compose restart db
# Check database is healthy
docker-compose ps
```

### Port Already in Use
```bash
# Stop conflicting services
# Change ports in docker-compose.yml if needed
```

---

## 📚 **Documentation**

- **Phase 1 Plan:** `README.md`
- **Phase 2 Plan:** `PHASE2-PLAN.md`
- **Implementation Summary:** `PHASE2-IMPLEMENTATION-SUMMARY.md`
- **Final Summary:** `PHASE2-FINAL-SUMMARY.md`
- **This Guide:** `QUICK-START-GUIDE.md`
- **API Docs:** http://localhost:8000/api/docs/

---

## 🌟 **Key Shortcuts**

| Page | Shortcut |
|------|----------|
| Dashboard | Click logo (top left) |
| Create Item | Master Data → Items → + New |
| Check Stock | Inventory → Stocks |
| New Project | Projects → + Create |
| Notifications | Bell icon (top right) |
| Audit Log | System menu |
| Logout | User avatar (top right) |

---

## ✨ **Pro Tips**

1. **Use Search Everywhere** - Most pages have search boxes
2. **Export to Excel** - Many tables have export buttons
3. **Check Notifications Daily** - System alerts are important
4. **Review Audit Log** - Track all changes
5. **Mobile First** - Install PWA for on-the-go access
6. **Bookmark API Docs** - Useful for integration
7. **Schedule Reports** - Use Celery for automation
8. **Monitor Dashboard** - Real-time business pulse

---

## 🎉 **You're Ready!**

The system is fully operational with:
- ✅ 16 major features
- ✅ 35+ API endpoints
- ✅ 22 frontend pages
- ✅ Real-time analytics
- ✅ Automated workflows
- ✅ Complete traceability

**Start exploring and enjoy the power of a modern ERP system! 🚀**

---

**Need Help?** Check the documentation or API docs at http://localhost:8000/api/docs/

