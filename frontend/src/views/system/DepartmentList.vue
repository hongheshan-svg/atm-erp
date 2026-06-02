<template>
  <div class="department-management">
    <!-- 顶部工具栏 -->
    <div class="toolbar">
      <div class="toolbar-left">
        <el-button type="primary" v-permission="'accounts:department:create'" @click="handleAdd(null)">
          <el-icon><Plus /></el-icon>
          新建部门
        </el-button>
        <el-button @click="loadDepartments" :loading="loading">
          <el-icon><Refresh /></el-icon>
          刷新
        </el-button>
        <el-button @click="expandAll">
          <el-icon><Expand /></el-icon>
          全部展开
        </el-button>
        <el-button @click="collapseAll">
          <el-icon><Fold /></el-icon>
          全部折叠
        </el-button>
      </div>
      <div class="toolbar-right">
        <el-input v-model="searchText" placeholder="搜索部门..." clearable style="width: 200px" @input="handleSearch">
          <template #prefix><el-icon><Search /></el-icon></template>
        </el-input>
      </div>
    </div>

    <!-- 主内容区 -->
    <div class="main-content">
      <!-- 左侧：组织架构树 -->
      <div class="tree-panel">
        <div class="panel-header">
          <el-icon><OfficeBuilding /></el-icon>
          <span>组织架构</span>
        </div>
        
        <div class="tree-container" v-loading="loading">
          <el-tree
            ref="treeRef"
            :data="treeData"
            :props="treeProps"
            node-key="id"
            highlight-current
            :expand-on-click-node="false"
            :default-expand-all="true"
            :filter-node-method="filterNode"
            @node-click="handleNodeClick"
            class="dept-tree"
          >
            <template #default="{ node: _node, data }">
              <div class="tree-node">
                <div class="node-content">
                  <el-icon class="dept-icon" :class="{ 'has-children': data.children?.length }">
                    <component :is="data.children?.length ? 'Folder' : 'Document'" />
                  </el-icon>
                  <span class="node-name">{{ data.name }}</span>
                  <el-tag v-if="data.member_count" size="small" type="info" class="member-tag">
                    {{ data.member_count }}人
                  </el-tag>
                </div>
                <div class="node-actions">
                  <el-tooltip content="添加子部门" placement="top">
                    <el-icon class="action-btn" @click.stop="handleAdd(data)"><Plus /></el-icon>
                  </el-tooltip>
                  <el-tooltip content="编辑" placement="top">
                    <el-icon class="action-btn" @click.stop="handleEdit(data)"><Edit /></el-icon>
                  </el-tooltip>
                  <el-tooltip content="删除" placement="top">
                    <el-icon class="action-btn delete" @click.stop="handleDelete(data)"><Delete /></el-icon>
                  </el-tooltip>
                </div>
              </div>
            </template>
          </el-tree>
          
          <el-empty v-if="!loading && treeData.length === 0" description="暂无部门数据">
            <el-button type="primary" v-permission="'accounts:department:create'" @click="handleAdd(null)">创建第一个部门</el-button>
          </el-empty>
        </div>
      </div>

      <!-- 右侧：部门详情 -->
      <div class="detail-panel">
        <template v-if="selectedDept">
          <!-- 部门头部信息 -->
          <div class="detail-header">
            <div class="dept-avatar">
              <el-icon :size="32"><OfficeBuilding /></el-icon>
            </div>
            <div class="dept-info">
              <h2>{{ selectedDept.name }}</h2>
              <div class="dept-path">
                <el-breadcrumb separator="/">
                  <el-breadcrumb-item v-for="item in deptPath" :key="item.id">
                    {{ item.name }}
                  </el-breadcrumb-item>
                </el-breadcrumb>
              </div>
            </div>
            <div class="header-actions">
              <el-button v-permission="'accounts:department:edit'" @click="handleEdit(selectedDept)">编辑</el-button>
              <el-button type="danger" v-permission="'accounts:department:delete'" @click="handleDelete(selectedDept)">删除</el-button>
            </div>
          </div>

          <!-- 统计卡片 -->
          <div class="stat-cards">
            <div class="stat-card">
              <div class="stat-icon blue"><el-icon><User /></el-icon></div>
              <div class="stat-content">
                <div class="stat-value">{{ selectedDept.member_count || 0 }}</div>
                <div class="stat-label">直属成员</div>
              </div>
            </div>
            <div class="stat-card">
              <div class="stat-icon green"><el-icon><UserFilled /></el-icon></div>
              <div class="stat-content">
                <div class="stat-value">{{ selectedDept.total_member_count || 0 }}</div>
                <div class="stat-label">全部成员</div>
              </div>
            </div>
            <div class="stat-card">
              <div class="stat-icon orange"><el-icon><Folder /></el-icon></div>
              <div class="stat-content">
                <div class="stat-value">{{ selectedDept.children?.length || 0 }}</div>
                <div class="stat-label">子部门</div>
              </div>
            </div>
            <div class="stat-card">
              <div class="stat-icon purple"><el-icon><Avatar /></el-icon></div>
              <div class="stat-content">
                <div class="stat-value">{{ selectedDept.manager_name || '未设置' }}</div>
                <div class="stat-label">部门负责人</div>
              </div>
            </div>
          </div>

          <!-- 部门信息 -->
          <div class="info-section">
            <div class="section-header">
              <el-icon><InfoFilled /></el-icon>
              <span>基本信息</span>
            </div>
            <el-descriptions :column="2" border>
              <el-descriptions-item label="部门编号">{{ selectedDept.id }}</el-descriptions-item>
              <el-descriptions-item label="部门名称">{{ selectedDept.name }}</el-descriptions-item>
              <el-descriptions-item label="上级部门">{{ selectedDept.parent_name || '无（顶级部门）' }}</el-descriptions-item>
              <el-descriptions-item label="部门负责人">{{ selectedDept.manager_name || '未设置' }}</el-descriptions-item>
              <el-descriptions-item label="创建时间">{{ formatDate(selectedDept.created_at) }}</el-descriptions-item>
              <el-descriptions-item label="更新时间">{{ formatDate(selectedDept.updated_at) }}</el-descriptions-item>
              <el-descriptions-item label="部门描述" :span="2">{{ selectedDept.description || '暂无描述' }}</el-descriptions-item>
            </el-descriptions>
          </div>

          <!-- 部门成员 -->
          <div class="info-section">
            <div class="section-header">
              <el-icon><User /></el-icon>
              <span>部门成员</span>
              <el-button type="primary" size="small" style="margin-left: auto" @click="showAddMember">
                添加成员
              </el-button>
            </div>
            <!-- 批量操作 -->
            <div v-if="selectedRows.length > 0" class="batch-toolbar">
              <span class="batch-info">已选择 {{ selectedRows.length }} 项</span>
              <el-button type="danger" size="small" @click="batchDelete">批量删除</el-button>
              <el-button size="small" @click="batchExport">导出选中</el-button>
            </div>
            <el-table :data="deptMembers" v-loading="membersLoading" stripe size="small" @selection-change="handleSelectionChange">
              <el-table-column type="selection" width="45" />
              <el-table-column prop="username" label="用户名" width="120" />
              <el-table-column prop="display_name" label="姓名" width="120" />
              <el-table-column prop="email" label="邮箱" />
              <el-table-column prop="phone" label="电话" width="130" />
              <el-table-column label="角色" width="150">
                <template #default="{ row }">
                  <el-tag v-if="row.id === selectedDept.manager" type="warning" size="small">负责人</el-tag>
                  <el-tag v-else size="small">成员</el-tag>
                </template>
              </el-table-column>
            </el-table>
            <el-empty v-if="!membersLoading && deptMembers.length === 0" description="暂无成员" />
          </div>

          <!-- 子部门 -->
          <div class="info-section" v-if="selectedDept.children?.length">
            <div class="section-header">
              <el-icon><Folder /></el-icon>
              <span>子部门</span>
            </div>
            <div class="sub-dept-list">
              <div 
                v-for="child in selectedDept.children" 
                :key="child.id" 
                class="sub-dept-item"
                @click="selectDept(child)"
              >
                <el-icon><OfficeBuilding /></el-icon>
                <span class="sub-dept-name">{{ child.name }}</span>
                <el-tag size="small" type="info">{{ child.member_count || 0 }}人</el-tag>
                <el-icon class="arrow"><ArrowRight /></el-icon>
              </div>
            </div>
          </div>
        </template>

        <!-- 未选择部门 -->
        <div v-else class="no-selection">
          <el-empty description="请从左侧选择一个部门查看详情">
            <el-button type="primary" v-permission="'accounts:department:create'" @click="handleAdd(null)">或创建新部门</el-button>
          </el-empty>
        </div>
      </div>
    </div>

    <!-- 新增/编辑部门对话框 -->
    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="550px" destroy-on-close>
      <el-form :model="form" :rules="rules" ref="formRef" label-width="100px">
        <el-form-item label="部门名称" prop="name">
          <el-input v-model="form.name" placeholder="请输入部门名称" />
        </el-form-item>
        <el-form-item label="上级部门">
          <el-tree-select
            v-model="form.parent"
            :data="parentOptions"
            :props="{ label: 'name', value: 'id', children: 'children' }"
            placeholder="选择上级部门（留空为顶级部门）"
            clearable
            check-strictly
            :render-after-expand="false"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="部门负责人">
          <el-select v-model="form.manager" placeholder="选择负责人" clearable filterable style="width: 100%">
            <el-option
              v-for="user in users"
              :key="user.id"
              :label="getUserLabel(user)"
              :value="user.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="部门描述">
          <el-input v-model="form.description" type="textarea" :rows="3" placeholder="请输入部门描述" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSubmit" :loading="submitting">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { 
  Plus, Refresh, Search, OfficeBuilding, Folder, Document, Edit, Delete,
  User, UserFilled, Avatar, InfoFilled, ArrowRight, Expand, Fold
} from '@element-plus/icons-vue'
import { getDepartments, getUsers, createDepartment, updateDepartment, deleteDepartment } from '@/api/auth'
import { useBatchOperation } from '@/composables/useBatchOperation'

