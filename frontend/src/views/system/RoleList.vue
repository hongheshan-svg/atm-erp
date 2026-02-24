<template>
  <div class="role-list">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>角色管理</span>
          <el-button type="primary" @click="handleAdd">新增角色</el-button>
        </div>
      </template>

      <!-- 批量操作工具栏 -->
      <div class="table-toolbar" v-if="canDelete && selectedRows.length > 0">
        <span>已选择 {{ selectedRows.length }} 项</span>
        <el-button type="danger" size="small" @click="batchDelete" :loading="deleteLoading">批量删除</el-button>
      </div>

      <el-table :data="roles" v-loading="loading" stripe border @selection-change="handleSelectionChange">
        <el-table-column v-if="canDelete" type="selection" width="55" fixed />
        <el-table-column prop="id" label="编号" width="80" />
        <el-table-column prop="name" label="角色名称" width="150" />
        <el-table-column prop="code" label="角色编码" width="150" />
        <el-table-column prop="description" label="描述" />
        <el-table-column label="权限状态" width="180">
          <template #default="{ row }">
            <el-tag :type="row.permissions?.menu_ids?.length ? 'success' : 'warning'" size="small" style="margin-right: 5px;">
              菜单: {{ row.permissions?.menu_ids?.length || 0 }}项
            </el-tag>
            <el-tag type="info" size="small">
              {{ getDataScopeLabel(row.data_scope) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="handleEdit(row)">编辑</el-button>
            <el-button size="small" type="primary" @click="handlePermission(row)">权限配置</el-button>
            <el-button v-if="canDelete" size="small" type="danger" @click="deleteRow(row)" :loading="deleteLoading">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 编辑角色对话框 -->
    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="600px">
      <el-form :model="form" :rules="rules" ref="formRef" label-width="120px">
        <el-form-item label="角色名称" prop="name">
          <el-input v-model="form.name" placeholder="请输入角色名称" />
        </el-form-item>
        <el-form-item label="角色编码">
          <el-input v-model="form.code" placeholder="留空则自动生成（如：ADMIN, SALES）" :disabled="isEdit">
            <template #append v-if="!isEdit">
              <el-tooltip content="留空将自动生成编码，也可手动输入便于程序识别的英文编码" placement="top">
                <el-icon><QuestionFilled /></el-icon>
              </el-tooltip>
            </template>
          </el-input>
          <div class="el-form-item__extra" v-if="!isEdit">
            💡 建议使用英文大写，如：ADMIN、SALES_MANAGER、FINANCE 等
          </div>
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="form.description" type="textarea" placeholder="请输入描述" />
        </el-form-item>
        <el-form-item label="数据范围">
          <el-select v-model="form.data_scope" placeholder="选择数据范围" style="width: 100%;">
            <el-option label="全部数据" value="ALL" />
            <el-option label="部门数据" value="DEPARTMENT" />
            <el-option label="仅本人" value="SELF" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSubmit" :loading="saving">确定</el-button>
      </template>
    </el-dialog>

    <!-- 权限配置对话框 -->
    <el-dialog v-model="permDialogVisible" title="权限配置" width="900px">
      <div v-if="currentRole" class="permission-config">
        <div class="role-info">
          <el-tag type="primary" size="large">{{ currentRole.name }}</el-tag>
          <span class="role-desc">{{ currentRole.description }}</span>
        </div>
        
        <!-- 预设角色模板（非标自动化行业） -->
        <el-divider content-position="left">
          <el-icon><Briefcase /></el-icon> 快速配置（非标自动化行业预设）
        </el-divider>
        <div class="preset-roles">
          <el-button v-for="preset in presetRoles" :key="preset.code" 
            size="small" :type="preset.type || 'default'" plain
            @click="applyPreset(preset)">
            {{ preset.name }}
          </el-button>
        </div>
        
        <el-divider content-position="left">数据权限</el-divider>
        <el-form label-width="100px">
          <el-form-item label="数据范围">
            <el-radio-group v-model="permForm.data_scope">
              <el-radio-button value="ALL">
                <el-icon><Grid /></el-icon> 全部数据
              </el-radio-button>
              <el-radio-button value="DEPARTMENT">
                <el-icon><OfficeBuilding /></el-icon> 本部门数据
              </el-radio-button>
              <el-radio-button value="SELF">
                <el-icon><User /></el-icon> 仅本人数据
              </el-radio-button>
            </el-radio-group>
          </el-form-item>
          <el-form-item>
            <el-text type="info" size="small">
              <template v-if="permForm.data_scope === 'ALL'">👑 可查看系统中所有数据（适用于：总经理、财务经理）</template>
              <template v-else-if="permForm.data_scope === 'DEPARTMENT'">🏢 仅可查看本部门及下级部门的数据（适用于：部门主管、项目经理）</template>
              <template v-else>👤 仅可查看自己创建或负责的数据（适用于：普通员工）</template>
            </el-text>
          </el-form-item>
        </el-form>
        
        <el-divider content-position="left">菜单权限（按业务流程分组）</el-divider>
        
        <div class="menu-tree-header">
          <el-checkbox v-model="checkAll" :indeterminate="isIndeterminate" @change="handleCheckAll">
            全选
          </el-checkbox>
          <el-button-group style="margin-left: 20px;">
            <el-button size="small" @click="expandAll(true)">展开全部</el-button>
            <el-button size="small" @click="expandAll(false)">收起全部</el-button>
          </el-button-group>
          <el-text type="info" size="small" style="margin-left: 15px;">
            勾选的菜单将在侧边栏中显示
          </el-text>
        </div>
        
        <el-tree
          ref="menuTreeRef"
          :data="industryMenuTree"
          show-checkbox
          node-key="id"
          :default-checked-keys="checkedMenuIds"
          :default-expand-all="false"
          :props="{ label: 'label', children: 'children' }"
          @check="handleMenuCheck"
          class="menu-tree"
        >
          <template #default="{ node, data }">
            <span class="custom-tree-node">
              <span>{{ node.label }}</span>
              <el-tag v-if="data.tag" :type="data.tagType || 'info'" size="small" style="margin-left: 8px;">
                {{ data.tag }}
              </el-tag>
            </span>
          </template>
        </el-tree>
      </div>
      <template #footer>
        <el-button @click="permDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="savePermissions" :loading="savingPerm">保存权限</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, computed, nextTick } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { QuestionFilled, Briefcase, Grid, OfficeBuilding, User } from '@element-plus/icons-vue'
import request from '@/utils/request'
import { useBatchDelete } from '@/composables/useBatchDelete'
import { usePermission } from '@/composables/usePermission'

// 权限检查
const { canDelete } = usePermission()

// 批量删除功能
const { selectedRows, loading: deleteLoading, handleSelectionChange, batchDelete, deleteRow } = useBatchDelete(
  '/accounts/roles/',
  { onSuccess: () => loadRoles(), confirmTitle: '删除角色', confirmMessage: '确定要删除该角色吗？删除后相关用户将失去此角色权限！' }
)

const loading = ref(false)
const saving = ref(false)
const savingPerm = ref(false)
const roles = ref([])
const dialogVisible = ref(false)
const permDialogVisible = ref(false)
const dialogTitle = ref('新增角色')
const isEdit = ref(false)
const formRef = ref(null)
const menuTreeRef = ref(null)
const currentRole = ref(null)
const checkedMenuIds = ref([])
const checkAll = ref(false)
const isIndeterminate = ref(false)

const form = reactive({
  id: null,
  name: '',
  code: '',
  description: '',
  data_scope: 'DEPARTMENT'
})

const permForm = reactive({
  data_scope: 'DEPARTMENT'
})

const rules = {
  name: [{ required: true, message: '请输入角色名称', trigger: 'blur' }]
  // code 不再必填，后端会自动生成
}

// 定义系统菜单树
const menuTree = ref([
  {
    id: 'dashboard',
    label: '仪表盘',
    children: []
  },
  {
    id: 'workflow',
    label: '审批中心',
    children: [
      { id: 'workflow:tasks', label: '待办审批' },
      { id: 'workflow:my-submissions', label: '我的提交' },
      { id: 'workflow:config', label: '流程配置' }
    ]
  },
  {
    id: 'system',
    label: '系统管理',
    children: [
      { id: 'system:users', label: '用户管理' },
      { id: 'system:roles', label: '角色管理' },
      { id: 'system:departments', label: '部门管理' },
      { id: 'system:code-rules', label: '编码规则' },
      { id: 'system:notifications', label: '通知中心' },
      { id: 'system:audit-log', label: '审计日志' },
      { id: 'system:login-logs', label: '登录日志' },
      { id: 'system:webhooks', label: 'Webhook管理' },
      { id: 'system:dashboard-config', label: '仪表盘配置' },
      { id: 'system:config', label: '系统配置' },
      { id: 'system:monitor', label: '系统监控' },
      { id: 'system:backup', label: '数据备份' },
      { id: 'system:audit-analytics', label: '操作日志分析' },
      { id: 'system:data-dictionary', label: '数据字典' },
      { id: 'system:email-templates', label: '邮件模板' },
      { id: 'system:custom-fields', label: '自定义字段' },
      { id: 'system:announcements', label: '系统公告' }
    ]
  },
  {
    id: 'masterdata',
    label: '基础数据',
    children: [
      { id: 'masterdata:items', label: '物料管理' },
      { id: 'masterdata:customers', label: '客户管理' },
      { id: 'masterdata:customer-contacts', label: '客户联系人' },
      { id: 'masterdata:customer-followups', label: '客户跟进' },
      { id: 'masterdata:suppliers', label: '供应商管理' },
      { id: 'masterdata:warehouses', label: '仓库管理' },
      { id: 'masterdata:locations', label: '库位管理' },
      { id: 'masterdata:credit', label: '客户信用' }
    ]
  },
  {
    id: 'projects',
    label: '项目管理',
    children: [
      { id: 'projects:list', label: '项目列表' },
      { id: 'projects:dashboard', label: '项目仪表盘' },
      { id: 'projects:tasks', label: '任务管理' },
      { id: 'projects:members', label: '成员管理' },
      { id: 'projects:bom', label: 'BOM清单' },
      { id: 'projects:time-logs', label: '工时填报' },
      { id: 'projects:gantt', label: '甘特图' },
      { id: 'projects:bugs', label: 'Bug跟踪' },
      { id: 'projects:drawings', label: '图纸管理' },
      { id: 'projects:documents', label: '技术文档协同' },
      { id: 'projects:ecn', label: 'ECN变更' },
      { id: 'projects:archives', label: '项目归档' },
      { id: 'projects:milestones', label: '项目里程碑' },
      { id: 'projects:work-orders', label: '工单管理' },
      { id: 'projects:alerts', label: '项目预警' },
      { id: 'projects:equipment-archives', label: '设备档案' },
      { id: 'projects:acceptances', label: '验收管理' },
      { id: 'projects:batch-drawing', label: '批量图纸导入' },
      { id: 'projects:drawing-bom-link', label: '图纸-BOM关联' },
      { id: 'projects:service', label: '项目服务' },
      { id: 'projects:cost', label: '项目成本' },
      { id: 'projects:monitoring', label: '项目监控' }
    ]
  },
  {
    id: 'plm',
    label: 'PLM产品研发',
    children: [
      { id: 'plm:requirements', label: '需求管理' },
      { id: 'plm:proposals', label: '方案设计' },
      { id: 'plm:agreements', label: '技术协议' },
      { id: 'plm:model-viewer', label: '3D模型预览' },
      { id: 'plm:cad-bom', label: 'CAD BOM导入' },
      { id: 'plm:bom-compare', label: 'BOM版本对比' }
    ]
  },
  {
    id: 'purchase',
    label: '采购管理',
    children: [
      { id: 'purchase:requests', label: '采购申请' },
      { id: 'purchase:comparisons', label: '比价分析' },
      { id: 'purchase:orders', label: '采购订单' },
      { id: 'purchase:goods-receipts', label: '到货质检' },
      { id: 'purchase:outsource', label: '外协加工' },
      { id: 'purchase:evaluations', label: '供应商评价' },
      { id: 'purchase:blacklist', label: '供应商黑名单' },
      { id: 'purchase:budgets', label: '采购预算' },
      { id: 'purchase:collaboration', label: '供应链协同' },
      { id: 'purchase:portal', label: '供应商协同门户' }
    ]
  },
  {
    id: 'sales',
    label: '销售管理',
    children: [
      { id: 'sales:crm-dashboard', label: 'CRM仪表盘' },
      { id: 'sales:leads', label: '销售线索' },
      { id: 'sales:opportunities', label: '销售商机' },
      { id: 'sales:quotations', label: '销售报价' },
      { id: 'sales:quote-estimation', label: '报价估算' },
      { id: 'sales:orders', label: '销售订单' },
      { id: 'sales:contracts', label: '销售合同' },
      { id: 'sales:delivery-orders', label: '发货单' },
      { id: 'sales:quote-templates', label: '报价单模板' },
      { id: 'sales:contract-templates', label: '合同模板' },
      { id: 'sales:performance', label: '销售业绩' },
      { id: 'sales:analysis', label: '销售分析' },
      { id: 'sales:training', label: '销售培训' },
      { id: 'sales:service', label: '销售服务' },
      { id: 'sales:quote', label: '快速报价' }
    ]
  },
  {
    id: 'aftersales',
    label: '售后服务',
    children: [
      { id: 'aftersales:orders', label: '售后工单' }
    ]
  },
  {
    id: 'inventory',
    label: '库存管理',
    children: [
      { id: 'inventory:stocks', label: '库存查询' },
      { id: 'inventory:batches', label: '批次管理' },
      { id: 'inventory:moves', label: '库存流水' },
      { id: 'inventory:transfer', label: '库存调拨' },
      { id: 'inventory:adjustment', label: '库存盘点' },
      { id: 'inventory:alert', label: '库存预警' },
      { id: 'inventory:alerts', label: '库存预警配置' },
      { id: 'inventory:requisitions', label: '生产领料' },
      { id: 'inventory:returns', label: '生产退料' },
      { id: 'inventory:cost-accounting', label: '库存成本' },
      { id: 'inventory:mrp', label: 'MRP计划' },
      { id: 'inventory:spare-parts', label: '备品备件' },
      { id: 'inventory:data-accuracy', label: '库存准确性' }
    ]
  },
  {
    id: 'production',
    label: '生产管理',
    children: [
      { id: 'production:processes', label: '生产工序' },
      { id: 'production:plans', label: '生产计划' },
      { id: 'production:debug-records', label: '调试记录' },
      { id: 'production:inspections', label: '质量检验' },
      { id: 'production:serial-numbers', label: '序列号管理' },
      { id: 'production:routing', label: '工艺路线' },
      { id: 'production:assembly', label: '装配管理' },
      { id: 'production:scheduling', label: '生产排程' },
      { id: 'production:capacity', label: '产能管理' }
    ]
  },
  {
    id: 'mes',
    label: 'MES制造执行',
    children: [
      { id: 'mes:scheduling', label: 'APS排程' },
      { id: 'mes:kanban', label: '电子看板' },
      { id: 'mes:andon', label: '安灯系统' },
      { id: 'mes:data-acquisition', label: '数据采集' }
    ]
  },
  {
    id: 'equipment',
    label: '设备管理',
    children: [
      { id: 'equipment:list', label: '设备台账' },
      { id: 'equipment:fixtures', label: '工装夹具' },
      { id: 'equipment:inspection', label: '设备点检' },
      { id: 'equipment:maintenance', label: '维护日历' },
      { id: 'equipment:oee', label: 'OEE分析' }
    ]
  },
  {
    id: 'finance',
    label: '财务管理',
    children: [
      { id: 'finance:expenses', label: '费用报销' },
      { id: 'finance:shared-expenses', label: '公共费用分摊' },
      { id: 'finance:ar', label: '应收账款' },
      { id: 'finance:ap', label: '应付账款' },
      { id: 'finance:invoices', label: '发票管理' },
      { id: 'finance:project-costs', label: '项目成本核算' },
      { id: 'finance:collection', label: '回款计划' },
      { id: 'finance:assets', label: '固定资产' },
      { id: 'finance:sales-reconciliation', label: '销售对账' },
      { id: 'finance:purchase-reconciliation', label: '采购对账' }
    ]
  },
  {
    id: 'knowledge',
    label: '知识库',
    children: [
      { id: 'knowledge:articles', label: '知识文章' },
      { id: 'knowledge:issues', label: '技术问题' },
      { id: 'knowledge:components', label: '标准部件库' }
    ]
  },
  {
    id: 'oa',
    label: '协同办公',
    children: [
      { id: 'oa:schedule', label: '日程管理' },
      { id: 'oa:meeting', label: '会议管理' },
      { id: 'oa:leave', label: '请假申请' },
      { id: 'oa:announcement', label: '公告管理' },
      { id: 'oa:vehicles', label: '车辆管理' },
      { id: 'oa:vehicle-request', label: '用车申请' },
      { id: 'oa:assets', label: '资产管理' },
      { id: 'oa:im', label: '即时通讯' },
      { id: 'oa:attendance', label: '考勤管理' },
      { id: 'oa:attendance-import', label: '考勤导入' }
    ]
  },
  {
    id: 'accounts',
    label: '人事管理',
    children: [
      { id: 'accounts:attendance', label: '考勤打卡' }
    ]
  },
  {
    id: 'reports',
    label: '报表统计',
    children: [
      { id: 'reports:profitability', label: '项目利润分析' },
      { id: 'reports:aging', label: '账龄分析' },
      { id: 'reports:cash-flow', label: '现金流预测' },
      { id: 'reports:slow-moving', label: '呆滞物料分析' },
      { id: 'reports:timelog', label: '工时统计' },
      { id: 'reports:cost-analysis', label: '项目成本分析' },
      { id: 'reports:industry', label: '行业分析' }
    ]
  },
  {
    id: 'analytics',
    label: '数据分析',
    children: [
      { id: 'analytics:project', label: '项目分析' },
      { id: 'analytics:inventory', label: '库存分析' }
    ]
  }
])

// ============================================
// 非标自动化行业 - 按业务流程分组的权限树
// ============================================
const industryMenuTree = ref([
  {
    id: '_presales',
    label: '📋 售前阶段（客户→商机→报价→合同）',
    tag: '销售团队',
    tagType: 'success',
    children: [
      { id: 'dashboard', label: '工作台仪表盘' },
      { id: 'masterdata:customers', label: '客户档案' },
      { id: 'masterdata:customer-contacts', label: '客户联系人' },
      { id: 'masterdata:customer-followups', label: '客户跟进' },
      { id: 'masterdata:credit', label: '客户信用' },
      { id: 'sales:crm-dashboard', label: 'CRM仪表盘' },
      { id: 'sales:leads', label: '销售线索' },
      { id: 'sales:opportunities', label: '销售商机' },
      { id: 'sales:quotations', label: '销售报价' },
      { id: 'sales:quote-estimation', label: '报价估算' },
      { id: 'sales:quote', label: '快速报价' },
      { id: 'sales:contracts', label: '销售合同' },
      { id: 'sales:quote-templates', label: '报价单模板' },
      { id: 'sales:contract-templates', label: '合同模板' },
      { id: 'sales:performance', label: '销售业绩' },
      { id: 'sales:analysis', label: '销售分析' }
    ]
  },
  {
    id: '_design',
    label: '🔧 设计阶段（需求→方案→BOM→图纸）',
    tag: '技术团队',
    tagType: 'primary',
    children: [
      { id: 'plm:requirements', label: '需求管理' },
      { id: 'plm:proposals', label: '方案设计' },
      { id: 'plm:agreements', label: '技术协议' },
      { id: 'projects:bom', label: 'BOM清单' },
      { id: 'plm:cad-bom', label: 'CAD BOM导入' },
      { id: 'plm:bom-compare', label: 'BOM版本对比' },
      { id: 'projects:drawings', label: '图纸管理' },
      { id: 'projects:batch-drawing', label: '批量图纸导入' },
      { id: 'projects:drawing-bom-link', label: '图纸-BOM关联' },
      { id: 'plm:model-viewer', label: '3D模型预览' },
      { id: 'projects:documents', label: '技术文档协同' },
      { id: 'projects:ecn', label: 'ECN变更' },
      { id: 'knowledge:articles', label: '知识文章' },
      { id: 'knowledge:issues', label: '技术问题' },
      { id: 'knowledge:components', label: '标准部件库' }
    ]
  },
  {
    id: '_project',
    label: '📊 项目管理（计划→任务→进度→成本）',
    tag: '项目经理',
    tagType: 'warning',
    children: [
      { id: 'projects:list', label: '项目列表' },
      { id: 'projects:dashboard', label: '项目仪表盘' },
      { id: 'projects:tasks', label: '任务管理' },
      { id: 'projects:members', label: '成员管理' },
      { id: 'projects:milestones', label: '项目里程碑' },
      { id: 'projects:gantt', label: '甘特图' },
      { id: 'projects:time-logs', label: '工时填报' },
      { id: 'projects:alerts', label: '项目预警' },
      { id: 'projects:cost', label: '项目成本' },
      { id: 'projects:monitoring', label: '项目监控' },
      { id: 'projects:bugs', label: 'Bug跟踪' },
      { id: 'projects:archives', label: '项目归档' }
    ]
  },
  {
    id: '_purchase',
    label: '🛒 采购阶段（MRP→询价→比价→订单→到货）',
    tag: '采购团队',
    tagType: 'info',
    children: [
      { id: 'inventory:mrp', label: 'MRP需求计划' },
      { id: 'purchase:requests', label: '采购申请' },
      { id: 'purchase:comparisons', label: '比价分析' },
      { id: 'purchase:orders', label: '采购订单' },
      { id: 'purchase:goods-receipts', label: '到货质检' },
      { id: 'purchase:outsource', label: '外协加工' },
      { id: 'purchase:budgets', label: '采购预算' },
      { id: 'masterdata:suppliers', label: '供应商档案' },
      { id: 'purchase:evaluations', label: '供应商评价' },
      { id: 'purchase:blacklist', label: '供应商黑名单' },
      { id: 'purchase:collaboration', label: '供应链协同' },
      { id: 'purchase:portal', label: '供应商协同门户' }
    ]
  },
  {
    id: '_warehouse',
    label: '📦 仓储物流（入库→库存→出库→盘点）',
    tag: '仓库团队',
    tagType: '',
    children: [
      { id: 'inventory:stocks', label: '库存查询' },
      { id: 'inventory:batches', label: '批次管理' },
      { id: 'inventory:moves', label: '库存流水' },
      { id: 'inventory:transfer', label: '库存调拨' },
      { id: 'inventory:adjustment', label: '库存盘点' },
      { id: 'inventory:alert', label: '库存预警' },
      { id: 'inventory:alerts', label: '库存预警配置' },
      { id: 'inventory:requisitions', label: '生产领料' },
      { id: 'inventory:returns', label: '生产退料' },
      { id: 'inventory:cost-accounting', label: '库存成本' },
      { id: 'inventory:spare-parts', label: '备品备件' },
      { id: 'inventory:data-accuracy', label: '库存准确性' },
      { id: 'masterdata:items', label: '物料管理' },
      { id: 'masterdata:warehouses', label: '仓库管理' },
      { id: 'masterdata:locations', label: '库位管理' }
    ]
  },
  {
    id: '_production',
    label: '🏭 生产阶段（计划→排程→执行→质检）',
    tag: '生产团队',
    tagType: 'danger',
    children: [
      { id: 'production:plans', label: '生产计划' },
      { id: 'production:scheduling', label: '生产排程' },
      { id: 'mes:scheduling', label: 'APS排程' },
      { id: 'production:capacity', label: '产能管理' },
      { id: 'projects:work-orders', label: '工单派工' },
      { id: 'production:processes', label: '生产工序' },
      { id: 'production:routing', label: '工艺路线' },
      { id: 'production:assembly', label: '装配管理' },
      { id: 'production:debug-records', label: '调试记录' },
      { id: 'production:serial-numbers', label: '序列号管理' },
      { id: 'mes:kanban', label: '电子看板' },
      { id: 'mes:andon', label: '安灯系统' },
      { id: 'mes:data-acquisition', label: '数据采集' },
      { id: 'production:inspections', label: '质量检验' }
    ]
  },
  {
    id: '_equipment',
    label: '⚙️ 设备管理（台账→点检→维护→OEE）',
    tag: '设备团队',
    tagType: '',
    children: [
      { id: 'equipment:list', label: '设备台账' },
      { id: 'equipment:fixtures', label: '工装夹具' },
      { id: 'equipment:inspection', label: '设备点检' },
      { id: 'equipment:maintenance', label: '维护日历' },
      { id: 'equipment:oee', label: 'OEE分析' },
      { id: 'projects:equipment-archives', label: '设备档案' }
    ]
  },
  {
    id: '_delivery',
    label: '🚚 交付验收（发货→安装→调试→验收）',
    tag: '交付团队',
    tagType: 'success',
    children: [
      { id: 'sales:orders', label: '销售订单' },
      { id: 'sales:delivery-orders', label: '发货管理' },
      { id: 'projects:acceptances', label: '验收管理(FAT/SAT)' },
      { id: 'projects:service', label: '项目服务' },
      { id: 'aftersales:orders', label: '售后工单' },
      { id: 'sales:service', label: '销售服务' },
      { id: 'sales:training', label: '客户培训' }
    ]
  },
  {
    id: '_finance',
    label: '💰 财务管理（应收→应付→成本→报表）',
    tag: '财务团队',
    tagType: 'warning',
    children: [
      { id: 'finance:ar', label: '应收账款' },
      { id: 'finance:ap', label: '应付账款' },
      { id: 'finance:invoices', label: '发票管理' },
      { id: 'finance:collection', label: '回款计划' },
      { id: 'finance:sales-reconciliation', label: '销售对账' },
      { id: 'finance:purchase-reconciliation', label: '采购对账' },
      { id: 'finance:expenses', label: '费用报销' },
      { id: 'finance:shared-expenses', label: '公共费用分摊' },
      { id: 'finance:project-costs', label: '项目成本核算' },
      { id: 'finance:assets', label: '固定资产' }
    ]
  },
  {
    id: '_reports',
    label: '📈 报表分析（利润→成本→库存→趋势）',
    tag: '管理层',
    tagType: 'primary',
    children: [
      { id: 'reports:profitability', label: '项目利润分析' },
      { id: 'reports:cost-analysis', label: '项目成本分析' },
      { id: 'reports:timelog', label: '工时统计' },
      { id: 'reports:cash-flow', label: '现金流预测' },
      { id: 'reports:aging', label: '账龄分析' },
      { id: 'reports:slow-moving', label: '呆滞物料分析' },
      { id: 'reports:industry', label: '行业分析' },
      { id: 'analytics:project', label: '项目分析' },
      { id: 'analytics:inventory', label: '库存分析' }
    ]
  },
  {
    id: '_oa',
    label: '🏢 协同办公（审批→考勤→日程→会议）',
    tag: '全员',
    tagType: 'info',
    children: [
      { id: 'workflow:tasks', label: '待办审批' },
      { id: 'workflow:my-submissions', label: '我的提交' },
      { id: 'workflow:config', label: '流程配置' },
      { id: 'accounts:attendance', label: '考勤打卡' },
      { id: 'oa:attendance', label: '考勤管理' },
      { id: 'oa:attendance-import', label: '考勤导入' },
      { id: 'oa:leave', label: '请假申请' },
      { id: 'oa:schedule', label: '日程管理' },
      { id: 'oa:meeting', label: '会议管理' },
      { id: 'oa:announcement', label: '公告管理' },
      { id: 'oa:vehicles', label: '车辆管理' },
      { id: 'oa:vehicle-request', label: '用车申请' },
      { id: 'oa:assets', label: '资产管理' },
      { id: 'oa:im', label: '即时通讯' }
    ]
  },
  {
    id: '_system',
    label: '⚙️ 系统管理（用户→角色→配置→监控）',
    tag: '管理员',
    tagType: 'danger',
    children: [
      { id: 'system:users', label: '用户管理' },
      { id: 'system:roles', label: '角色管理' },
      { id: 'system:departments', label: '部门管理' },
      { id: 'system:code-rules', label: '编码规则' },
      { id: 'system:notifications', label: '通知中心' },
      { id: 'system:data-dictionary', label: '数据字典' },
      { id: 'system:custom-fields', label: '自定义字段' },
      { id: 'system:email-templates', label: '邮件模板' },
      { id: 'system:webhooks', label: 'Webhook管理' },
      { id: 'system:dashboard-config', label: '仪表盘配置' },
      { id: 'system:config', label: '系统配置' },
      { id: 'system:monitor', label: '系统监控' },
      { id: 'system:backup', label: '数据备份' },
      { id: 'system:audit-log', label: '审计日志' },
      { id: 'system:login-logs', label: '登录日志' },
      { id: 'system:audit-analytics', label: '日志分析' },
      { id: 'system:announcements', label: '系统公告' }
    ]
  }
])

// ============================================
// 非标自动化行业 - 预设角色模板
// 行业特点：项目制、团队小(50-200人)、跨部门协作频繁
// ============================================
const presetRoles = ref([
  {
    name: '总经理',
    code: 'general_manager',
    type: 'danger',
    data_scope: 'ALL',
    menu_ids: ['dashboard', 'projects', 'plm', 'sales', 'purchase', 'inventory', 'production', 'mes', 'equipment', 'finance', 'reports', 'analytics', 'oa', 'workflow', 'masterdata', 'knowledge', 'aftersales', 'accounts', 'system']
  },
  {
    name: '项目经理',
    code: 'project_manager',
    type: 'warning',
    data_scope: 'ALL',
    menu_ids: ['dashboard', 'projects', 'projects:list', 'projects:dashboard', 'projects:tasks', 'projects:members', 'projects:bom', 'projects:time-logs', 'projects:gantt', 'projects:milestones', 'projects:alerts', 'projects:equipment-archives', 'projects:acceptances', 'projects:archives', 'projects:cost', 'projects:monitoring', 'projects:work-orders', 'projects:drawings', 'projects:documents', 'projects:ecn', 'plm', 'plm:requirements', 'plm:proposals', 'plm:agreements', 'plm:model-viewer', 'plm:cad-bom', 'plm:bom-compare', 'knowledge', 'knowledge:articles', 'knowledge:issues', 'knowledge:components', 'purchase', 'purchase:requests', 'purchase:orders', 'purchase:goods-receipts', 'purchase:outsource', 'sales', 'sales:orders', 'sales:delivery-orders', 'aftersales', 'aftersales:orders', 'inventory', 'inventory:stocks', 'inventory:requisitions', 'inventory:returns', 'inventory:mrp', 'production', 'production:plans', 'production:debug-records', 'production:inspections', 'mes', 'mes:scheduling', 'mes:kanban', 'equipment', 'equipment:list', 'equipment:fixtures', 'reports', 'reports:profitability', 'reports:cost-analysis', 'reports:timelog', 'masterdata', 'masterdata:items', 'masterdata:customers', 'masterdata:suppliers', 'workflow', 'workflow:tasks', 'workflow:my-submissions', 'oa', 'oa:schedule', 'oa:meeting', 'oa:leave', 'accounts:attendance']
  },
  {
    name: '技术工程师',
    code: 'engineer',
    type: 'primary',
    data_scope: 'ALL',
    menu_ids: ['dashboard', 'plm', 'plm:requirements', 'plm:proposals', 'plm:agreements', 'plm:model-viewer', 'plm:cad-bom', 'plm:bom-compare', 'projects', 'projects:list', 'projects:tasks', 'projects:bom', 'projects:drawings', 'projects:documents', 'projects:ecn', 'projects:bugs', 'projects:time-logs', 'projects:batch-drawing', 'projects:drawing-bom-link', 'projects:work-orders', 'knowledge', 'knowledge:articles', 'knowledge:issues', 'knowledge:components', 'purchase', 'purchase:requests', 'inventory', 'inventory:stocks', 'inventory:requisitions', 'inventory:returns', 'production', 'production:processes', 'production:debug-records', 'production:inspections', 'masterdata', 'masterdata:items', 'workflow', 'workflow:tasks', 'workflow:my-submissions', 'oa', 'oa:schedule', 'oa:leave', 'accounts:attendance']
  },
  {
    name: '销售经理',
    code: 'sales_manager',
    type: 'success',
    data_scope: 'ALL',
    menu_ids: ['dashboard', 'crm', 'masterdata:customers', 'masterdata:customer-contacts', 'masterdata:customer-followups', 'sales', 'sales:leads', 'sales:opportunities', 'sales:quotations', 'sales:orders', 'sales:contracts', 'sales:delivery-orders', 'sales:quote-estimation', 'sales:quote', 'finance:sales-reconciliation', 'finance:ar', 'finance:collection', 'aftersales', 'aftersales:orders', 'projects', 'projects:list', 'projects:dashboard', 'reports', 'reports:profitability', 'reports:cash-flow', 'reports:aging', 'masterdata', 'masterdata:items', 'workflow', 'workflow:tasks', 'workflow:my-submissions', 'oa', 'oa:schedule', 'oa:meeting', 'accounts:attendance']
  },
  {
    name: '销售人员',
    code: 'salesperson',
    type: 'success',
    data_scope: 'DEPARTMENT',
    menu_ids: ['dashboard', 'crm', 'masterdata:customers', 'masterdata:customer-contacts', 'masterdata:customer-followups', 'sales', 'sales:leads', 'sales:opportunities', 'sales:quotations', 'sales:orders', 'sales:contracts', 'sales:delivery-orders', 'sales:quote-estimation', 'sales:quote', 'finance:sales-reconciliation', 'aftersales', 'aftersales:orders', 'projects', 'projects:list', 'masterdata', 'masterdata:items', 'workflow', 'workflow:tasks', 'workflow:my-submissions', 'oa', 'oa:schedule', 'accounts:attendance']
  },
  {
    name: '采购经理',
    code: 'purchase_manager',
    type: 'info',
    data_scope: 'ALL',
    menu_ids: ['dashboard', 'purchase', 'purchase:requests', 'purchase:comparisons', 'purchase:orders', 'purchase:goods-receipts', 'purchase:outsource', 'purchase:rfqs', 'purchase:contracts', 'purchase:evaluations', 'purchase:portal', 'purchase:blacklist', 'finance:purchase-reconciliation', 'finance:ap', 'finance:payment-requests', 'inventory', 'inventory:stocks', 'inventory:mrp', 'inventory:alerts', 'projects', 'projects:list', 'reports', 'reports:slow-moving', 'reports:aging', 'masterdata', 'masterdata:suppliers', 'masterdata:items', 'workflow', 'workflow:tasks', 'workflow:my-submissions', 'oa', 'oa:schedule', 'oa:meeting', 'accounts:attendance']
  },
  {
    name: '采购人员',
    code: 'purchaser',
    type: 'info',
    data_scope: 'ALL',
    menu_ids: ['dashboard', 'purchase', 'purchase:requests', 'purchase:comparisons', 'purchase:orders', 'purchase:goods-receipts', 'purchase:outsource', 'purchase:rfqs', 'purchase:contracts', 'purchase:evaluations', 'purchase:portal', 'finance:purchase-reconciliation', 'inventory', 'inventory:stocks', 'inventory:mrp', 'masterdata', 'masterdata:suppliers', 'masterdata:items', 'workflow', 'workflow:tasks', 'workflow:my-submissions', 'oa', 'oa:schedule', 'accounts:attendance']
  },
  {
    name: '仓库管理',
    code: 'warehouse',
    type: '',
    data_scope: 'ALL',
    menu_ids: ['dashboard', 'inventory', 'inventory:stocks', 'inventory:batches', 'inventory:moves', 'inventory:transfer', 'inventory:adjustment', 'inventory:requisitions', 'inventory:returns', 'inventory:alerts', 'inventory:cost-accounting', 'purchase', 'purchase:goods-receipts', 'masterdata', 'masterdata:items', 'masterdata:warehouses', 'masterdata:locations', 'workflow', 'workflow:tasks', 'workflow:my-submissions', 'oa', 'accounts:attendance']
  },
  {
    name: '生产主管',
    code: 'production_manager',
    type: 'danger',
    data_scope: 'ALL',
    menu_ids: ['dashboard', 'production', 'production:processes', 'production:plans', 'production:debug-records', 'production:inspections', 'production:serial-numbers', 'production:routing', 'production:assembly', 'production:scheduling', 'production:capacity', 'mes', 'mes:scheduling', 'mes:kanban', 'mes:andon', 'mes:data-acquisition', 'projects', 'projects:list', 'projects:work-orders', 'equipment', 'equipment:list', 'equipment:fixtures', 'equipment:inspection', 'equipment:maintenance', 'equipment:oee', 'inventory', 'inventory:stocks', 'inventory:requisitions', 'inventory:returns', 'purchase', 'purchase:outsource', 'workflow', 'workflow:tasks', 'workflow:my-submissions', 'oa', 'oa:schedule', 'accounts:attendance']
  },
  {
    name: '财务经理',
    code: 'finance_manager',
    type: 'warning',
    data_scope: 'ALL',
    menu_ids: ['dashboard', 'finance', 'finance:expenses', 'finance:ar', 'finance:ap', 'finance:invoices', 'finance:collection', 'finance:purchase-reconciliation', 'finance:sales-reconciliation', 'finance:payment-requests', 'finance:bank-statements', 'finance:assets', 'finance:project-costs', 'reports', 'reports:profitability', 'reports:cost-analysis', 'reports:cash-flow', 'reports:aging', 'workflow', 'workflow:tasks', 'workflow:my-submissions', 'workflow:config', 'oa', 'oa:schedule', 'accounts:attendance']
  },
  {
    name: '财务人员',
    code: 'accountant',
    type: 'warning',
    data_scope: 'ALL',
    menu_ids: ['dashboard', 'finance', 'finance:expenses', 'finance:ar', 'finance:ap', 'finance:invoices', 'finance:collection', 'finance:purchase-reconciliation', 'finance:sales-reconciliation', 'finance:payment-requests', 'finance:bank-statements', 'finance:assets', 'finance:project-costs', 'reports', 'reports:aging', 'reports:cash-flow', 'workflow', 'workflow:tasks', 'workflow:my-submissions', 'oa', 'oa:schedule', 'accounts:attendance']
  },
  {
    name: '普通员工',
    code: 'employee',
    type: '',
    data_scope: 'SELF',
    menu_ids: ['dashboard', 'projects', 'projects:list', 'projects:tasks', 'projects:time-logs', 'workflow', 'workflow:tasks', 'workflow:my-submissions', 'oa', 'oa:schedule', 'oa:leave', 'oa:meeting', 'oa:announcement', 'oa:vehicle-request', 'accounts:attendance']
  }
])

// 应用预设角色配置
const applyPreset = (preset) => {
  ElMessageBox.confirm(
    `确定要应用"${preset.name}"的权限配置吗？这将覆盖当前的权限设置。`,
    '应用预设配置',
    { type: 'warning' }
  ).then(() => {
    permForm.data_scope = preset.data_scope
    if (menuTreeRef.value) {
      menuTreeRef.value.setCheckedKeys(preset.menu_ids)
    }
    ElMessage.success(`已应用"${preset.name}"的权限配置`)
  }).catch(() => {})
}

// 展开/收起树节点
const expandAll = (expand) => {
  const tree = menuTreeRef.value
  if (!tree) return
  const nodes = tree.store._getAllNodes()
  nodes.forEach(node => {
    node.expanded = expand
  })
}

// 获取所有菜单ID
const allMenuIds = computed(() => {
  const ids = []
  const traverse = (nodes) => {
    nodes.forEach(node => {
      ids.push(node.id)
      if (node.children) traverse(node.children)
    })
  }
  traverse(menuTree.value)
  return ids
})

const getDataScopeLabel = (scope) => {
  const labels = {
    'all': '全部数据',
    'ALL': '全部数据',
    'department': '部门数据',
    'DEPARTMENT': '部门数据',
    'self': '仅本人',
    'SELF': '仅本人'
  }
  return labels[scope] || scope
}

const loadRoles = async () => {
  loading.value = true
  try {
    const response = await request.get('/auth/roles/')
    roles.value = response.results || response || []
  } catch (error) {
    ElMessage.error('加载角色失败')
  } finally {
    loading.value = false
  }
}

const handleAdd = () => {
  dialogTitle.value = '新增角色'
  isEdit.value = false
  Object.assign(form, { id: null, name: '', code: '', description: '', data_scope: 'DEPARTMENT' })
  dialogVisible.value = true
}

const handleEdit = (row) => {
  dialogTitle.value = '编辑角色'
  isEdit.value = true
  Object.assign(form, {
    id: row.id,
    name: row.name,
    code: row.code,
    description: row.description,
    data_scope: row.data_scope
  })
  dialogVisible.value = true
}

const handlePermission = async (row) => {
  currentRole.value = row
  const menuIds = row.permissions?.menu_ids || []
  checkedMenuIds.value = menuIds
  
  // 设置数据权限
  permForm.data_scope = row.data_scope || 'DEPARTMENT'
  
  // 更新全选状态
  checkAll.value = menuIds.length === allMenuIds.value.length
  isIndeterminate.value = menuIds.length > 0 && menuIds.length < allMenuIds.value.length
  
  permDialogVisible.value = true
  
  await nextTick()
  if (menuTreeRef.value) {
    menuTreeRef.value.setCheckedKeys(menuIds)
  }
}

// handleDelete 已被 useBatchDelete 的 deleteRow 替代

const handleSubmit = async () => {
  try {
    await formRef.value.validate()
    saving.value = true
    
    const data = {
      name: form.name,
      code: form.code,
      description: form.description,
      data_scope: form.data_scope
    }
    
    if (isEdit.value) {
      await request.put(`/auth/roles/${form.id}/`, data)
      ElMessage.success('更新角色成功')
    } else {
      await request.post('/auth/roles/', data)
      ElMessage.success('创建角色成功')
    }
    dialogVisible.value = false
    loadRoles()
  } catch (error) {
    const msg = error.response?.data?.detail || error.response?.data?.code?.[0] || '保存角色失败'
    ElMessage.error(msg)
  } finally {
    saving.value = false
  }
}

const handleCheckAll = (val) => {
  if (menuTreeRef.value) {
    if (val) {
      menuTreeRef.value.setCheckedKeys(allMenuIds.value)
    } else {
      menuTreeRef.value.setCheckedKeys([])
    }
  }
  isIndeterminate.value = false
}

const handleMenuCheck = () => {
  if (menuTreeRef.value) {
    const checked = menuTreeRef.value.getCheckedKeys()
    checkAll.value = checked.length === allMenuIds.value.length
    isIndeterminate.value = checked.length > 0 && checked.length < allMenuIds.value.length
  }
}

const savePermissions = async () => {
  if (!currentRole.value || !menuTreeRef.value) return
  
  savingPerm.value = true
  try {
    // 获取选中的菜单ID（包括半选状态的父节点）
    const checkedKeys = menuTreeRef.value.getCheckedKeys()
    const halfCheckedKeys = menuTreeRef.value.getHalfCheckedKeys()
    const menuIds = [...checkedKeys, ...halfCheckedKeys]
    
    // 根据菜单生成权限列表
    const permissions = generatePermissions(checkedKeys)
    
    const data = {
      ...currentRole.value,
      data_scope: permForm.data_scope,  // 保存数据权限
      permissions: {
        menu_ids: menuIds,
        permissions: permissions
      }
    }
    
    await request.put(`/auth/roles/${currentRole.value.id}/`, data)
    ElMessage.success('权限配置保存成功')
    permDialogVisible.value = false
    loadRoles()
  } catch (error) {
    ElMessage.error('保存权限失败')
  } finally {
    savingPerm.value = false
  }
}

// 根据选中的菜单生成权限代码
const generatePermissions = (menuIds) => {
  const permissions = []
  
  menuIds.forEach(menuId => {
    // 为每个菜单生成基本的增删改查权限
    const module = menuId.split(':')[0]
    const subModule = menuId.split(':')[1] || ''
    
    if (subModule) {
      permissions.push(`${module}:${subModule}:view`)
      permissions.push(`${module}:${subModule}:add`)
      permissions.push(`${module}:${subModule}:edit`)
      permissions.push(`${module}:${subModule}:delete`)
    } else {
      permissions.push(`${module}:view`)
    }
  })
  
  return [...new Set(permissions)]
}

onMounted(() => {
  loadRoles()
})
</script>

<style scoped>
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.permission-config {
  max-height: 650px;
  overflow-y: auto;
}

.preset-roles {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  padding: 12px;
  background: linear-gradient(135deg, #f5f7fa 0%, #e4e7eb 100%);
  border-radius: 8px;
  margin-bottom: 16px;
}

.preset-roles .el-button {
  margin: 0;
}

.menu-tree {
  max-height: 400px;
  overflow-y: auto;
  border: 1px solid #ebeef5;
  border-radius: 4px;
  padding: 10px;
}

.role-info {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
}

.role-desc {
  color: #666;
  font-size: 14px;
}

.menu-tree-header {
  margin-bottom: 12px;
  padding: 10px 12px;
  background: #f5f7fa;
  border-radius: 4px;
  display: flex;
  align-items: center;
}

.custom-tree-node {
  display: flex;
  align-items: center;
  font-size: 14px;
}

:deep(.el-tree) {
  background: transparent;
}

:deep(.el-tree-node__content) {
  height: 36px;
}

:deep(.el-tree-node__expand-icon) {
  font-size: 16px;
}

:deep(.el-divider__text) {
  display: flex;
  align-items: center;
  gap: 6px;
  font-weight: 500;
}
</style>
