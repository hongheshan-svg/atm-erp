<template>
  <div class="location-list">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>库位管理</span>
          <div class="header-actions">
            <el-select v-model="selectedWarehouse" placeholder="选择仓库" style="width: 200px; margin-right: 10px;" @change="loadLocations">
              <el-option v-for="w in warehouses" :key="w.id" :label="w.name" :value="w.id" />
            </el-select>
            <el-button type="primary" :icon="Plus" v-permission="'masterdata:warehouse_location:create'" @click="handleAdd" :disabled="!selectedWarehouse">新增库位</el-button>
          </div>
        </div>
      </template>

      <div class="content-wrapper" v-if="selectedWarehouse">
        <!-- Tree view on left -->
        <div class="tree-panel">
          <el-input v-model="filterText" placeholder="搜索库位" class="mb-10" />
          <el-tree
            ref="treeRef"
            :data="locationTree"
            :props="treeProps"
            node-key="id"
            :filter-node-method="filterNode"
            :expand-on-click-node="false"
            @node-click="handleNodeClick"
            highlight-current
            default-expand-all
          >
            <template #default="{ node: _node, data }">
              <span class="tree-node">
                <el-tag :type="getTypeTagType(data.location_type)" size="small">{{ data.type_display }}</el-tag>
                <span class="node-label">{{ data.code }} - {{ data.name }}</span>
              </span>
            </template>
          </el-tree>
        </div>

        <!-- Detail panel on right -->
        <div class="detail-panel">
          <template v-if="selectedLocation">
            <el-descriptions title="库位详情" :column="2" border>
              <el-descriptions-item label="库位编码">{{ selectedLocation.code }}</el-descriptions-item>
              <el-descriptions-item label="库位名称">{{ selectedLocation.name }}</el-descriptions-item>
              <el-descriptions-item label="完整路径">{{ selectedLocation.full_path }}</el-descriptions-item>
              <el-descriptions-item label="库位类型">{{ selectedLocation.type_display }}</el-descriptions-item>
              <el-descriptions-item label="最大承重">{{ selectedLocation.max_weight || '-' }} kg</el-descriptions-item>
              <el-descriptions-item label="最大容积">{{ selectedLocation.max_volume || '-' }} m³</el-descriptions-item>
              <el-descriptions-item label="可拣货">
                <el-tag :type="selectedLocation.is_pickable ? 'success' : 'info'">
                  {{ selectedLocation.is_pickable ? '是' : '否' }}
                </el-tag>
              </el-descriptions-item>
              <el-descriptions-item label="可存储">
                <el-tag :type="selectedLocation.is_storable ? 'success' : 'info'">
                  {{ selectedLocation.is_storable ? '是' : '否' }}
                </el-tag>
              </el-descriptions-item>
              <el-descriptions-item label="状态">
                <el-tag :type="selectedLocation.is_active ? 'success' : 'danger'">
                  {{ selectedLocation.is_active ? '启用' : '禁用' }}
                </el-tag>
              </el-descriptions-item>
              <el-descriptions-item label="备注">{{ selectedLocation.notes || '-' }}</el-descriptions-item>
            </el-descriptions>

            <div class="action-buttons">
              <el-button type="primary" v-permission="'masterdata:warehouse_location:edit'" @click="handleEdit(selectedLocation)">编辑</el-button>
              <el-button type="success" v-permission="'masterdata:warehouse_location:create'" @click="handleAddChild(selectedLocation)">添加下级</el-button>
              <el-button type="danger" v-permission="'masterdata:warehouse_location:delete'" @click="handleDelete(selectedLocation)">删除</el-button>
            </div>

            <!-- Child locations table -->
            <!-- 批量操作 -->
            <div v-if="selectedRows.length > 0" class="batch-toolbar">
              <span class="batch-info">已选择 {{ selectedRows.length }} 项</span>
              <el-button type="danger" size="small" @click="batchDelete">批量删除</el-button>
              <el-button size="small" @click="batchExport">导出选中</el-button>
            </div>
            <el-table :data="childLocations" border style="margin-top: 20px;" v-if="childLocations.length > 0" @selection-change="handleSelectionChange">
              <el-table-column type="selection" width="45" />
              <el-table-column prop="code" label="编码" width="120" />
              <el-table-column prop="name" label="名称" />
              <el-table-column prop="type_display" label="类型" width="100" />
              <el-table-column prop="is_active" label="状态" width="80">
                <template #default="{ row }">
                  <el-tag :type="row.is_active ? 'success' : 'danger'" size="small">
                    {{ row.is_active ? '启用' : '禁用' }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column label="操作" width="120">
                <template #default="{ row }">
                  <el-button type="primary" link @click="handleNodeClick(row)">查看</el-button>
                </template>
              </el-table-column>
            </el-table>
          </template>
          <el-empty v-else description="请选择库位查看详情" />
        </div>
      </div>
      <el-empty v-else description="请先选择仓库" />
    </el-card>

    <!-- Add/Edit Dialog -->
    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="500px">
      <el-form ref="formRef" :model="form" :rules="rules" label-width="100px">
        <el-form-item label="库位编码" prop="code">
          <el-input v-model="form.code" placeholder="请输入库位编码" />
        </el-form-item>
        <el-form-item label="库位名称" prop="name">
          <el-input v-model="form.name" placeholder="请输入库位名称" />
        </el-form-item>
        <el-form-item label="库位类型" prop="location_type">
          <el-select v-model="form.location_type" style="width: 100%;">
            <el-option label="区域" value="ZONE" />
            <el-option label="通道" value="AISLE" />
            <el-option label="货架" value="RACK" />
            <el-option label="层" value="SHELF" />
            <el-option label="库位" value="BIN" />
          </el-select>
        </el-form-item>
        <el-form-item label="上级库位">
          <el-tree-select
            v-model="form.parent"
            :data="locationTree"
            :props="{ label: 'name', value: 'id', children: 'children' }"
            placeholder="选择上级库位（可选）"
            clearable
            check-strictly
            style="width: 100%;"
          />
        </el-form-item>
        <el-form-item label="最大承重">
          <el-input-number v-model="form.max_weight" :min="0" :precision="2" placeholder="kg" />
          <span class="unit-label">kg</span>
        </el-form-item>
        <el-form-item label="最大容积">
          <el-input-number v-model="form.max_volume" :min="0" :precision="2" placeholder="m³" />
          <span class="unit-label">m³</span>
        </el-form-item>
        <el-form-item label="可拣货">
          <el-switch v-model="form.is_pickable" />
        </el-form-item>
        <el-form-item label="可存储">
          <el-switch v-model="form.is_storable" />
        </el-form-item>
        <el-form-item label="启用">
          <el-switch v-model="form.is_active" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="form.notes" type="textarea" rows="2" />
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
import { ref, reactive, watch, onMounted } from 'vue'
import { Plus } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getWarehouseList, getLocationTree, getLocation, getLocationChildren, createLocation, patchLocation, deleteLocation } from '@/api/masterdata'
import { useBatchOperation } from '@/composables/useBatchOperation'

