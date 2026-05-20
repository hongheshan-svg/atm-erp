<template>
  <div class="workflow-config-sap">
    <!-- 顶部工具栏 -->
    <div class="toolbar">
      <div class="toolbar-left">
        <el-button type="primary" @click="showCreateDialog">
          <el-icon><Plus /></el-icon>
          新建流程
        </el-button>
        <el-button @click="loadWorkflows" :loading="loading">
          <el-icon><Refresh /></el-icon>
          刷新
        </el-button>
      </div>
      <div class="toolbar-right">
        <el-input v-model="searchText" placeholder="搜索流程..." clearable style="width: 200px">
          <template #prefix><el-icon><Search /></el-icon></template>
        </el-input>
      </div>
    </div>

    <!-- 主内容区：左右分栏 -->
    <div class="main-content">
      <!-- 左侧：流程列表 -->
      <div class="workflow-list-panel">
        <div class="panel-header">
          <span>流程定义</span>
          <el-tag size="small">{{ filteredWorkflows.length }} 个</el-tag>
        </div>
        
        <!-- 按业务类型分组的树形结构 -->
        <el-tree
          :data="treeData"
          :props="{ label: 'label', children: 'children' }"
          node-key="id"
          highlight-current
          :expand-on-click-node="false"
          @node-click="handleNodeClick"
          default-expand-all
          class="workflow-tree"
        >
          <template #default="{ node: _node, data }">
            <div class="tree-node" :class="{ 'is-workflow': data.isWorkflow }">
              <div class="node-content">
                <el-icon v-if="!data.isWorkflow" class="folder-icon"><Folder /></el-icon>
                <el-icon v-else class="workflow-icon"><Document /></el-icon>
                <span class="node-label">{{ data.label }}</span>
                <el-tag v-if="!data.isWorkflow && data.isEmpty" size="small" type="info">点击配置</el-tag>
                <el-tag v-if="data.isWorkflow && !data.is_active" size="small" type="danger">停用</el-tag>
                <el-tag v-if="data.isWorkflow && data.isDefault" size="small" type="info">默认</el-tag>
                <el-tag v-if="data.isWorkflow && data.amount_threshold" size="small" type="warning">
                  ≥{{ formatAmount(data.amount_threshold) }}
                </el-tag>
              </div>
            </div>
          </template>
        </el-tree>
      </div>

      <!-- 右侧：流程详情和步骤配置 -->
      <div class="workflow-detail-panel">
        <template v-if="selectedWorkflow">
          <!-- 流程基本信息 -->
          <div class="detail-header">
            <div class="header-info">
              <h2>{{ selectedWorkflow.name }}</h2>
              <div class="header-meta">
                <el-tag :type="selectedWorkflow.is_active ? 'success' : 'danger'" size="small">
                  {{ selectedWorkflow.is_active ? '已启用' : '已停用' }}
                </el-tag>
                <el-tag type="info" size="small">
                  {{ getBusinessTypeLabel(selectedWorkflow.business_type) }}
                </el-tag>
              </div>
            </div>
            <div class="header-actions">
              <el-button @click="editWorkflow(selectedWorkflow)">编辑</el-button>
              <el-button 
                :type="selectedWorkflow.is_active ? 'warning' : 'success'"
                @click="toggleStatus(selectedWorkflow)"
              >
                {{ selectedWorkflow.is_active ? '停用' : '启用' }}
              </el-button>
              <el-button type="danger" @click="deleteWorkflow(selectedWorkflow)">删除</el-button>
            </div>
          </div>

          <!-- 流程属性卡片 -->
          <div class="property-cards">
            <div class="prop-card">
              <div class="prop-icon"><el-icon><Briefcase /></el-icon></div>
              <div class="prop-content">
                <div class="prop-label">业务类型</div>
                <div class="prop-value">{{ selectedWorkflow.business_type_display }}</div>
              </div>
            </div>
            <div class="prop-card">
              <div class="prop-icon"><el-icon><Money /></el-icon></div>
              <div class="prop-content">
                <div class="prop-label">金额阈值</div>
                <div class="prop-value">{{ selectedWorkflow.amount_threshold ? '≥ ¥' + formatAmount(selectedWorkflow.amount_threshold) : '默认流程' }}</div>
              </div>
            </div>
            <div class="prop-card">
              <div class="prop-icon"><el-icon><List /></el-icon></div>
              <div class="prop-content">
                <div class="prop-label">审批步骤</div>
                <div class="prop-value">{{ steps.length }} 个步骤</div>
              </div>
            </div>
            <div class="prop-card">
              <div class="prop-icon"><el-icon><Clock /></el-icon></div>
              <div class="prop-content">
                <div class="prop-label">预计耗时</div>
                <div class="prop-value">{{ estimatedDays }} 天</div>
              </div>
            </div>
          </div>

          <!-- 可视化流程图 -->
          <div class="flow-designer">
            <div class="designer-header">
              <span class="title">审批流程设计</span>
              <el-button type="primary" size="small" @click="addStep">
                <el-icon><Plus /></el-icon>
                添加步骤
              </el-button>
            </div>
            
            <div class="flow-canvas" v-loading="stepsLoading">
              <!-- 开始节点 -->
              <div class="flow-node start-node">
                <div class="node-circle start">
                  <el-icon><VideoPlay /></el-icon>
                </div>
                <div class="node-label">提交申请</div>
              </div>

              <!-- 连接线 -->
              <div class="flow-connector" v-if="steps.length > 0"></div>

              <!-- 审批步骤节点 -->
              <template v-for="(step, index) in steps" :key="step.id">
                <div 
                  class="flow-node step-node"
                  :class="{ 'is-selected': selectedStep?.id === step.id }"
                  @click="selectStep(step)"
                >
                  <div class="node-box">
                    <div class="node-header">
                      <span class="step-order">{{ index + 1 }}</span>
                      <span class="step-name">{{ step.name }}</span>
                      <div class="node-actions">
                        <el-icon class="action-icon" @click.stop="editStep(step)"><Edit /></el-icon>
                        <el-icon class="action-icon delete" @click.stop="deleteStep(step)"><Delete /></el-icon>
                      </div>
                    </div>
                    <div class="node-body">
                      <div class="approver-info">
                        <el-icon><User /></el-icon>
                        <span>{{ getApproverDisplay(step) }}</span>
                      </div>
                      <div class="step-meta">
                        <el-tag size="small" :type="getApproverTypeColor(step.approver_type)">
                          {{ getApproverTypeLabel(step.approver_type) }}
                        </el-tag>
                        <el-tag v-if="step.can_reject" size="small" type="danger">可拒绝</el-tag>
                        <el-tag v-if="step.timeout_hours" size="small" type="warning">{{ Math.ceil(step.timeout_hours/24) }}天超时</el-tag>
                        <el-tag v-if="getCcCount(step) > 0" size="small" type="info">
                          抄送{{ getCcCount(step) }}人
                        </el-tag>
                      </div>
                    </div>
                    <!-- 排序按钮 -->
                    <div class="sort-buttons">
                      <el-button 
                        size="small" 
                        circle 
                        :disabled="index === 0"
                        @click.stop="moveStep(index, -1)"
                      >
                        <el-icon><ArrowUp /></el-icon>
                      </el-button>
                      <el-button 
                        size="small" 
                        circle 
                        :disabled="index === steps.length - 1"
                        @click.stop="moveStep(index, 1)"
                      >
                        <el-icon><ArrowDown /></el-icon>
                      </el-button>
                    </div>
                  </div>
                </div>
                
                <!-- 连接线 -->
                <div class="flow-connector" v-if="index < steps.length - 1"></div>
              </template>

              <!-- 添加步骤占位 -->
              <div class="flow-connector" v-if="steps.length > 0"></div>

              <!-- 结束节点 -->
              <div class="flow-node end-node">
                <div class="node-circle end">
                  <el-icon><CircleCheck /></el-icon>
                </div>
                <div class="node-label">审批完成</div>
              </div>

              <!-- 空状态 -->
              <div v-if="steps.length === 0 && !stepsLoading" class="empty-flow">
                <el-empty description="暂无审批步骤">
                  <el-button type="primary" @click="addStep">添加第一个步骤</el-button>
                </el-empty>
              </div>
            </div>
          </div>
        </template>

        <!-- 未选择流程时的提示 -->
        <div v-else class="no-selection">
          <el-empty description="请从左侧选择一个流程进行配置">
            <el-button type="primary" @click="showCreateDialog">或创建新流程</el-button>
          </el-empty>
        </div>
      </div>
    </div>

    <!-- 创建/编辑流程对话框 -->
    <el-dialog v-model="dialogVisible" :title="isEdit ? '编辑流程' : '新建流程'" width="600px" destroy-on-close>
      <el-form :model="form" :rules="rules" ref="formRef" label-width="100px" label-position="top">
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="流程名称" prop="name">
              <el-input v-model="form.name" placeholder="如: 采购申请审批(大额)" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="流程编码" prop="code">
              <el-input v-model="form.code" :disabled="isEdit" placeholder="系统自动生成或自定义" />
              <div class="form-tip">流程唯一标识，创建后不可修改</div>
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="业务类型" prop="business_type">
              <el-select v-model="form.business_type" style="width: 100%" placeholder="选择业务类型">
                <el-option v-for="(label, value) in businessTypeLabels" :key="value" :label="label" :value="value" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="金额阈值">
              <el-input-number v-model="form.amount_threshold" :min="0" :precision="2" style="width: 100%" placeholder="留空为默认流程" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="流程描述">
          <el-input v-model="form.description" type="textarea" :rows="3" placeholder="描述此流程的用途和适用场景" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="saveWorkflow" :loading="saving">保存</el-button>
      </template>
    </el-dialog>

    <!-- 步骤编辑对话框 -->
    <el-dialog v-model="stepDialogVisible" :title="isEditStep ? '编辑审批步骤' : '添加审批步骤'" width="550px" destroy-on-close>
      <el-form :model="stepForm" :rules="stepRules" ref="stepFormRef" label-width="100px" label-position="top">
        <el-form-item label="步骤名称" prop="name">
          <el-input v-model="stepForm.name" placeholder="如: 部门经理审批、财务总监审批" />
        </el-form-item>
        
        <el-form-item label="审批人类型" prop="approver_type">
          <div class="approver-type-selector">
            <div 
              v-for="type in approverTypes" 
              :key="type.value"
              class="type-option"
              :class="{ 'is-selected': stepForm.approver_type === type.value }"
              @click="selectApproverType(type.value)"
            >
              <el-icon :size="24"><component :is="type.icon" /></el-icon>
              <div class="type-label">{{ type.label }}</div>
              <div class="type-desc">{{ type.desc }}</div>
            </div>
          </div>
        </el-form-item>

        <el-form-item v-if="stepForm.approver_type === 'USER'" label="选择审批人" prop="approver">
          <el-select v-model="stepForm.approver" style="width: 100%" filterable placeholder="搜索并选择用户">
            <el-option v-for="user in users" :key="user.id" :label="getUserLabel(user)" :value="user.id">
              <div class="user-option">
                <span>{{ user.display_name || user.username }}</span>
                <span class="user-dept">{{ user.department_name || '' }}</span>
              </div>
            </el-option>
          </el-select>
        </el-form-item>

        <el-form-item v-if="stepForm.approver_type === 'ROLE'" label="选择角色" prop="role">
          <el-select v-model="stepForm.role" style="width: 100%" filterable placeholder="搜索并选择角色">
            <el-option v-for="role in roles" :key="role.id" :label="role.name" :value="role.id" />
          </el-select>
        </el-form-item>

        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="允许拒绝">
              <el-switch v-model="stepForm.can_reject" active-text="是" inactive-text="否" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="超时天数">
              <el-input-number v-model="stepForm.timeout_days" :min="0" :max="30" style="width: 100%" />
            </el-form-item>
          </el-col>
        </el-row>

        <el-divider content-position="left">抄送设置</el-divider>
        
        <el-form-item label="抄送人员">
          <el-select 
            v-model="stepForm.cc_users" 
            multiple 
            filterable 
            style="width: 100%" 
            placeholder="选择需要抄送的人员（可多选）"
          >
            <el-option v-for="user in users" :key="user.id" :label="getUserLabel(user)" :value="user.id">
              <div class="user-option">
                <span>{{ user.display_name || user.username }}</span>
                <span class="user-dept">{{ user.department_name || '' }}</span>
              </div>
            </el-option>
          </el-select>
        </el-form-item>

        <el-form-item label="抄送角色">
          <el-select 
            v-model="stepForm.cc_roles" 
            multiple 
            filterable 
            style="width: 100%" 
            placeholder="选择需要抄送的角色（可多选）"
          >
            <el-option v-for="role in roles" :key="role.id" :label="role.name" :value="role.id" />
          </el-select>
          <div class="form-tip">该角色下的所有人员都会收到抄送通知</div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="stepDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="saveStep" :loading="stepSaving">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { 
  Plus, Refresh, Search, Folder, Document, Briefcase, Money, List, Clock,
  VideoPlay, CircleCheck, Edit, Delete, User, ArrowUp, ArrowDown,
  UserFilled, Avatar, OfficeBuilding, Connection
} from '@element-plus/icons-vue'
import { 
  getWorkflowDefinitions, createWorkflowDefinition, updateWorkflowDefinition, deleteWorkflowDefinition,
  getWorkflowSteps, createWorkflowStep, updateWorkflowStep, deleteWorkflowStep
} from '@/api/workflow'
import { getUsers, getRoles } from '@/api/auth'