const { selectedRows, handleSelectionChange, batchDelete, batchExport } = useBatchOperation('/api/auth/')


// 状态
const loading = ref(false)
const submitting = ref(false)
const membersLoading = ref(false)
const departments = ref<any[]>([])
const users = ref<any[]>([])
const selectedDept = ref(null)
const deptMembers = ref<any[]>([])
const searchText = ref('')
const treeRef = ref(null)

// 对话框
const dialogVisible = ref(false)
const dialogTitle = ref('新建部门')
const isEdit = ref(false)
const formRef = ref(null)

const form = reactive({
  id: null,
  name: '',
  parent: null,
  manager: null,
  description: ''
})

const rules = {
  name: [{ required: true, message: '请输入部门名称', trigger: 'blur' }]
}

const treeProps = {
  label: 'name',
  children: 'children'
}

// 计算属性
const treeData = computed(() => {
  return buildTree(departments.value)
})

const parentOptions = computed(() => {
  // 编辑时排除自己和子部门
  if (isEdit.value && form.id) {
    return filterSelfAndChildren(treeData.value, form.id)
  }
  return treeData.value
})

const deptPath = computed(() => {
  if (!selectedDept.value) return []
  return getDeptPath(selectedDept.value.id, departments.value)
})

// 方法
const buildTree = (list, parentId = null) => {
  return list
    .filter(item => item.parent === parentId)
    .map(item => ({
      ...item,
      children: buildTree(list, item.id)
    }))
}