const { selectedRows, handleSelectionChange, batchDelete, batchExport } = useBatchOperation('/api/masterdata/locations/', { onSuccess: () => selectedLocation.value && handleNodeClick(selectedLocation.value) })


const warehouses = ref<any[]>([])
const selectedWarehouse = ref(null)
const locationTree = ref<any[]>([])
const selectedLocation = ref(null)
const childLocations = ref<any[]>([])
const filterText = ref('')
const treeRef = ref(null)

const dialogVisible = ref(false)
const dialogTitle = ref('')
const submitting = ref(false)
const formRef = ref(null)
const isEdit = ref(false)

const form = reactive({
  id: null,
  code: '',
  name: '',
  location_type: 'BIN',
  parent: null,
  max_weight: null,
  max_volume: null,
  is_pickable: true,
  is_storable: true,
  is_active: true,
  notes: ''
})

const rules = {
  code: [{ required: true, message: '请输入库位编码', trigger: 'blur' }],
  name: [{ required: true, message: '请输入库位名称', trigger: 'blur' }],
  location_type: [{ required: true, message: '请选择库位类型', trigger: 'change' }]
}

const treeProps = {
  children: 'children',
  label: 'name'
}

watch(filterText, (val) => {
  treeRef.value?.filter(val)
})

const filterNode = (value, data) => {
  if (!value) return true
  return data.name.includes(value) || data.code.includes(value)
}