// 状态
const loading = ref(false)
const saving = ref(false)
const stepsLoading = ref(false)
const stepSaving = ref(false)
const workflows = ref([])
const selectedWorkflow = ref(null)
const selectedStep = ref(null)
const steps = ref([])
const users = ref([])
const roles = ref([])
const searchText = ref('')

// 对话框
const dialogVisible = ref(false)
const stepDialogVisible = ref(false)
const isEdit = ref(false)
const isEditStep = ref(false)
const formRef = ref(null)
const stepFormRef = ref(null)

// 表单
const form = ref({ code: '', name: '', business_type: '', amount_threshold: null, description: '', is_active: true })
const stepForm = ref({ name: '', approver_type: 'USER', approver: null, role: null, can_reject: true, timeout_days: 3, cc_users: [], cc_roles: [] })

// 常量 - 业务类型中文标签
const businessTypeLabels = {
  // 采购管理
  'PURCHASE_REQUEST': '采购申请',
  'PURCHASE_ORDER': '采购订单',
  'PURCHASE_CONTRACT': '采购合同',
  'OUTSOURCE_MATERIAL_ISSUE': '外协发料',
  'OUTSOURCE_RECEIPT': '外协收货',
  'CONTRACT_EXECUTION': '合同执行',
  'PAYMENT_RECORD': '合同付款',
  // 销售管理
  'QUOTATION': '销售报价',
  'SALES_ORDER': '销售订单',
  'SALES_CONTRACT': '销售合同',
  'DELIVERY_ORDER': '发货单',
  'SERVICE_REQUEST': '售后服务',
  // 财务管理
  'EXPENSE': '费用报销',
  'PAYMENT': '付款申请',
  // 项目管理
  'PROJECT': '项目立项',
  'ECN': '工程变更',
  // 库存管理
  'STOCK_ADJUSTMENT': '库存调整',
  // OA办公
  'LEAVE_REQUEST': '请假申请',
  'OVERTIME_REQUEST': '加班申请',
  'VEHICLE_REQUEST': '用车申请',
  'ASSET_BORROW': '资产借用'
}

