<template>
  <div class="role-list">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>角色管理</span>
          <el-button type="primary" v-permission="'system:role'" @click="handleAdd">新增角色</el-button>
        </div>
      </template>

      <!-- 批量操作工具栏 -->
      <div class="table-toolbar" v-if="canManage && selectedRows.length > 0">
        <span>已选择 {{ selectedRows.length }} 项</span>
        <el-button type="danger" size="small" @click="batchDelete" :loading="deleteLoading">批量删除</el-button>
      </div>

      <el-table :data="roles" v-loading="loading" stripe border @selection-change="handleSelectionChange">
        <el-table-column v-if="canManage" type="selection" width="55" fixed />
        <el-table-column prop="id" label="编号" width="80" />
        <el-table-column prop="name" label="角色名称" width="150" />
        <el-table-column prop="code" label="角色编码" width="150" />
        <el-table-column prop="description" label="描述" />
        <el-table-column label="权限状态" width="180">
          <template #default="{ row }">
            <el-tag :type="getRoleMenuCount(row) ? 'success' : 'warning'" size="small" style="margin-right: 5px;">
              菜单: {{ getRoleMenuCount(row) }}项
            </el-tag>
            <el-tag type="info" size="small">
              {{ getDataScopeLabel(getRoleDefaultScope(row)) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button size="small" v-permission="'system:role'" @click="handleEdit(row)">编辑</el-button>
            <el-button size="small" type="primary" v-permission="'system:role'" @click="handlePermission(row)">权限配置</el-button>
            <el-button v-if="canManage" size="small" type="danger" @click="deleteRow(row)" :loading="deleteLoading">删除</el-button>
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
            <el-option label="全部数据" value="all" />
            <el-option label="本部门及下级部门" value="dept_tree" />
            <el-option label="仅本部门" value="dept" />
            <el-option label="仅本人" value="self" />
            <el-option label="自定义部门" value="custom" />
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
        
        <el-divider content-position="left">数据范围</el-divider>
        <el-form-item label="数据可见范围" style="margin-bottom: 16px;">
          <el-select v-model="permForm.data_scope" style="width: 280px;">
            <el-option label="全部数据" value="all" />
            <el-option label="本部门及下级部门" value="dept_tree" />
            <el-option label="仅本部门" value="dept" />
            <el-option label="仅本人创建" value="self" />
            <el-option label="自定义部门" value="custom" />
          </el-select>
          <el-text type="info" size="small" style="margin-left: 12px;">
            控制该角色可查看的数据范围
          </el-text>
        </el-form-item>
        
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
          :data="permissionTreeNodes"
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

<script setup lang="ts">
import { ref, reactive, onMounted, computed, nextTick } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { QuestionFilled, Briefcase, Grid, OfficeBuilding, User } from '@element-plus/icons-vue'
import { getRoles, createRole, updateRole } from '@/api/auth'
import { getPermissionTree } from '@/api/system'
import { useBatchDelete } from '@/composables/useBatchDelete'
import { usePermission } from '@/composables/usePermission'

// 权限检查（菜单级粒度：持有 system:role 菜单即可管理角色）
const { hasPermission } = usePermission()
const canManage = computed(() => hasPermission('system:role'))

// 批量删除功能
const { selectedRows, loading: deleteLoading, handleSelectionChange, batchDelete, deleteRow } = useBatchDelete(
  '/accounts/roles/',
  { onSuccess: () => loadRoles(), confirmTitle: '删除角色', confirmMessage: '确定要删除该角色吗？删除后相关用户将失去此角色权限！' }
)

const loading = ref(false)
const saving = ref(false)
const savingPerm = ref(false)
const roles = ref<any[]>([])
const dialogVisible = ref(false)
const permDialogVisible = ref(false)
const dialogTitle = ref('新增角色')
const isEdit = ref(false)
const formRef = ref(null)
const menuTreeRef = ref(null)
const currentRole = ref(null)
const checkedMenuIds = ref<any[]>([])
const checkAll = ref(false)
const isIndeterminate = ref(false)
const permissionTreeNodes = ref<any[]>([])
const permissionMetaByCode = ref<Record<string, any>>({})
const permissionMetaById = ref<Record<string, any>>({})

const form = reactive({
  id: null,
  name: '',
  code: '',
  description: '',
  data_scope: 'all'
})

const permForm = reactive({
  data_scope: 'all'
})

const rules = {
  name: [{ required: true, message: '请输入角色名称', trigger: 'blur' }]
  // code 不再必填，后端会自动生成
}

// ============================================
// 非标自动化行业 - 预设角色模板
// 行业特点：项目制、团队小(50-200人)、跨部门协作频繁
// ============================================
const presetRoles = ref([
  {
    name: '总经理',
    code: 'general_manager',
    type: 'danger',
    data_scope: 'all',
    menu_ids: ['dashboard', 'projects', 'design', 'plm', 'sales', 'purchase', 'inventory', 'production', 'mes', 'equipment', 'finance', 'aftersales', 'masterdata', 'knowledge', 'oa', 'workflow', 'reports', 'analytics', 'system']
  },
  {
    name: '项目经理',
    code: 'project_manager',
    type: 'warning',
    data_scope: 'all',
    menu_ids: ['dashboard', 'projects', 'design', 'plm', 'knowledge', 'purchase:requests', 'purchase:orders', 'purchase:goods-receipts', 'purchase:outsource', 'sales:quotations', 'sales:orders', 'sales:delivery-orders', 'aftersales', 'inventory:stocks', 'inventory:requisitions', 'inventory:returns', 'inventory:mrp', 'production:plans', 'production:debug-records', 'production:inspections', 'mes:scheduling', 'mes:kanban', 'equipment:list', 'equipment:fixtures', 'reports:profitability', 'reports:cost-analysis', 'reports:timelog', 'masterdata:items', 'masterdata:customers', 'masterdata:suppliers', 'oa:workflow', 'oa:schedule', 'oa:meeting', 'oa:leave', 'accounts:attendance']
  },
  {
    name: '技术工程师',
    code: 'engineer',
    type: 'primary',
    data_scope: 'all',
    menu_ids: ['dashboard', 'projects:list', 'projects:tasks', 'projects:bom', 'projects:bom-cost', 'projects:bugs', 'projects:drawing-versions', 'projects:time-logs', 'projects:work-orders', 'design', 'plm', 'knowledge', 'purchase:requests', 'inventory:stocks', 'inventory:requisitions', 'inventory:returns', 'production:processes', 'production:routing', 'production:debug-records', 'production:inspections', 'masterdata:items', 'oa:workflow', 'oa:schedule', 'oa:leave', 'accounts:attendance']
  },
  {
    name: '销售经理',
    code: 'sales_manager',
    type: 'success',
    data_scope: 'all',
    menu_ids: ['dashboard', 'sales', 'masterdata:customers', 'masterdata:customer-contacts', 'masterdata:customer-followups', 'masterdata:items', 'finance:ar', 'finance:collection', 'finance:sales-reconciliation', 'aftersales', 'projects:list', 'projects:dashboard', 'reports:profitability', 'reports:cash-flow', 'reports:aging', 'reports:customer-value', 'oa:workflow', 'oa:schedule', 'oa:meeting', 'accounts:attendance']
  },
  {
    name: '销售人员',
    code: 'salesperson',
    type: 'success',
    data_scope: 'self',
    menu_ids: ['dashboard', 'sales:crm-dashboard', 'sales:leads', 'sales:opportunities', 'sales:quotations', 'sales:quote', 'sales:quote-estimation', 'sales:orders', 'sales:contracts', 'sales:delivery-orders', 'masterdata:customers', 'masterdata:customer-contacts', 'masterdata:customer-followups', 'masterdata:items', 'aftersales:orders', 'projects:list', 'oa:workflow', 'oa:schedule', 'accounts:attendance']
  },
  {
    name: '采购经理',
    code: 'purchase_manager',
    type: 'info',
    data_scope: 'all',
    menu_ids: ['dashboard', 'purchase', 'masterdata:suppliers', 'masterdata:items', 'inventory:stocks', 'inventory:mrp', 'inventory:alerts', 'finance:ap', 'finance:purchase-reconciliation', 'projects:list', 'reports:slow-moving', 'reports:aging', 'reports:cost-analysis', 'oa:workflow', 'oa:schedule', 'oa:meeting', 'accounts:attendance']
  },
  {
    name: '采购人员',
    code: 'purchaser',
    type: 'info',
    data_scope: 'self',
    menu_ids: ['dashboard', 'purchase:requests', 'purchase:orders', 'purchase:goods-receipts', 'purchase:rfqs', 'purchase:comparisons', 'purchase:outsource', 'purchase:collaboration', 'masterdata:suppliers', 'masterdata:items', 'inventory:stocks', 'inventory:mrp', 'finance:purchase-reconciliation', 'oa:workflow', 'oa:schedule', 'accounts:attendance']
  },
  {
    name: '仓库管理',
    code: 'warehouse_manager',
    type: '',
    data_scope: 'all',
    menu_ids: ['dashboard', 'inventory', 'purchase:goods-receipts', 'masterdata:items', 'masterdata:warehouses', 'masterdata:locations', 'oa:workflow', 'oa:schedule', 'accounts:attendance']
  },
  {
    name: '生产主管',
    code: 'production_manager',
    type: 'danger',
    data_scope: 'all',
    menu_ids: ['dashboard', 'production', 'mes', 'equipment', 'projects:list', 'projects:work-orders', 'inventory:stocks', 'inventory:requisitions', 'inventory:returns', 'purchase:outsource', 'reports:capacity-utilization', 'oa:workflow', 'oa:schedule', 'accounts:attendance']
  },
  {
    name: '财务经理',
    code: 'finance_manager',
    type: 'warning',
    data_scope: 'all',
    menu_ids: ['dashboard', 'finance', 'reports:profitability', 'reports:project-profitability', 'reports:cost-analysis', 'reports:cash-flow', 'reports:aging', 'oa:workflow', 'oa:schedule', 'accounts:attendance']
  },
  {
    name: '财务人员',
    code: 'accountant',
    type: 'warning',
    data_scope: 'self',
    menu_ids: ['dashboard', 'finance:expenses', 'finance:ar', 'finance:ap', 'finance:invoices', 'finance:collection', 'finance:assets', 'finance:purchase-reconciliation', 'finance:sales-reconciliation', 'finance:shared-expenses', 'reports:aging', 'reports:cash-flow', 'oa:workflow', 'oa:schedule', 'accounts:attendance']
  },
  {
    name: '普通员工',
    code: 'employee',
    type: '',
    data_scope: 'self',
    menu_ids: ['dashboard', 'projects:list', 'projects:tasks', 'projects:time-logs', 'oa:announcement', 'oa:meeting', 'oa:schedule', 'oa:leave', 'oa:vehicle-request', 'oa:workflow', 'accounts:attendance']
  }
])

// 应用预设角色配置
const applyPreset = (preset) => {
  ElMessageBox.confirm(
    `确定要应用"${preset.name}"的权限配置吗？这将覆盖当前的权限设置。`,
    '应用预设配置',
    { type: 'warning' }
  ).then(() => {
    permForm.data_scope = normalizeScopeForForm(preset.data_scope)
    if (menuTreeRef.value) {
      menuTreeRef.value.setCheckedKeys(
        preset.menu_ids.filter(code => permissionMetaByCode.value[code])
      )
    }
    ElMessage.success(`已应用"${preset.name}"的权限配置`)
  }).catch(error => { console.error(error) })
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
  traverse(permissionTreeNodes.value)
  return ids
})

const normalizeScopeForForm = (scope) => {
  const normalized = {
    ALL: 'all',
    all: 'all',
    global: 'all',
    GLOBAL: 'all',
    DEPARTMENT: 'dept_tree',
    department_and_below: 'dept_tree',
    DEPT_TREE: 'dept_tree',
    dept_tree: 'dept_tree',
    department: 'dept',
    DEPT: 'dept',
    dept: 'dept',
    SELF: 'self',
    self: 'self',
    CUSTOM: 'custom',
    custom: 'custom'
  }
  return normalized[scope] || 'dept_tree'
}

const formatPermissionTree = (nodes) => {
  return nodes.map(node => ({
    id: node.code,
    label: node.name,
    type: node.type,
    children: formatPermissionTree(node.children || [])
  }))
}

const indexPermissionTree = (nodes) => {
  const codeMap = {}
  const idMap = {}

  const walk = (node) => {
    const descendantIds = [node.id]
    ;(node.children || []).forEach(child => {
      descendantIds.push(...walk(child))
    })

    codeMap[node.code] = {
      id: node.id,
      code: node.code,
      type: node.type,
      descendantIds: [...new Set(descendantIds)]
    }
    idMap[node.id] = {
      code: node.code,
      type: node.type
    }

    return descendantIds
  }

  nodes.forEach(walk)
  permissionMetaByCode.value = codeMap
  permissionMetaById.value = idMap
}

const loadPermissionCatalog = async () => {
  const response = await getPermissionTree()
  const tree = Array.isArray(response) ? response : (response.results || [])
  permissionTreeNodes.value = formatPermissionTree(tree)
  indexPermissionTree(tree)
}

const getRoleCheckedCodes = (row) => {
  return [...new Set(
    (row.permission_ids || [])
      .map(id => permissionMetaById.value[id])
      .filter(Boolean)
      .map(meta => meta.code)
  )]
}

const getRoleMenuCount = (row) => getRoleCheckedCodes(row).length

const getRoleDefaultScope = (row) => {
  const defaultScope = (row.data_scopes || []).find(scope => !scope.module)
  return normalizeScopeForForm(defaultScope?.scope_type)
}

const buildPermissionIdsFromCheckedCodes = (checkedCodes, halfCheckedCodes) => {
  const fullCheckedIds = checkedCodes.flatMap(code => permissionMetaByCode.value[code]?.descendantIds || [])
  const halfCheckedIds = halfCheckedCodes.map(code => permissionMetaByCode.value[code]?.id).filter(Boolean)

  return [...new Set([...fullCheckedIds, ...halfCheckedIds])]
}

const getDataScopeLabel = (scope) => {
  const labels = {
    all: '全部数据',
    dept_tree: '本部门及下级部门',
    dept: '仅本部门',
    self: '仅本人',
    custom: '自定义部门'
  }
  return labels[scope] || scope
}

const loadRoles = async () => {
  loading.value = true
  try {
    const response = await getRoles()
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
  Object.assign(form, { id: null, name: '', code: '', description: '', data_scope: 'all' })
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
    data_scope: getRoleDefaultScope(row)
  })
  dialogVisible.value = true
}