const getTypeTagType = (type) => {
  const types = {
    'ZONE': 'danger',
    'AISLE': 'warning',
    'RACK': 'primary',
    'SHELF': 'success',
    'BIN': 'info'
  }
  return types[type] || 'info'
}

const loadWarehouses = async () => {
  try {
    const response = await getWarehouseList({ is_active: true })
    warehouses.value = response.results || response || [] || []
  } catch (error) {
    console.error('加载仓库失败:', error)
  }
}

const loadLocations = async () => {
  if (!selectedWarehouse.value) return
  
  try {
    const response = await getLocationTree(selectedWarehouse.value)
    locationTree.value = response || []
    selectedLocation.value = null
    childLocations.value = []
  } catch (error) {
    console.error('加载库位失败:', error)
  }
}

const handleNodeClick = async (data) => {
  try {
    const detail = await getLocation(data.id)
    selectedLocation.value = detail
    
    // Load children
    const children = await getLocationChildren(data.id)
    childLocations.value = children || []
  } catch (error) {
    console.error('加载库位详情失败:', error)
  }
}

const resetForm = () => {
  form.id = null
  form.code = ''
  form.name = ''
  form.location_type = 'BIN'
  form.parent = null
  form.max_weight = null
  form.max_volume = null
  form.is_pickable = true
  form.is_storable = true
  form.is_active = true
  form.notes = ''
}

const handleAdd = () => {
  resetForm()
  isEdit.value = false
  dialogTitle.value = '新增库位'
  dialogVisible.value = true
}

const handleAddChild = (parent) => {
  resetForm()
  form.parent = parent.id
  isEdit.value = false
  dialogTitle.value = `新增下级库位 - ${parent.name}`
  dialogVisible.value = true
}

const handleEdit = (location) => {
  form.id = location.id
  form.code = location.code
  form.name = location.name
  form.location_type = location.location_type
  form.parent = location.parent
  form.max_weight = location.max_weight
  form.max_volume = location.max_volume
  form.is_pickable = location.is_pickable
  form.is_storable = location.is_storable
  form.is_active = location.is_active
  form.notes = location.notes
  isEdit.value = true
  dialogTitle.value = '编辑库位'
  dialogVisible.value = true
}

const handleSubmit = async () => {
  await formRef.value?.validate()
  
  submitting.value = true
  try {
    const payload = {
      warehouse: selectedWarehouse.value,
      code: form.code,
      name: form.name,
      location_type: form.location_type,
      parent: form.parent,
      max_weight: form.max_weight,
      max_volume: form.max_volume,
      is_pickable: form.is_pickable,
      is_storable: form.is_storable,
      is_active: form.is_active,
      notes: form.notes
    }
    
    if (isEdit.value) {
      await patchLocation(form.id, payload)
      ElMessage.success('更新成功')
    } else {
      await createLocation(payload)
      ElMessage.success('创建成功')
    }
    
    dialogVisible.value = false
    loadLocations()
  } catch (error) {
    console.error('保存失败:', error)
    ElMessage.error('保存失败')
  } finally {
    submitting.value = false
  }
}

const handleDelete = async (location) => {
  try {
    await ElMessageBox.confirm(`确定要删除库位 "${location.name}" 吗？`, '确认删除', {
      type: 'warning'
    })
    
    await deleteLocation(location.id)
    ElMessage.success('删除成功')
    selectedLocation.value = null
    loadLocations()
  } catch (error) {
    if (error !== 'cancel') {
      console.error('删除失败:', error)
      ElMessage.error('删除失败')
    }
  }
}

onMounted(() => {
  loadWarehouses()
})
</script>

<style scoped>
.location-list {
  padding: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.header-actions {
  display: flex;
  align-items: center;
}

.content-wrapper {
  display: flex;
  gap: 20px;
}

.tree-panel {
  width: 300px;
  flex-shrink: 0;
  border-right: 1px solid #eee;
  padding-right: 20px;
}

.detail-panel {
  flex: 1;
}

.tree-node {
  display: flex;
  align-items: center;
  gap: 8px;
}

.node-label {
  font-size: 13px;
}

.action-buttons {
  margin-top: 20px;
  display: flex;
  gap: 10px;
}

.mb-10 {
  margin-bottom: 10px;
}

.unit-label {
  margin-left: 8px;
  color: #999;
}
</style>