const approverTypes = [
  { value: 'USER', label: '指定用户', desc: '固定审批人', icon: 'UserFilled' },
  { value: 'ROLE', label: '指定角色', desc: '角色内任意用户', icon: 'Avatar' },
  { value: 'DEPARTMENT_MANAGER', label: '部门经理', desc: '提交人部门经理', icon: 'OfficeBuilding' },
  { value: 'PROJECT_MANAGER', label: '项目经理', desc: '关联项目的项目经理', icon: 'Briefcase' },
  { value: 'SUPERIOR', label: '直接上级', desc: '提交人的上级', icon: 'Connection' }
]

const rules = {
  code: [{ required: true, message: '请输入流程编码', trigger: 'blur' }],
  name: [{ required: true, message: '请输入流程名称', trigger: 'blur' }],
  business_type: [{ required: true, message: '请选择业务类型', trigger: 'change' }]
}

const stepRules = {
  name: [{ required: true, message: '请输入步骤名称', trigger: 'blur' }],
  approver_type: [{ required: true, message: '请选择审批人类型', trigger: 'change' }]
}

// 计算属性
const filteredWorkflows = computed(() => {
  if (!searchText.value) return workflows.value
  const search = searchText.value.toLowerCase()
  return workflows.value.filter(w => 
    w.name.toLowerCase().includes(search) || 
    w.code.toLowerCase().includes(search)
  )
})