const handlePermission = async (row) => {
  if (Object.keys(permissionMetaByCode.value).length === 0) {
    await loadPermissionCatalog()
  }

  currentRole.value = row
  const menuIds = getRoleCheckedCodes(row)
  checkedMenuIds.value = menuIds
  
  // 设置数据权限
  permForm.data_scope = getRoleDefaultScope(row)
  
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
      data_scopes: [
        {
          module: '',
          scope_type: form.data_scope,
          department_ids: []
        }
      ]
    }
    
    if (isEdit.value) {
      await updateRole(form.id, data)
      ElMessage.success('更新角色成功')
    } else {
      await createRole(data)
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
    const checkedKeys = menuTreeRef.value.getCheckedKeys()
    const halfCheckedKeys = menuTreeRef.value.getHalfCheckedKeys()
    const permissionIds = buildPermissionIdsFromCheckedCodes(checkedKeys, halfCheckedKeys)
    
    const data = {
      name: currentRole.value.name,
      code: currentRole.value.code,
      description: currentRole.value.description,
      is_active: currentRole.value.is_active,
      sort_order: currentRole.value.sort_order,
      permission_ids: permissionIds,
      data_scopes: [
        {
          module: '',
          scope_type: permForm.data_scope,
          department_ids: []
        }
      ]
    }
    
    await updateRole(currentRole.value.id, data)
    ElMessage.success('权限配置保存成功')
    permDialogVisible.value = false
    loadRoles()
  } catch (error) {
    ElMessage.error('保存权限失败')
  } finally {
    savingPerm.value = false
  }
}

onMounted(async () => {
  try {
    await Promise.all([loadPermissionCatalog(), loadRoles()])
  } catch (error) {
    console.error('加载数据失败', error)
    ElMessage.error('加载数据失败')
  }
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
