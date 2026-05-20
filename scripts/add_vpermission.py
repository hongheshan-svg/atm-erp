#!/usr/bin/env python3
"""
Add v-permission directives to Vue view action buttons.
"""
import os
import re

BASE = '/home/administrator/erp/frontend/src/views'

FILE_PERMISSION_MAP = {
    'purchase/RequestList.vue': 'purchase:request',
    'purchase/OrderList.vue': 'purchase:purchase_order',
    'purchase/GoodsReceiptList.vue': 'purchase:goods_receipt',
    'purchase/OutsourceList.vue': 'purchase:outsource_order',
    'purchase/RFQList.vue': 'purchase:rfq',
    'purchase/ComparisonList.vue': 'purchase:quotation_comparison',
    'purchase/SupplierEvaluationList.vue': 'purchase:supplier_evaluation',
    'purchase/SupplierBlacklist.vue': 'purchase:supplier_blacklist',
    'purchase/BudgetList.vue': 'purchase:request',
    'sales/QuotationList.vue': 'sales:quotation',
    'sales/OrderList.vue': 'sales:order',
    'sales/DeliveryOrderList.vue': 'sales:delivery',
    'sales/ContractList.vue': 'sales:contract',
    'sales/LeadList.vue': 'sales:quotation',
    'sales/OpportunityList.vue': 'sales:quotation',
    'sales/QuoteEstimation.vue': 'sales:quotation',
    'sales/ContractTemplates.vue': 'sales:contract',
    'sales/ServiceContractList.vue': 'sales:contract',
    'sales/ServiceRequestList.vue': 'sales:order',
    'sales/TrainingPlanList.vue': 'sales:order',
    'sales/TrainingCourseList.vue': 'sales:order',
    'sales/PreventiveMaintenanceList.vue': 'sales:order',
    'projects/ProjectList.vue': 'projects:project',
    'projects/TaskList.vue': 'projects:project',
    'projects/BOMList.vue': 'projects:project',
    'projects/ECNList.vue': 'projects:ecn',
    'projects/DrawingList.vue': 'projects:project',
    'projects/BugList.vue': 'projects:project',
    'projects/TimeLogList.vue': 'projects:project',
    'projects/MilestoneList.vue': 'projects:project',
    'projects/MemberList.vue': 'projects:project',
    'projects/AcceptanceList.vue': 'projects:project',
    'projects/AlertList.vue': 'projects:project',
    'projects/WorkOrderList.vue': 'projects:project',
    'projects/CostRecordList.vue': 'projects:project',
    'projects/LaborRateList.vue': 'projects:project',
    'projects/TechDocumentList.vue': 'projects:project',
    'projects/TechnicianList.vue': 'projects:project',
    'projects/ServiceOrder.vue': 'projects:aftersales',
    'projects/EquipmentArchiveList.vue': 'projects:project',
    'projects/InstallationTaskList.vue': 'projects:project',
    'projects/DiagnosticSessionList.vue': 'projects:project',
    'projects/DrawingVersionList.vue': 'projects:project',
    'projects/ArchiveList.vue': 'projects:project',
    'inventory/StockList.vue': 'inventory:stock',
    'inventory/StockMoveList.vue': 'inventory:stock_move',
    'inventory/StockAdjustmentList.vue': 'inventory:stock_adjustment',
    'inventory/RequisitionList.vue': 'inventory:material_requisition',
    'inventory/ReturnList.vue': 'inventory:material_return',
    'inventory/BatchList.vue': 'inventory:stock',
    'inventory/StockTransfer.vue': 'inventory:stock',
    'inventory/SparePartList.vue': 'inventory:stock',
    'inventory/MRPPlan.vue': 'inventory:stock',
    'inventory/CostAccounting.vue': 'inventory:stock',
    'finance/ARList.vue': 'finance:receivable',
    'finance/APList.vue': 'finance:payable',
    'finance/InvoiceList.vue': 'finance:invoice',
    'finance/ExpenseList.vue': 'finance:expense',
    'finance/AssetList.vue': 'finance:fixed_asset',
    'finance/CollectionPlanList.vue': 'finance:collection_plan',
    'finance/SharedExpenseList.vue': 'finance:shared_expense',
    'finance/ProjectCostList.vue': 'finance:expense',
    'finance/PurchaseReconciliation.vue': 'finance:purchase_reconciliation',
    'finance/SalesReconciliation.vue': 'finance:sales_reconciliation',
    'production/ProcessList.vue': 'production:process',
    'production/PlanList.vue': 'production:plan',
    'production/DebugRecordList.vue': 'production:debug_check_item',
    'production/QualityInspectionList.vue': 'production:inspection_item',
    'production/SerialNumberList.vue': 'production:plan',
    'production/WorkStationList.vue': 'production:process',
    'production/RoutingTemplate.vue': 'production:process',
    'production/AssemblyGuideList.vue': 'production:process',
    'production/ResourceTypeList.vue': 'production:process',
    'masterdata/ItemList.vue': 'masterdata:item',
    'masterdata/CustomerList.vue': 'masterdata:customer',
    'masterdata/SupplierList.vue': 'masterdata:supplier',
    'masterdata/WarehouseList.vue': 'masterdata:warehouse',
    'masterdata/LocationList.vue': 'masterdata:warehouse_location',
    'masterdata/CustomerContactList.vue': 'masterdata:customer',
    'masterdata/CustomerCredit.vue': 'masterdata:customer',
    'masterdata/CustomerFollowUp.vue': 'masterdata:customer',
    'oa/LeaveList.vue': 'oa:archive',
    'oa/AnnouncementList.vue': 'oa:archive',
    'oa/VehicleList.vue': 'oa:vehicle',
    'oa/VehicleRequestList.vue': 'oa:vehicle_request',
    'oa/AssetList.vue': 'oa:asset',
    'oa/Meeting.vue': 'oa:archive',
    'oa/Schedule.vue': 'oa:archive',
    'aftersales/OrderList.vue': 'projects:aftersales',
    'system/UserList.vue': 'accounts:user',
    'system/RoleList.vue': 'accounts:role',
    'system/DepartmentList.vue': 'accounts:department',
    'system/CodeRuleList.vue': 'accounts:user',
    'system/EmailTemplates.vue': 'accounts:user',
    'system/DataDictionary.vue': 'accounts:user',
    'system/CustomFields.vue': 'accounts:user',
    'system/WebhookList.vue': 'accounts:user',
    'system/Announcement.vue': 'accounts:user',
    'system/SystemConfig.vue': 'accounts:user',
    'equipment/EquipmentList.vue': 'projects:project',
    'equipment/FixtureList.vue': 'projects:project',
    'equipment/InspectionList.vue': 'projects:project',
}