const treeData = computed(() => {
  // 先创建所有业务类型的分组（确保都显示）
  const groups = {}
  Object.keys(businessTypeLabels).forEach(type => {
    groups[type] = {
      id: `group_${type}`,
      label: businessTypeLabels[type],
      children: [],
      isEmpty: true
    }
  })
  
  // 将现有工作流添加到对应分组
  filteredWorkflows.value.forEach(w => {
    const type = w.business_type
    if (groups[type]) {
      groups[type].isEmpty = false
      groups[type].children.push({
        ...w,
        id: w.id,
        label: w.name,
        isWorkflow: true,
        isDefault: !w.amount_threshold
      })
    }
  })
  return Object.values(groups)
})

const estimatedDays = computed(() => {
  return steps.value.reduce((sum, s) => sum + Math.ceil((s.timeout_hours || 24) / 24), 0)
})

// 方法
const formatAmount = (amount) => Number(amount).toLocaleString()

const getBusinessTypeLabel = (type) => businessTypeLabels[type] || type

const getApproverTypeLabel = (type) => {
  const t = approverTypes.find(a => a.value === type)
  return t ? t.label : type
}

const getApproverTypeColor = (type) => {
  const colors = { 
    'USER': 'primary', 
    'ROLE': 'success', 
    'DEPARTMENT_MANAGER': 'warning', 
    'PROJECT_MANAGER': 'danger',
    'SUPERIOR': 'info' 
  }
  return colors[type] || ''
}