const filterSelfAndChildren = (tree, excludeId) => {
  return tree
    .filter(node => node.id !== excludeId)
    .map(node => ({
      ...node,
      children: node.children?.length ? filterSelfAndChildren(node.children, excludeId) : []
    }))
}

const getDeptPath = (deptId, list) => {
  const path = []
  let current = list.find(d => d.id === deptId)
  while (current) {
    path.unshift(current)
    current = list.find(d => d.id === current.parent)
  }
  return path
}

const findDeptInTree = (tree, id) => {
  for (const node of tree) {
    if (node.id === id) return node
    if (node.children?.length) {
      const found = findDeptInTree(node.children, id)
      if (found) return found
    }
  }
  return null
}

const formatDate = (dateStr) => {
  if (!dateStr) return '-'
  return new Date(dateStr).toLocaleString('zh-CN')
}

const getUserLabel = (user) => {
  return user.display_name ? `${user.display_name} (${user.username})` : user.username
}

const filterNode = (value, data) => {
  if (!value) return true
  return data.name.toLowerCase().includes(value.toLowerCase())
}

const handleSearch = () => {
  treeRef.value?.filter(searchText.value)
}

const expandAll = () => {
  const nodes = treeRef.value?.store?.nodesMap
  if (nodes) {
    Object.values(nodes).forEach(node => node.expand())
  }
}

