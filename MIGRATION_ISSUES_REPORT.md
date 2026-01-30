# Django Migration Issues Report
Generated: 2026-01-30

## Executive Summary

**Status**: ⚠️ **CRITICAL ISSUES FOUND**

All migrations are currently applied (`showmigrations` shows all [X]), but `makemigrations --dry-run` detected **extensive pending migrations** across multiple apps. This indicates that model definitions in code do not match the database schema.

---

## 1. Migration Status Overview

### All Migrations Applied ✅
All existing migrations are applied successfully. No unapplied migrations found.

### Pending Migrations Detected ⚠️
The `makemigrations --dry-run` command detected pending migrations for the following apps:
- `masterdata` - 1 pending migration
- `workflow` - 1 pending migration  
- `core` - 1 pending migration
- `finance` - 1 pending migration
- `inventory` - 2 pending migrations
- `oa` - 1 pending migration
- `production` - 1 pending migration
- `projects` - 1 pending migration
- `purchase` - 1 pending migration
- `sales` - 1 pending migration

**Total**: 11 pending migrations detected

---

## 2. Detailed Issues by App

### 2.1 masterdata App

**Issue**: Missing migration for `Supplier.settlement_method` field

**Details**:
- **Model Location**: `backend/apps/masterdata/models.py` (line 407-412)
- **Field Definition**: 
  ```python
  settlement_method = models.CharField(
      max_length=20,
      choices=SETTLEMENT_METHOD_CHOICES,
      blank=True,
      verbose_name='结款方式'
  )
  ```
- **Latest Migration**: `0005_automation_bom_fields.py`
- **Status**: Field exists in model but NOT in database

**Impact**: 
- Database schema missing this field
- Any code accessing `supplier.settlement_method` will fail
- Admin interface may show errors

**Required Action**: Create migration `0006_supplier_settlement_method.py`

---

### 2.2 workflow App (core/workflow)

**Issue**: `WorkflowDefinition.business_type` field choices are outdated

**Details**:
- **Model Location**: `backend/apps/core/workflow/models.py` (line 13-35)
- **Current Model Choices**: Includes 14 business types:
  - PURCHASE_REQUEST, PURCHASE_ORDER
  - QUOTATION, SALES_ORDER, SALES_CONTRACT, DELIVERY_ORDER
  - EXPENSE, PAYMENT
  - PROJECT, ECN
  - STOCK_ADJUSTMENT
  - LEAVE_REQUEST, OVERTIME_REQUEST, VEHICLE_REQUEST, ASSET_BORROW

- **Latest Migration**: `0003_rename_workflow_in_busines_a1b2c3_idx_workflow_in_busines_f6512a_idx_and_more.py` (line 31)
- **Migration Choices**: Only includes 7 business types:
  - PURCHASE_REQUEST, EXPENSE, SALES_ORDER, PROJECT, STOCK_ADJUSTMENT, DELIVERY_ORDER, ECN

**Impact**:
- Database constraint allows only old choices
- New business types (PURCHASE_ORDER, QUOTATION, SALES_CONTRACT, PAYMENT, LEAVE_REQUEST, OVERTIME_REQUEST, VEHICLE_REQUEST, ASSET_BORROW) cannot be saved
- Data integrity issues

**Required Action**: Create migration `0004_alter_workflowdefinition_business_type.py` to update choices

---

### 2.3 core App

#### Issue 2.3.1: Missing `Meeting.meeting_type` field

**Details**:
- **Model Location**: `backend/apps/core/schedule.py` (line 136)
- **Field Definition**:
  ```python
  meeting_type = models.CharField(
      max_length=20, 
      choices=TYPE_CHOICES, 
      default='REGULAR', 
      verbose_name='会议类型'
  )
  ```
- **Latest Migration**: `0006_announcement_conversation_customfielddefinition_and_more.py`
- **Status**: Field exists in model but NOT in migration 0006 (Meeting model created without this field)

**Impact**:
- Database schema missing this field
- Code accessing `meeting.meeting_type` will fail
- Serializers reference this field (line 314, 336 in schedule.py)

**Required Action**: Add field to Meeting model via migration

#### Issue 2.3.2: Missing migrations for Mobile models

**Details**:
- **Model Location**: `backend/apps/core/mobile_api.py`
- **Models Missing Migrations**:
  1. `MobileTimeEntry` (line 26)
  2. `MobilePhoto` (line 86)
  3. `MobileScanRecord` (line 129)
  4. `MobileApproval` (line 170)
  5. `MobileNotification` (line 224)

- **Latest Migration**: `0006_announcement_conversation_customfielddefinition_and_more.py`
- **Status**: These models are imported in `core/models.py` (line 263-266) but have NO migrations

**Impact**:
- **CRITICAL**: These models don't exist in database
- Any code using these models will fail with "table does not exist" errors
- Mobile API endpoints will fail

**Required Action**: Create migration `0007_meeting_meeting_type_mobiletimeentry_and_more.py`

---

### 2.4 finance App

**Issue**: Missing migrations for new models