CREATE_CLICKS = [
    'handleAdd', 'handleCreate', 'openCreateDialog', 'showCreateDialog',
    'openAddDialog', 'addNew', 'handleAddTemplate', 'handleAddClause',
    'handleAddConfig', 'createReconciliation', 'addItem',
]
EDIT_CLICKS = [
    'handleEdit', 'handleEditTemplate', 'handleEditClause', 'handleEditConfig',
    'openEditDialog',
]
DELETE_CLICKS = [
    'handleDelete', 'handleRemove', 'handleDeleteTemplate', 'handleDeleteClause',
    'batchDelete', 'handleBatchDelete',
]


def process_file(filepath, perm_code):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    if 'v-permission' in content:
        return 0

    original = content
    changes = 0
    create_perm = "'" + perm_code + ":create'"
    edit_perm = "'" + perm_code + ":edit'"
    delete_perm = "'" + perm_code + ":delete'"

    # Process line by line for better control
    lines = content.split('\n')
    new_lines = []
    for line in lines:
        new_line = line

        # Skip lines that already have v-permission
        if 'v-permission' in line:
            new_lines.append(new_line)
            continue

        # Check for el-button with create clicks
        if '<el-button' in line:
            for click in CREATE_CLICKS:
                if '@click="' + click in line:
                    # Insert v-permission before @click
                    new_line = new_line.replace(
                        '@click="' + click,
                        'v-permission="' + create_perm + '" @click="' + click
                    )
                    changes += 1
                    break

            if changes == 0 or new_line == line:
                for click in EDIT_CLICKS:
                    pat = '@click="' + click + '('
                    if pat in line:
                        new_line = new_line.replace(
                            pat,
                            'v-permission="' + edit_perm + '" ' + pat
                        )
                        changes += 1
                        break

            if new_line == line:
                for click in DELETE_CLICKS:
                    pat = '@click="' + click
                    if pat in line:
                        new_line = new_line.replace(
                            pat,
                            'v-permission="' + delete_perm + '" ' + pat
                        )
                        changes += 1
                        break

        # Check for div toolbar with canDelete
        if '<div' in line and 'v-if="canDelete' in line and 'v-permission' not in line:
            new_line = new_line.replace(
                'v-if="canDelete',
                'v-permission="' + delete_perm + '" v-if="canDelete'
            )
            changes += 1

        # Check for selection column with canDelete
        if '<el-table-column' in line and 'v-if="canDelete"' in line and 'v-permission' not in line:
            new_line = new_line.replace(
                'v-if="canDelete"',
                'v-permission="' + delete_perm + '" v-if="canDelete"'
            )
            changes += 1

        new_lines.append(new_line)

    content = '\n'.join(new_lines)

    if content != original:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        return changes
    return 0


def main():
    total_files = 0
    total_changes = 0

    for rel_path, perm_code in sorted(FILE_PERMISSION_MAP.items()):
        filepath = os.path.join(BASE, rel_path)
        if not os.path.exists(filepath):
            print(f'  SKIP (not found): {rel_path}')
            continue

        ch = process_file(filepath, perm_code)
        if ch > 0:
            total_files += 1
            total_changes += ch
            print(f'  OK ({ch}): {rel_path} -> {perm_code}')
        else:
            print(f'  SKIP (0 matches): {rel_path}')

    print(f'\n=== Added {total_changes} v-permission directives in {total_files} files ===')


if __name__ == '__main__':
    main()