const collapseAll = () => {
  const nodes = treeRef.value?.store?.nodesMap
  if (nodes) {
    Object.values(nodes).forEach(node => node.collapse())
  }
}

const loadDepartments = async () => {
  loading.value = true
  try {
    const response = await getDepartments()
    departments.value = response.results || response || []
  } catch (error) {
    ElMessage.error('加载部门失败')
  } finally {
    loading.value = false
  }
}

const loadUsers = async () => {
  try {
    const response = await getUsers()
    users.value = response.results || response || []
  } catch (error) {
    console.error('加载用户失败:', error)
  }
}

const loadDeptMembers = async (deptId) => {
  membersLoading.value = true
  try {
    const response = await getUsers({ department: deptId })
    deptMembers.value = response.results || response || []
  } catch (error) {
    deptMembers.value = []
  } finally {
    membersLoading.value = false
  }
}

const handleNodeClick = (data) => {
  selectedDept.value = data
  loadDeptMembers(data.id)
}

const selectDept = (dept) => {
  selectedDept.value = findDeptInTree(treeData.value, dept.id)
  loadDeptMembers(dept.id)
  // 在树中高亮
  treeRef.value?.setCurrentKey(dept.id)
}

const handleAdd = (parent) => {
  dialogTitle.value = parent ? `在"${parent.name}"下新建子部门` : '新建部门'
  isEdit.value = false
  Object.assign(form, { 
    id: null, 
    name: '', 
    parent: parent?.id || null, 
    manager: null, 
    description: '' 
  })
  dialogVisible.value = true
}

const handleEdit = (dept) => {
  dialogTitle.value = '编辑部门'
  isEdit.value = true
  Object.assign(form, {
    id: dept.id,
    name: dept.name,
    parent: dept.parent,
    manager: dept.manager,
    description: dept.description || ''
  })
  dialogVisible.value = true
}

const handleDelete = async (dept) => {
  if (dept.children?.length) {
    ElMessage.warning('该部门下有子部门，请先删除子部门')
    return
  }
  try {
    await ElMessageBox.confirm(`确定要删除部门"${dept.name}"吗？`, '删除确认', { type: 'warning' })
    await deleteDepartment(dept.id)
    ElMessage.success('删除成功')
    if (selectedDept.value?.id === dept.id) {
      selectedDept.value = null
    }
    loadDepartments()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('删除失败')
    }
  }
}

const handleSubmit = async () => {
  try {
    await formRef.value.validate()
    submitting.value = true
    if (isEdit.value) {
      await updateDepartment(form.id, form)
      ElMessage.success('更新成功')
    } else {
      await createDepartment(form)
      ElMessage.success('创建成功')
    }
    dialogVisible.value = false
    loadDepartments()
  } catch (error) {
    ElMessage.error('保存失败')
  } finally {
    submitting.value = false
  }
}

const showAddMember = () => {
  ElMessage.info('请在用户管理中设置用户的所属部门')
}

onMounted(() => {
  loadDepartments()
  loadUsers()
})
</script>