**Details**:
- **Pending Models** (from makemigrations output):
  1. `TaxDeclaration`
  2. `TaxType`
  3. `TaxRate`
  4. `TaxPeriod`
  5. `TaxDeclarationItem`
  6. `PaymentRequest`
  7. `TaxInvoice`

- **Latest Migration**: `0014_accountcategory_chartofaccount_fiscalperiod_and_more.py`
- **Status**: Models exist in code but NOT in database

**Impact**:
- Tax management features will fail
- Payment request functionality unavailable
- Data integrity issues

**Required Action**: Create migration `0015_taxdeclaration_taxtype_taxrate_taxperiod_and_more.py`

---

### 2.5 inventory App

**Issue**: Missing migrations for new models

**Details**:
- **Pending Models** (from makemigrations output):
  1. `DataValidationResult`
  2. `DataValidationRule`
  3. `ReconciliationItem`
  4. `ReconciliationSession`
  5. `SparePart`
  6. `SparePartAlert`
  7. `SparePartCategory`
  8. `SparePartForecast`
  9. `SparePartEquipmentRelation`
  10. `SparePartConsumption`

- **Latest Migration**: `0005_stockalertrule_stockalert_mrpplan_mrpline_and_more.py`
- **Status**: Models exist in code but NOT in database

**Impact**:
- Data validation features unavailable
- Reconciliation functionality broken
- Spare parts management unavailable
- Equipment maintenance features affected

**Required Action**: Create migrations `0006_datavalidationresult_datavalidationrule_and_more.py` and `0007_sparepartconsumption_service_order_and_more.py`

---

### 2.6 oa App

**Issue**: Missing migrations for new models

**Details**:
- **Pending Models** (from makemigrations output):
  1. `Asset`
  2. `AttendanceDevice`
  3. `SignatureDocument`
  4. `Vehicle`
  5. `WechatWorkConfig`
  6. `WechatSyncLog`
  7. `VehicleRequest`
  8. `VehicleMaintenance`
  9. `SignatureSeal`
  10. `SignatureParticipant`
  11. `SignatureLog`
  12. `OAAssetTransfer`
  13. `OAAssetCategory`
  14. `DeviceSyncLog`
  15. `AssetMaintenance`
  16. `AssetBorrow`
  17. `WechatUserMapping`
  18. `WechatCheckinRecord`
  19. `DeviceUserMapping`
  20. `DeviceAttendanceLog`

- **Latest Migration**: `0002_archive_archivetransfer_archivedestruction_and_more.py`
- **Status**: Models exist in code but NOT in database

**Impact**:
- Asset management features unavailable
- Attendance device integration broken
- Signature/document management unavailable
- Vehicle management features unavailable
- WeChat integration features unavailable

**Required Action**: Create migration `0003_asset_attendancedevice_signaturedocument_vehicle_and_more.py`

---

### 2.7 production App

**Issue**: Missing migrations for extensive new models

**Details**:
- **Pending Models** (from makemigrations output): 50+ models including:
  - `AndonCall`, `AssemblyGuide`, `AssemblyStep`, `ControlChart`
  - `ProductBatch`, `ProductionPlan`, `ProductionSchedule`
  - `ProjectRouting`, `Resource`, `SchedulingConstraint`
  - `WorkStation`, `SPCDataPoint`, `SNTraceRecord`
  - And many more...

- **Latest Migration**: `0001_automation_bom_fields.py` and `0001_initial.py`
- **Status**: Models exist in code but NOT in database

**Impact**:
- **CRITICAL**: Production management features completely unavailable
- Manufacturing execution system (MES) features broken
- Quality control features unavailable
- Scheduling and planning features unavailable

**Required Action**: Create migration `0002_andoncall_assemblyguide_assemblystep_controlchart_and_more.py`

---

### 2.8 projects App

**Issue**: Missing migrations for new models

**Details**:
- **Pending Models** (from makemigrations output): 40+ models including:
  - `Acceptance`, `AcceptanceCheckItem`
  - `EquipmentArchive`, `EquipmentConnection`
  - `ServiceDispatch`, `ServiceOrder`
  - `TechnicianProfile`, `TechnicalDocument`
  - And many more...

- **Latest Migration**: `0011_add_pr_tracking_fields.py`
- **Status**: Models exist in code but NOT in database

**Impact**:
- Service management features unavailable
- Equipment management features unavailable
- Technical documentation features unavailable
- Project cost tracking features affected

**Required Action**: Create migration `0012_acceptance_acceptancecheckitem_equipmentarchive_and_more.py`

---

### 2.9 purchase App

**Issue**: Missing migrations for new models

**Details**:
- **Pending Models** (from makemigrations output):
  1. `OutsourceInspection`
  2. `RFQCollaboration`
  3. `RFQItem`
  4. `SupplierOrderView`
  5. `SupplierQualityRecord`
  6. `SupplierProgressUpdate`
  7. `SupplierPortalUser`
  8. `SupplierNotification`
  9. `SupplierMessage`
  10. `SupplierDocument`
  11. `SupplierAccount`
  12. `RFQSupplierResponse`
  13. `RFQItemQuote`
  14. `ReconciliationCollaboration`
  15. `QualityCollaboration`
  16. `OutsourceProgress`
  17. `OutsourceClaim`
  18. `DeliveryCollaboration`
  19. `OutsourceCapability`