const getApproverDisplay = (step) => {
  if (step.approver_type === 'USER') return step.approver_user_name || '未指定用户'
  if (step.approver_type === 'ROLE') return step.approver_role_name || '未指定角色'
  if (step.approver_type === 'DEPARTMENT_HEAD' || step.approver_type === 'DEPARTMENT_MANAGER') return '部门负责人'
  if (step.approver_type === 'SUBMITTER_LEADER' || step.approver_type === 'SUPERIOR') return '直接上级'
  if (step.approver_type === 'PROJECT_MANAGER') return '项目经理'
  return '-'
}

const getCcCount = (step) => {
  const userCount = step.cc_users_detail?.length || step.cc_users?.length || 0
  const roleCount = step.cc_roles_detail?.length || step.cc_roles?.length || 0
  return userCount + roleCount
}

const getUserLabel = (user) => {
  let label = user.display_name || user.username
  if (user.department_name) label += ` (${user.department_name})`
  return label
}

const loadWorkflows = async () => {
  loading.value = true
  try {
    const res = await getWorkflowDefinitions()
    workflows.value = res.results || res || []
  } catch (error) {
    workflows.value = []
  } finally {
    loading.value = false
  }
}

const loadSteps = async () => {
  if (!selectedWorkflow.value) return
  stepsLoading.value = true
  try {
    const res = await getWorkflowSteps({ workflow: selectedWorkflow.value.id })
    steps.value = (res.results || res || []).sort((a, b) => (a.step_order || a.order || 0) - (b.step_order || b.order || 0))
  } catch (error) {
    steps.value = []
  } finally {
    stepsLoading.value = false
  }
}

const loadUsersAndRoles = async () => {
  try {
    const [usersRes, rolesRes] = await Promise.all([getUsers(), getRoles()])
    users.value = usersRes.results || usersRes || []
    roles.value = rolesRes.results || rolesRes || []
  } catch (error) {
    console.error('Failed to load users/roles:', error)
  }
}

const handleNodeClick = (data) => {
  if (data.isWorkflow) {
    selectedWorkflow.value = data
    selectedStep.value = null
    loadSteps()
  } else if (data.id?.startsWith('group_')) {
    // 点击分类节点时，自动弹出创建对话框并预选该业务类型
    const businessType = data.id.replace('group_', '')
    showCreateDialogWithType(businessType)
  }
}

