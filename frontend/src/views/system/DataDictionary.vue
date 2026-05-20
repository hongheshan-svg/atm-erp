<template>
  <div class="data-dictionary-container">
    <div class="page-header">
      <h2>数据字典管理</h2>
      <div class="header-actions">
        <el-button type="primary" @click="showTypeDialog = true">
          <el-icon><Plus /></el-icon>
          新增字典类型
        </el-button>
        <el-button @click="handleInitSystemDicts" :loading="initLoading">
          初始化系统字典
        </el-button>
      </div>
    </div>

    <div class="content-wrapper">
      <!-- 左侧字典类型列表 -->
      <div class="type-list">
        <div class="search-box">
          <el-input v-model="typeSearch" placeholder="搜索字典类型" clearable>
            <template #prefix>
              <el-icon><Search /></el-icon>
            </template>
          </el-input>
        </div>
        <el-scrollbar height="calc(100vh - 280px)">
          <div 
            v-for="type in filteredTypes" 
            :key="type.id"
            class="type-item"
            :class="{ active: selectedType?.id === type.id }"
            @click="selectType(type)"
          >
            <div class="type-info">
              <span class="type-code">{{ type.code }}</span>
              <span class="type-name">{{ type.name }}</span>
            </div>
            <div class="type-meta">
              <el-tag v-if="type.is_system" size="small" type="info">系统</el-tag>
              <span class="items-count">{{ type.items_count }} 项</span>
            </div>
          </div>
        </el-scrollbar>
      </div>

      <!-- 右侧字典项列表 -->
      <div class="items-panel">
        <template v-if="selectedType">
          <div class="panel-header">
            <div class="type-detail">
              <h3>{{ selectedType.name }}</h3>
              <span class="code-badge">{{ selectedType.code }}</span>
            </div>
            <div class="panel-actions">
              <el-button type="primary" size="small" @click="showItemDialog = true">
                <el-icon><Plus /></el-icon>
                新增字典项
              </el-button>
              <el-button size="small" @click="editType(selectedType)">
                <el-icon><Edit /></el-icon>
                编辑
              </el-button>
              <el-button 
                size="small" 
                type="danger" 
                @click="deleteType(selectedType)"
                :disabled="selectedType.is_system"
              >
                <el-icon><Delete /></el-icon>
                删除
              </el-button>
            </div>
          </div>

          <!-- 批量操作 -->

          <div v-if="selectedRows.length > 0" class="batch-toolbar">

            <span class="batch-info">已选择 {{ selectedRows.length }} 项</span>

            <el-button type="danger" size="small" @click="batchDelete">批量删除</el-button>

            <el-button size="small" @click="batchExport">导出选中</el-button>

          </div>

          <el-table :data="dictItems" stripe style="width: 100%" @selection-change="handleSelectionChange">
            <el-table-column type="selection" width="45" />
            <el-table-column prop="value" label="值" width="150" />
            <el-table-column prop="label" label="显示标签" min-width="200" />
            <el-table-column label="颜色" width="100">
              <template #default="{ row }">
                <el-tag 
                  v-if="row.color" 
                  :color="row.color" 
                  size="small"
                  style="color: white;"
                >
                  {{ row.label }}
                </el-tag>
                <span v-else>-</span>
              </template>
            </el-table-column>
            <el-table-column prop="sort_order" label="排序" width="80" />
            <el-table-column label="默认" width="80">
              <template #default="{ row }">
                <el-tag v-if="row.is_default" type="success" size="small">是</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="状态" width="80">
              <template #default="{ row }">
                <el-tag :type="row.is_enabled ? 'success' : 'danger'" size="small">
                  {{ row.is_enabled ? '启用' : '禁用' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="200" fixed="right">
              <template #default="{ row }">
                <el-button size="small" text type="primary" @click="editItem(row)">编辑</el-button>
                <el-button size="small" text type="primary" @click="setDefault(row)">设为默认</el-button>
                <el-button size="small" text :type="row.is_enabled ? 'warning' : 'success'" @click="toggleItem(row)">
                  {{ row.is_enabled ? '禁用' : '启用' }}
                </el-button>
                <el-button size="small" text type="danger" @click="deleteItem(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </template>
        <template v-else>
          <el-empty description="请从左侧选择字典类型" />
        </template>
      </div>
    </div>

    <!-- 字典类型对话框 -->
    <el-dialog 
      v-model="showTypeDialog" 
      :title="editingType ? '编辑字典类型' : '新增字典类型'"
      width="500px"
    >
      <el-form :model="typeForm" label-width="100px">
        <el-form-item label="类型编码" required>
          <el-input v-model="typeForm.code" :disabled="editingType" />
        </el-form-item>
        <el-form-item label="类型名称" required>
          <el-input v-model="typeForm.name" />
        </el-form-item>
        <el-form-item label="排序">
          <el-input-number v-model="typeForm.sort_order" :min="0" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="typeForm.description" type="textarea" :rows="3" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showTypeDialog = false">取消</el-button>
        <el-button type="primary" @click="saveType" :loading="saving">保存</el-button>
      </template>
    </el-dialog>

    <!-- 字典项对话框 -->
    <el-dialog 
      v-model="showItemDialog" 
      :title="editingItem ? '编辑字典项' : '新增字典项'"
      width="500px"
    >
      <el-form :model="itemForm" label-width="100px">
        <el-form-item label="字典值" required>
          <el-input v-model="itemForm.value" />
        </el-form-item>
        <el-form-item label="显示标签" required>
          <el-input v-model="itemForm.label" />
        </el-form-item>
        <el-form-item label="颜色标识">
          <el-color-picker v-model="itemForm.color" />
        </el-form-item>
        <el-form-item label="排序">
          <el-input-number v-model="itemForm.sort_order" :min="0" />
        </el-form-item>
        <el-form-item label="是否默认">
          <el-switch v-model="itemForm.is_default" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="itemForm.description" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showItemDialog = false">取消</el-button>
        <el-button type="primary" @click="saveItem" :loading="saving">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Search, Edit, Delete } from '@element-plus/icons-vue'
import { getDictTypeList, createDictType, updateDictType, deleteDictType, initSystemDicts, getDictItemList, createDictItem, updateDictItem, deleteDictItem, setDictItemDefault, toggleDictItemEnable } from '@/api/system'
import { useBatchOperation } from '@/composables/useBatchOperation'

const { selectedRows, handleSelectionChange, batchDelete, batchExport } = useBatchOperation('/api/system/')


const dictTypes = ref([])
const dictItems = ref([])
const selectedType = ref(null)
const typeSearch = ref('')
const showTypeDialog = ref(false)
const showItemDialog = ref(false)
const editingType = ref(null)
const editingItem = ref(null)
const saving = ref(false)
const initLoading = ref(false)

const typeForm = ref({
  code: '',
  name: '',
  sort_order: 0,
  description: ''
})

const itemForm = ref({
  value: '',
  label: '',
  color: '',
  sort_order: 0,
  is_default: false,
  description: ''
})

const filteredTypes = computed(() => {
  if (!typeSearch.value) return dictTypes.value
  const search = typeSearch.value.toLowerCase()
  return dictTypes.value.filter(t => 
    t.code.toLowerCase().includes(search) || 
    t.name.toLowerCase().includes(search)
  )
})

const loadTypes = async () => {
  try {
    const res = await getDictTypeList()
    dictTypes.value = res.results || res || []
  } catch (e) {
    console.error('加载字典类型失败:', e)
  }
}

const selectType = async (type) => {
  selectedType.value = type
  try {
    const res = await getDictItemList({
      params: { dict_type: type.id }
    })
    dictItems.value = res.results || res || []
  } catch (e) {
    console.error('加载字典项失败:', e)
  }
}

const editType = (type) => {
  editingType.value = type
  typeForm.value = { ...type }
  showTypeDialog.value = true
}

const saveType = async () => {
  saving.value = true
  try {
    if (editingType.value) {
      await updateDictType(editingType.value.id, typeForm.value)
      ElMessage.success('更新成功')
    } else {
      await createDictType(typeForm.value)
      ElMessage.success('创建成功')
    }
    showTypeDialog.value = false
    editingType.value = null
    typeForm.value = { code: '', name: '', sort_order: 0, description: '' }
    loadTypes()
  } catch (e) {
    ElMessage.error('保存失败')
  } finally {
    saving.value = false
  }
}

const deleteType = async (type) => {
  if (type.is_system) {
    ElMessage.warning('系统字典类型不能删除')
    return
  }
  await ElMessageBox.confirm('确定要删除该字典类型吗？', '确认删除', { type: 'warning' })
  try {
    await deleteDictType(type.id)
    ElMessage.success('删除成功')
    selectedType.value = null
    dictItems.value = []
    loadTypes()
  } catch (e) {
    ElMessage.error('删除失败')
  }
}

const editItem = (item) => {
  editingItem.value = item
  itemForm.value = { ...item }
  showItemDialog.value = true
}

const saveItem = async () => {
  saving.value = true
  try {
    const data = { ...itemForm.value, dict_type: selectedType.value.id }
    if (editingItem.value) {
      await updateDictItem(editingItem.value.id, data)
      ElMessage.success('更新成功')
    } else {
      await createDictItem(data)
      ElMessage.success('创建成功')
    }
    showItemDialog.value = false
    editingItem.value = null
    itemForm.value = { value: '', label: '', color: '', sort_order: 0, is_default: false, description: '' }
    selectType(selectedType.value)
  } catch (e) {
    ElMessage.error('保存失败')
  } finally {
    saving.value = false
  }
}

const setDefault = async (item) => {
  try {
    await setDictItemDefault(item.id)
    ElMessage.success('设置成功')
    selectType(selectedType.value)
  } catch (e) {
    ElMessage.error('设置失败')
  }
}

const toggleItem = async (item) => {
  try {
    await toggleDictItemEnable(item.id)
    ElMessage.success('操作成功')
    selectType(selectedType.value)
  } catch (e) {
    ElMessage.error('操作失败')
  }
}

const deleteItem = async (item) => {
  await ElMessageBox.confirm('确定要删除该字典项吗？', '确认删除', { type: 'warning' })
  try {
    await deleteDictItem(item.id)
    ElMessage.success('删除成功')
    selectType(selectedType.value)
  } catch (e) {
    ElMessage.error('删除失败')
  }
}

const handleInitSystemDicts = async () => {
  initLoading.value = true
  try {
    const res = await initSystemDicts()
    ElMessage.success(res.message || '初始化成功')
    loadTypes()
  } catch (e) {
    ElMessage.error('初始化失败')
  } finally {
    initLoading.value = false
  }
}

onMounted(() => {
  loadTypes()
})
</script>

<style scoped lang="scss">
.data-dictionary-container {
  padding: 20px;
  background: #f5f7fa;
  min-height: 100vh;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
  
  h2 {
    margin: 0;
    color: #303133;
  }
}

.content-wrapper {
  display: flex;
  gap: 20px;
}

.type-list {
  width: 320px;
  background: white;
  border-radius: 8px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.1);
  padding: 16px;
  
  .search-box {
    margin-bottom: 16px;
  }
  
  .type-item {
    padding: 12px 16px;
    border-radius: 6px;
    cursor: pointer;
    margin-bottom: 8px;
    border: 1px solid #ebeef5;
    transition: all 0.3s;
    
    &:hover {
      background: #f5f7fa;
    }
    
    &.active {
      background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
      color: white;
      border-color: transparent;
      
      .type-code {
        color: rgba(255, 255, 255, 0.8);
      }
      
      .items-count {
        color: rgba(255, 255, 255, 0.7);
      }
    }
    
    .type-info {
      display: flex;
      flex-direction: column;
      gap: 4px;
    }
    
    .type-code {
      font-size: 12px;
      color: #909399;
      font-family: monospace;
    }
    
    .type-name {
      font-weight: 500;
    }
    
    .type-meta {
      display: flex;
      align-items: center;
      gap: 8px;
      margin-top: 8px;
    }
    
    .items-count {
      font-size: 12px;
      color: #909399;
    }
  }
}

.items-panel {
  flex: 1;
  background: white;
  border-radius: 8px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.1);
  padding: 20px;
  
  .panel-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 20px;
    padding-bottom: 16px;
    border-bottom: 1px solid #ebeef5;
    
    .type-detail {
      display: flex;
      align-items: center;
      gap: 12px;
      
      h3 {
        margin: 0;
      }
      
      .code-badge {
        padding: 4px 12px;
        background: #f0f0f0;
        border-radius: 4px;
        font-family: monospace;
        font-size: 13px;
        color: #606266;
      }
    }
  }
}
</style>