- **Latest Migration**: `0005_bom_integration.py`
- **Status**: Models exist in code but NOT in database

**Impact**:
- Supplier portal features unavailable
- RFQ collaboration features unavailable
- Supplier quality management unavailable
- Outsource management features unavailable

**Required Action**: Create migration `0006_outsourceinspection_rfqcollaboration_rfqitem_and_more.py`

---

### 2.10 sales App

**Issue**: Missing migrations for new models

**Details**:
- **Pending Models** (from makemigrations output): 30+ models including:
  - `CostCategory`, `ServiceContract`
  - `SMSCampaign`, `Trainee`, `TrainingCourse`
  - `WeChatCampaign`, `WeChatFollower`
  - `QuoteVersion`, `QuoteEstimation`
  - And many more...

- **Latest Migration**: `0006_campaignrecipient_salesprediction_and_more.py`
- **Status**: Models exist in code but NOT in database

**Impact**:
- Service contract management unavailable
- Training management features unavailable
- WeChat marketing features unavailable
- Quote management features unavailable
- Customer portal features unavailable

**Required Action**: Create migration `0007_costcategory_servicecontract_smscampaign_trainee_and_more.py`

---

## 3. Foreign Key Relationship Issues

### Potential Issues Detected:

1. **MobileTimeEntry** → `projects.Project` and `projects.ProjectTask`
   - If Project/ProjectTask models don't exist or have different structure, foreign keys will fail

2. **SparePartConsumption** → `projects.ServiceOrder`
   - ServiceOrder model needs to exist before SparePartConsumption migration

3. **EquipmentConnection** → Various equipment models
   - Ensure all referenced equipment models exist

4. **Many cross-app dependencies**:
   - Production models depend on projects, inventory, masterdata
   - Projects models depend on inventory, masterdata
   - Finance models depend on projects, sales, purchase

**Recommendation**: Review migration dependencies carefully. Some migrations may need to be created in specific order.

---

## 4. Summary of Critical Issues

### 🔴 CRITICAL (System Breaking)
1. **core app**: Mobile models completely missing from database
2. **production app**: 50+ production models missing - MES features broken
3. **oa app**: 20+ OA models missing - asset/attendance features broken

### 🟡 HIGH PRIORITY (Feature Breaking)
4. **masterdata**: Supplier.settlement_method field missing
5. **workflow**: Business type choices outdated - new types can't be saved
6. **core**: Meeting.meeting_type field missing
7. **finance**: Tax and payment models missing
8. **inventory**: Data validation and spare parts models missing
9. **projects**: Service and equipment models missing
10. **purchase**: Supplier portal models missing
11. **sales**: Service contract and training models missing

---

## 5. Recommended Actions

### Immediate Actions Required:

1. **Review Model Definitions**
   - Verify all models in code are intended to be in database
   - Check for models that should be abstract or removed

2. **Create Missing Migrations**
   ```bash
   docker-compose exec -T backend python manage.py makemigrations
   ```

3. **Review Migration Dependencies**
   - Check that all foreign key dependencies exist
   - Ensure migration order is correct

4. **Test Migrations**
   ```bash
   docker-compose exec -T backend python manage.py migrate --plan
   docker-compose exec -T backend python manage.py migrate --dry-run
   ```

5. **Apply Migrations** (after review)
   ```bash
   docker-compose exec -T backend python manage.py migrate
   ```

6. **Verify Database Schema**
   ```bash
   docker-compose exec -T backend python manage.py dbshell
   # Then check tables exist: \dt
   ```

### Long-term Recommendations:

1. **Add Pre-commit Hook**: Run `makemigrations --check` before commits
2. **CI/CD Integration**: Add migration check to CI pipeline
3. **Documentation**: Document model changes in changelog
4. **Code Review**: Require migration review for model changes

---

## 6. Migration Commands Reference

```bash
# Check migration status
docker-compose exec -T backend python manage.py showmigrations

# Check for pending migrations (dry-run)
docker-compose exec -T backend python manage.py makemigrations --dry-run

# Create migrations
docker-compose exec -T backend python manage.py makemigrations

# Preview migration plan
docker-compose exec -T backend python manage.py migrate --plan

# Apply migrations
docker-compose exec -T backend python manage.py migrate

# Check for migration conflicts
docker-compose exec -T backend python manage.py makemigrations --check
```

---

## 7. Files Modified/Checked

- `backend/apps/masterdata/models.py` - Supplier model
- `backend/apps/core/workflow/models.py` - WorkflowDefinition model
- `backend/apps/core/schedule.py` - Meeting model
- `backend/apps/core/mobile_api.py` - Mobile models
- `backend/apps/core/models.py` - BaseModel and imports
- All migration files in `backend/apps/*/migrations/`

---

**Report Generated**: 2026-01-30
**Next Review**: After applying migrations
