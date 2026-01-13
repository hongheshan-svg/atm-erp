<template>
  <div class="role-list">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>角色管理</span>
          <el-button type="primary" @click="handleAdd">新增角色</el-button>
        </div>
      </template>

      <el-table :data="roles" v-loading="loading" stripe border>
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
            <el-button size="small" type="danger" @click="handleDelete(row)">删除</el-button>
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
    <el-dialog v-model="permDialogVisible" title="权限配置" width="750px">
      <div v-if="currentRole" class="permission-config">
        <div class="role-info">
          <el-tag type="primary" size="large">{{ currentRole.name }}</el-tag>
          <span class="role-desc">{{ currentRole.description }}</span>
        </div>
        
        <el-divider content-position="left">数据权限</el-divider>
        <el-form label-width="100px">
          <el-form-item label="数据范围">
            <el-radio-group v-model="permForm.data_scope">
              <el-radio-button value="ALL">全部数据</el-radio-button>
              <el-radio-button value="DEPARTMENT">本部门数据</el-radio-button>
              <el-radio-button value="SELF">仅本人数据</el-radio-button>
            </el-radio-group>
          </el-form-item>
          <el-form-item>
            <el-text type="info" size="small">
              <template v-if="permForm.data_scope === 'ALL'">可查看系统中所有数据</template>
              <template v-else-if="permForm.data_scope === 'DEPARTMENT'">仅可查看本部门及下级部门的数据</template>
              <template v-else>仅可查看自己创建或被分配的数据</template>
            </el-text>
          </el-form-item>
        </el-form>
        
        <el-divider content-position="left">菜单权限</el-divider>
        
        <div class="menu-tree-header">
          <el-checkbox v-model="checkAll" :indeterminate="isIndeterminate" @change="handleCheckAll">
            全选
          </el-checkbox>
          <el-text type="info" size="small" style="margin-left: 15px;">
            勾选的菜单将在侧边栏中显示
          </el-text>
        </div>
        
        <el-tree
          ref="menuTreeRef"
          :data="menuTree"
          show-checkbox
          node-key="id"
          :default-checked-keys="checkedMenuIds"
          :props="{ label: 'label', children: 'children' }"
          @check="handleMenuCheck"
          class="menu-tree"
        />
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
import { QuestionFilled } from '@element-plus/icons-vue'
import request from '@/utils/request'

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
      { id: 'system:config', label: '系统配置' }
    ]
  },
  {
    id: 'masterdata',
    label: '基础数据',
    children: [
      { id: 'masterdata:items', label: '物料管理' },
      { id: 'masterdata:customers', label: '客户管理' },
      { id: 'masterdata:suppliers', label: '供应商管理' },
      { id: 'masterdata:warehouses', label: '仓库管理' },
      { id: 'masterdata:locations', label: '库位管理' }
    ]
  },
  {
    id: 'projects',
    label: '项目管理',
    children: [
      { id: 'projects:list', label: '项目列表' },
      { id: 'projects:tasks', label: '任务管理' },
      { id: 'projects:members', label: '成员管理' },
      { id: 'projects:bom', label: 'BOM清单' },
      { id: 'projects:time-logs', label: '工时填报' },
      { id: 'projects:gantt', label: '甘特图' },
      { id: 'projects:bugs', label: 'Bug跟踪' }
    ]
  },
  {
    id: 'purchase',
    label: '采购管理',
    children: [
      { id: 'purchase:requests', label: '采购申请' },
      { id: 'purchase:rfqs', label: '询价管理' },
      { id: 'purchase:comparisons', label: '比价分析' },
      { id: 'purchase:orders', label: '采购订单' },
      { id: 'purchase:goods-receipts', label: '到货质检' }
    ]
  },
  {
    id: 'sales',
    label: '销售管理',
    children: [
      { id: 'sales:quotations', label: '销售报价' },
      { id: 'sales:orders', label: '销售订单' },
      { id: 'sales:contracts', label: '销售合同' },
      { id: 'sales:delivery-orders', label: '发货单' }
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
      { id: 'inventory:requisitions', label: '生产领料' },
      { id: 'inventory:returns', label: '生产退料' }
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
      { id: 'finance:project-costs', label: '项目成本核算' }
    ]
  },
  {
    id: 'reports',
    label: '报表统计',
    children: [
      { id: 'reports:profitability', label: '项目利润分析' },
      { id: 'reports:inventory-turnover', label: '库存周转率' },
      { id: 'reports:aging', label: '账龄分析' },
      { id: 'reports:purchase-price-trend', label: '采购价格趋势' },
      { id: 'reports:cash-flow', label: '现金流预测' },
      { id: 'reports:slow-moving', label: '呆滞物料分析' }
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

const handleDelete = async (row) => {
  try {
    await ElMessageBox.confirm('确定要删除该角色吗？', '警告', {
      type: 'warning'
    })
    await request.delete(`/auth/roles/${row.id}/`)
    ElMessage.success('删除成功')
    loadRoles()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('删除角色失败')
    }
  }
}

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
  max-height: 600px;
  overflow-y: auto;
}

.menu-tree {
  max-height: 350px;
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
  padding: 8px;
  background: #f5f7fa;
  border-radius: 4px;
}

:deep(.el-tree) {
  background: transparent;
}

:deep(.el-tree-node__content) {
  height: 32px;
}
</style>