const selectStep = (step) => {
  selectedStep.value = step
}

const showCreateDialog = () => {
  isEdit.value = false
  form.value = { code: '', name: '', business_type: '', amount_threshold: null, description: '', is_active: true }
  dialogVisible.value = true
}

const showCreateDialogWithType = (businessType) => {
  isEdit.value = false
  const label = businessTypeLabels[businessType] || businessType
  form.value = { 
    code: '', 
    name: `${label}审批流程`, 
    business_type: businessType, 
    amount_threshold: null, 
    description: '', 
    is_active: true 
  }
  dialogVisible.value = true
}

const editWorkflow = (workflow) => {
  isEdit.value = true
  form.value = { ...workflow }
  dialogVisible.value = true
}

const saveWorkflow = async () => {
  await formRef.value.validate()
  saving.value = true
  try {
    if (isEdit.value) {
      await updateWorkflowDefinition(form.value.id, form.value)
      ElMessage.success('更新成功')
      // 更新选中的流程
      if (selectedWorkflow.value?.id === form.value.id) {
        selectedWorkflow.value = { ...selectedWorkflow.value, ...form.value }
      }
    } else {
      const res = await createWorkflowDefinition(form.value)
      ElMessage.success('创建成功')
      // 选中新创建的流程
      selectedWorkflow.value = res
    }
    dialogVisible.value = false
    loadWorkflows()
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '操作失败')
  } finally {
    saving.value = false
  }
}

const toggleStatus = async (workflow) => {
  try {
    await updateWorkflowDefinition(workflow.id, { ...workflow, is_active: !workflow.is_active })
    ElMessage.success(workflow.is_active ? '已停用' : '已启用')
    workflow.is_active = !workflow.is_active
    loadWorkflows()
  } catch (error) {
    ElMessage.error('操作失败')
  }
}

const deleteWorkflow = async (workflow) => {
  try {
    await ElMessageBox.confirm(`确定要删除流程"${workflow.name}"吗？此操作不可恢复。`, '删除确认', { type: 'warning' })
    await deleteWorkflowDefinition(workflow.id)
    ElMessage.success('删除成功')
    selectedWorkflow.value = null
    loadWorkflows()
  } catch (error) {
    if (error !== 'cancel') ElMessage.error('删除失败')
  }
}

const selectApproverType = (type) => {
  stepForm.value.approver_type = type
  stepForm.value.approver = null
  stepForm.value.role = null
}

const addStep = async () => {
  isEditStep.value = false
  stepForm.value = { name: '', approver_type: 'USER', approver: null, role: null, can_reject: true, timeout_days: 3, cc_users: [], cc_roles: [] }
  await loadUsersAndRoles()
  stepDialogVisible.value = true
}

const editStep = async (step) => {
  isEditStep.value = true
  stepForm.value = { 
    ...step,
    approver: step.approver_user || null,
    role: step.approver_role || null,
    timeout_days: Math.ceil((step.timeout_hours || 24) / 24),
    cc_users: step.cc_users || [],
    cc_roles: step.cc_roles || []
  }
  await loadUsersAndRoles()
  stepDialogVisible.value = true
}

const saveStep = async () => {
  await stepFormRef.value.validate()
  if (stepForm.value.approver_type === 'USER' && !stepForm.value.approver) {
    ElMessage.error('请选择审批人')
    return
  }
  if (stepForm.value.approver_type === 'ROLE' && !stepForm.value.role) {
    ElMessage.error('请选择角色')
    return
  }
  stepSaving.value = true
  try {
    const formData = stepForm.value
    const data = { 
      name: formData.name,
      workflow: selectedWorkflow.value.id,
      step_order: isEditStep.value ? (formData.step_order || formData.order) : steps.value.length + 1,
      approver_type: formData.approver_type,
      approver_user: formData.approver_type === 'USER' ? formData.approver : null,
      approver_role: formData.approver_type === 'ROLE' ? formData.role : null,
      action_type: formData.action_type || 'APPROVE',
      timeout_hours: (formData.timeout_days || 3) * 24,
      can_reject: formData.can_reject !== false,
      cc_users: formData.cc_users || [],
      cc_roles: formData.cc_roles || []
    }
    if (isEditStep.value) {
      await updateWorkflowStep(stepForm.value.id, data)
    } else {
      await createWorkflowStep(data)
    }
    ElMessage.success(isEditStep.value ? '更新成功' : '添加成功')
    stepDialogVisible.value = false
    await loadSteps()
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '操作失败')
  } finally {
    stepSaving.value = false
  }
}