<style scoped>
.department-management {
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

/* 左侧树形面板 */
.tree-panel {
  width: 350px;
  background: #fff;
  display: flex;
  flex-direction: column;
}

.panel-header {
  padding: 15px 20px;
  border-bottom: 1px solid #e8e8e8;
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 600;
  color: #1f2937;
  font-size: 15px;
}

.panel-header .el-icon {
  color: #409eff;
  font-size: 18px;
}

.tree-container {
  flex: 1;
  overflow: auto;
  padding: 15px;
}

.dept-tree :deep(.el-tree-node__content) {
  height: auto;
  padding: 6px 0;
}

.tree-node {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 12px;
  border-radius: 6px;
  transition: all 0.2s;
}

.tree-node:hover {
  background: #f5f7fa;
}

.node-content {
  display: flex;
  align-items: center;
  gap: 8px;
  flex: 1;
}

.dept-icon {
  font-size: 16px;
  color: #909399;
}

.dept-icon.has-children {
  color: #e6a23c;
}

.node-name {
  font-size: 14px;
  color: #303133;
}

.member-tag {
  margin-left: 5px;
}

.node-actions {
  display: flex;
  gap: 8px;
  opacity: 0;
  transition: opacity 0.2s;
}

.tree-node:hover .node-actions {
  opacity: 1;
}

.action-btn {
  cursor: pointer;
  color: #909399;
  font-size: 14px;
  transition: color 0.2s;
}

.action-btn:hover {
  color: #409eff;
}

.action-btn.delete:hover {
  color: #f56c6c;
}

/* 右侧详情面板 */
.detail-panel {
  flex: 1;
  background: #fff;
  display: flex;
  flex-direction: column;
  overflow: auto;
}

.detail-header {
  padding: 25px 30px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: #fff;
  display: flex;
  align-items: center;
  gap: 20px;
}

.dept-avatar {
  width: 70px;
  height: 70px;
  background: rgba(255,255,255,0.2);
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.dept-info {
  flex: 1;
}

.dept-info h2 {
  margin: 0 0 8px;
  font-size: 24px;
  font-weight: 600;
}

.dept-path {
  opacity: 0.9;
}

.dept-path :deep(.el-breadcrumb__inner),
.dept-path :deep(.el-breadcrumb__separator) {
  color: rgba(255,255,255,0.8) !important;
}

.header-actions {
  display: flex;
  gap: 10px;
}

.header-actions .el-button {
  background: rgba(255,255,255,0.2);
  border-color: rgba(255,255,255,0.3);
  color: #fff;
}

.header-actions .el-button:hover {
  background: rgba(255,255,255,0.3);
}

/* 统计卡片 */
.stat-cards {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 20px;
  padding: 25px 30px;
  background: #fafafa;
  border-bottom: 1px solid #e8e8e8;
}

.stat-card {
  display: flex;
  align-items: center;
  gap: 15px;
  padding: 20px;
  background: #fff;
  border-radius: 10px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.06);
}

.stat-icon {
  width: 50px;
  height: 50px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 22px;
  color: #fff;
}

.stat-icon.blue { background: linear-gradient(135deg, #409eff 0%, #337ecc 100%); }
.stat-icon.green { background: linear-gradient(135deg, #67c23a 0%, #5daf34 100%); }
.stat-icon.orange { background: linear-gradient(135deg, #e6a23c 0%, #cf9236 100%); }
.stat-icon.purple { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); }

.stat-value {
  font-size: 22px;
  font-weight: 600;
  color: #1f2937;
}

.stat-label {
  font-size: 13px;
  color: #909399;
  margin-top: 4px;
}

/* 信息区块 */
.info-section {
  padding: 25px 30px;
  border-bottom: 1px solid #f0f0f0;
}

.section-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 15px;
  font-size: 16px;
  font-weight: 600;
  color: #1f2937;
}

.section-header .el-icon {
  color: #409eff;
}

/* 子部门列表 */
.sub-dept-list {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
  gap: 12px;
}

.sub-dept-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 15px;
  background: #f5f7fa;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s;
}

.sub-dept-item:hover {
  background: #ecf5ff;
  transform: translateX(5px);
}

.sub-dept-item .el-icon {
  color: #409eff;
}

.sub-dept-name {
  flex: 1;
  font-weight: 500;
}

.sub-dept-item .arrow {
  color: #c0c4cc;
}

.no-selection {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
}
</style>