const deleteStep = async (step) => {
  try {
    await ElMessageBox.confirm('确定要删除此审批步骤吗？', '提示', { type: 'warning' })
    await deleteWorkflowStep(step.id)
    ElMessage.success('删除成功')
    await loadSteps()
  } catch (error) {
    if (error !== 'cancel') ElMessage.error('删除失败')
  }
}

const moveStep = async (index, direction) => {
  const newIndex = index + direction
  if (newIndex < 0 || newIndex >= steps.value.length) return
  const step1 = steps.value[index]
  const step2 = steps.value[newIndex]
  try {
    await Promise.all([
      updateWorkflowStep(step1.id, { ...step1, step_order: step2.step_order }),
      updateWorkflowStep(step2.id, { ...step2, step_order: step1.step_order })
    ])
    await loadSteps()
  } catch (error) {
    ElMessage.error('移动失败')
  }
}

onMounted(() => {
  loadWorkflows()
})
</script>


<style scoped>
.workflow-config-sap {
  height: calc(100vh - 120px);
  display: flex;
  flex-direction: column;
  background: #f0f2f5;
}

.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 20px;
  background: #fff;
  border-bottom: 1px solid #e8e8e8;
}

.toolbar-left {
  display: flex;
  gap: 10px;
}

.main-content {
  flex: 1;
  display: flex;
  gap: 1px;
  background: #e8e8e8;
  overflow: hidden;
}

/* 左侧面板 */
.workflow-list-panel {
  width: 320px;
  background: #fff;
  display: flex;
  flex-direction: column;
}

.panel-header {
  padding: 15px 20px;
  border-bottom: 1px solid #e8e8e8;
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-weight: 600;
  color: #1f2937;
}

.workflow-tree {
  flex: 1;
  overflow: auto;
  padding: 10px;
}

.workflow-tree :deep(.el-tree-node__content) {
  height: auto;
  padding: 8px 0;
}

.tree-node {
  flex: 1;
  display: flex;
  align-items: center;
}

.tree-node.is-workflow {
  padding: 5px 10px;
  border-radius: 6px;
  margin: 2px 0;
  transition: all 0.2s;
}

.tree-node.is-workflow:hover {
  background: #f5f7fa;
}

.node-content {
  display: flex;
  align-items: center;
  gap: 8px;
  flex: 1;
}

.folder-icon {
  color: #e6a23c;
  font-size: 18px;
}

.workflow-icon {
  color: #409eff;
  font-size: 16px;
}

.node-label {
  flex: 1;
  font-size: 14px;
}

/* 右侧面板 */
.workflow-detail-panel {
  flex: 1;
  background: #fff;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.detail-header {
  padding: 20px 25px;
  border-bottom: 1px solid #e8e8e8;
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: #fff;
}

.header-info h2 {
  margin: 0 0 8px;
  font-size: 22px;
  font-weight: 600;
}

.header-meta {
  display: flex;
  align-items: center;
  gap: 10px;
}

.header-meta .code {
  opacity: 0.9;
  font-size: 13px;
}

.header-actions {
  display: flex;
  gap: 8px;
}

.header-actions .el-button {
  background: rgba(255,255,255,0.2);
  border-color: rgba(255,255,255,0.3);
  color: #fff;
}

.header-actions .el-button:hover {
  background: rgba(255,255,255,0.3);
}

/* 属性卡片 */
.property-cards {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 15px;
  padding: 20px 25px;
  background: #fafafa;
  border-bottom: 1px solid #e8e8e8;
}

.prop-card {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 15px;
  background: #fff;
  border-radius: 8px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.08);
}

.prop-icon {
  width: 45px;
  height: 45px;
  border-radius: 10px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  font-size: 20px;
}

.prop-label {
  font-size: 12px;
  color: #909399;
  margin-bottom: 4px;
}

.prop-value {
  font-size: 16px;
  font-weight: 600;
  color: #1f2937;
}

/* 流程设计器 */
.flow-designer {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.designer-header {
  padding: 15px 25px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-bottom: 1px solid #e8e8e8;
}

.designer-header .title {
  font-size: 16px;
  font-weight: 600;
  color: #1f2937;
}

.flow-canvas {
  flex: 1;
  padding: 30px;
  overflow: auto;
  display: flex;
  align-items: flex-start;
  gap: 0;
  background: 
    linear-gradient(90deg, #f0f0f0 1px, transparent 1px),
    linear-gradient(#f0f0f0 1px, transparent 1px);
  background-size: 20px 20px;
}

/* 流程节点 */
.flow-node {
  display: flex;
  flex-direction: column;
  align-items: center;
  flex-shrink: 0;
}

.node-circle {
  width: 50px;
  height: 50px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 24px;
  color: #fff;
}

.node-circle.start {
  background: linear-gradient(135deg, #67c23a 0%, #5daf34 100%);
}

.node-circle.end {
  background: linear-gradient(135deg, #409eff 0%, #337ecc 100%);
}

.flow-node .node-label {
  margin-top: 8px;
  font-size: 12px;
  color: #606266;
}

.flow-connector {
  width: 60px;
  height: 2px;
  background: #dcdfe6;
  margin: 24px 0;
  position: relative;
  flex-shrink: 0;
}

.flow-connector::after {
  content: '';
  position: absolute;
  right: -6px;
  top: -4px;
  border: 5px solid transparent;
  border-left-color: #dcdfe6;
}

/* 步骤节点 */
.step-node .node-box {
  width: 280px;
  background: #fff;
  border: 2px solid #e4e7ed;
  border-radius: 8px;
  overflow: hidden;
  transition: all 0.3s;
  position: relative;
}

.step-node:hover .node-box,
.step-node.is-selected .node-box {
  border-color: #409eff;
  box-shadow: 0 4px 12px rgba(64, 158, 255, 0.2);
}

.node-header {
  padding: 12px 15px;
  background: #f5f7fa;
  display: flex;
  align-items: center;
  gap: 10px;
  border-bottom: 1px solid #e4e7ed;
}

.step-order {
  width: 24px;
  height: 24px;
  background: #409eff;
  color: #fff;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 600;
}

.step-name {
  flex: 1;
  font-weight: 600;
  color: #1f2937;
}

.node-actions {
  display: flex;
  gap: 8px;
  opacity: 0;
  transition: opacity 0.2s;
}

.step-node:hover .node-actions {
  opacity: 1;
}

.action-icon {
  cursor: pointer;
  color: #909399;
  transition: color 0.2s;
}

.action-icon:hover {
  color: #409eff;
}

.action-icon.delete:hover {
  color: #f56c6c;
}

.node-body {
  padding: 15px;
}

.approver-info {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
  color: #606266;
}

.step-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.sort-buttons {
  position: absolute;
  right: -40px;
  top: 50%;
  transform: translateY(-50%);
  display: flex;
  flex-direction: column;
  gap: 5px;
  opacity: 0;
  transition: opacity 0.2s;
}

.step-node:hover .sort-buttons {
  opacity: 1;
}

.empty-flow {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
}

.no-selection {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
}

/* 审批人类型选择器 */
.approver-type-selector {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
}

.type-option {
  padding: 15px;
  border: 2px solid #e4e7ed;
  border-radius: 8px;
  cursor: pointer;
  text-align: center;
  transition: all 0.2s;
}

.type-option:hover {
  border-color: #c0c4cc;
}

.type-option.is-selected {
  border-color: #409eff;
  background: #ecf5ff;
}

.type-option .el-icon {
  color: #409eff;
  margin-bottom: 8px;
}

.type-label {
  font-weight: 600;
  color: #1f2937;
  margin-bottom: 4px;
}

.type-desc {
  font-size: 12px;
  color: #909399;
}

.user-option {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.user-dept {
  font-size: 12px;
  color: #909399;
}

.form-tip {
  font-size: 12px;
  color: #909399;
  margin-top: 4px;
}

:deep(.el-divider__text) {
  font-size: 13px;
  color: #606266;
}
</style>
