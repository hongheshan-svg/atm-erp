<template>
  <div class="drawing-bom-link">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>图纸-BOM关联管理</span>
          <div>
            <el-select v-model="projectId" placeholder="选择项目" filterable style="width: 300px; margin-right: 10px;" @change="loadData">
              <el-option v-for="p in projects" :key="p.id" :label="`${p.code} - ${p.name}`" :value="p.id" />
            </el-select>
            <el-button type="primary" @click="autoLink" :loading="linking" :disabled="!projectId">
              <el-icon><Connection /></el-icon> 一键自动关联
            </el-button>
          </div>
        </div>
      </template>

      <!-- 统计信息 -->
      <el-row :gutter="20" class="stats-row" v-if="projectId">
        <el-col :span="6">
          <el-statistic title="BOM项总数" :value="bomStats.total" />
        </el-col>
        <el-col :span="6">
          <el-statistic title="已关联图纸">
            <template #default>
              <span class="stat-linked">{{ bomStats.linked }}</span>
            </template>
          </el-statistic>
        </el-col>
        <el-col :span="6">
          <el-statistic title="未关联图纸">
            <template #default>
              <span class="stat-unlinked">{{ bomStats.unlinked }}</span>
            </template>
          </el-statistic>
        </el-col>
        <el-col :span="6">
          <el-statistic title="关联率">
            <template #default>
              <span>{{ bomStats.total > 0 ? ((bomStats.linked / bomStats.total) * 100).toFixed(1) : 0 }}%</span>
            </template>
          </el-statistic>
        </el-col>
      </el-row>
    </el-card>

    <!-- 主要内容区 -->
    <el-row :gutter="20" class="main-content" v-if="projectId">
      <!-- 左侧：BOM树形结构 -->
      <el-col :span="12">
        <el-card>
          <template #header>
            <div class="card-header">
              <span>BOM结构</span>
              <el-input v-model="bomSearch" placeholder="搜索BOM项..." style="width: 200px;" clearable>
                <template #prefix><el-icon><Search /></el-icon></template>
              </el-input>
            </div>
          </template>
          
          <el-tree
            ref="bomTreeRef"
            :data="bomTree"
            :props="treeProps"
            node-key="id"
            :filter-node-method="filterBomNode"
            :expand-on-click-node="false"
            default-expand-all
            highlight-current
            @node-click="handleBomNodeClick"
          >
            <template #default="{ node: _node, data }">
              <div class="tree-node" :class="{ 'has-drawing': data.has_drawing === 'YES', 'is-custom': data.is_custom_part }">
                <span class="node-content">
                  <el-tag v-if="data.is_custom_part" size="small" type="warning" style="margin-right: 5px;">
                    {{ getCustomPartLabel(data.custom_part_type) }}
                  </el-tag>
                  <span class="node-code">{{ data.item_code || data.item_sku }}</span>
                  <span class="node-name">{{ data.item_name }}</span>
                  <span class="node-qty">({{ data.planned_qty }})</span>
                </span>
                <span class="node-actions">
                  <el-icon v-if="data.has_drawing === 'YES'" class="linked-icon" title="已关联图纸">
                    <Link />
                  </el-icon>
                  <el-icon v-else class="unlinked-icon" title="未关联图纸">
                    <Close />
                  </el-icon>
                  <el-tag v-if="data.drawing_no" size="small" type="info">
                    {{ data.drawing_no }}
                  </el-tag>
                </span>
              </div>
            </template>
          </el-tree>
        </el-card>
      </el-col>

      <!-- 右侧：图纸列表 -->
      <el-col :span="12">
        <el-card>
          <template #header>
            <div class="card-header">
              <span>图纸列表</span>
              <el-input v-model="drawingSearch" placeholder="搜索图纸..." style="width: 200px;" clearable>
                <template #prefix><el-icon><Search /></el-icon></template>
              </el-input>
            </div>
          </template>

          <!-- 批量操作 -->

          <div v-if="selectedRows.length > 0" class="batch-toolbar">

            <span class="batch-info">已选择 {{ selectedRows.length }} 项</span>

            <el-button type="danger" size="small" @click="batchDelete">批量删除</el-button>

            <el-button size="small" @click="batchExport">导出选中</el-button>

          </div>

          <el-table :data="filteredDrawings" border stripe max-height="500" @row-click="handleDrawingClick" @selection-change="handleSelectionChange">
            <el-table-column type="selection" width="45" />
            <el-table-column prop="drawing_no" label="图号" width="150" />
            <el-table-column prop="name" label="名称" min-width="150" show-overflow-tooltip />
            <el-table-column prop="version" label="版本" width="70" />
            <el-table-column prop="part_type" label="类型" width="90">
              <template #default="{ row }">
                <el-tag size="small">{{ getPartTypeLabel(row.part_type) }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="关联状态" width="100">
              <template #default="{ row }">
                <el-tag v-if="row.bom_item_id" type="success" size="small">
                  <el-icon><Link /></el-icon> 已关联
                </el-tag>
                <el-tag v-else type="info" size="small">
                  <el-icon><Close /></el-icon> 未关联
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="100" fixed="right">
              <template #default="{ row }">
                <el-button 
                  v-if="!row.bom_item_id && selectedBom" 
                  type="primary" 
                  size="small"
                  @click.stop="linkDrawingToBom(row)"
                >
                  关联
                </el-button>
                <el-button 
                  v-if="row.bom_item_id" 
                  type="danger" 
                  size="small"
                  @click.stop="unlinkDrawing(row)"
                >
                  解除
                </el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>
    </el-row>

    <!-- 关联预览 -->
    <el-card v-if="selectedBom && selectedDrawing" class="link-preview">
      <template #header>关联预览</template>
      <el-descriptions :column="2" border>
        <el-descriptions-item label="BOM项">
          {{ selectedBom.item_code || selectedBom.item_sku }} - {{ selectedBom.item_name }}
        </el-descriptions-item>
        <el-descriptions-item label="图纸">
          {{ selectedDrawing.drawing_no }} - {{ selectedDrawing.name }}
        </el-descriptions-item>
      </el-descriptions>
      <div class="link-actions">
        <el-button type="primary" @click="confirmLink">确认关联</el-button>
        <el-button @click="clearSelection">取消</el-button>
      </div>
    </el-card>

    <!-- 自动关联结果对话框 -->
    <el-dialog v-model="showLinkResult" title="自动关联结果" width="700px">
      <el-descriptions :column="3" border>
        <el-descriptions-item label="成功关联">{{ linkResult.linked || 0 }}</el-descriptions-item>
        <el-descriptions-item label="已有关联">{{ linkResult.already_linked || 0 }}</el-descriptions-item>
        <el-descriptions-item label="未匹配">{{ linkResult.not_found || 0 }}</el-descriptions-item>
      </el-descriptions>

      <el-table :data="linkResult.details || []" border stripe max-height="400" style="margin-top: 20px;">
        <el-table-column prop="drawing_no" label="图号" width="150" />
        <el-table-column prop="match_type" label="匹配类型" width="120">
          <template #default="{ row }">
            <el-tag :type="getMatchTypeColor(row.match_type)" size="small">
              {{ getMatchTypeLabel(row.match_type) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="item_sku" label="关联物料" min-width="150" />
        <el-table-column prop="score" label="匹配度" width="80">
          <template #default="{ row }">
            {{ row.score ? (row.score * 100).toFixed(0) + '%' : '-' }}
          </template>
        </el-table-column>
      </el-table>

      <template #footer>
        <el-button type="primary" @click="showLinkResult = false; loadData()">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Connection, Link, Close, Search } from '@element-plus/icons-vue'
import { getDrawingList, patchDrawing, autoLinkDrawings, manualLinkDrawing, getCreoBOMTree } from '@/api/projects/drawing'
import { getProjectList } from '@/api/projects/project'
import { useBatchOperation } from '@/composables/useBatchOperation'

const { selectedRows, handleSelectionChange, batchDelete, batchExport } = useBatchOperation('/api/projects_drawing/')


const projects = ref([])
const projectId = ref(null)
const bomTree = ref([])
const drawings = ref([])
const linking = ref(false)
const showLinkResult = ref(false)
const linkResult = ref({})

const bomSearch = ref('')
const drawingSearch = ref('')
const selectedBom = ref(null)
const selectedDrawing = ref(null)
const bomTreeRef = ref(null)

const treeProps = {
  children: 'children',
  label: 'item_name'
}

const bomStats = computed(() => {
  const countNodes = (nodes) => {
    let total = 0, linked = 0
    for (const node of nodes) {
      total++
      if (node.has_drawing === 'YES') linked++
      if (node.children?.length) {
        const sub = countNodes(node.children)
        total += sub.total
        linked += sub.linked
      }
    }
    return { total, linked }
  }
  
  const result = countNodes(bomTree.value)
  return {
    total: result.total,
    linked: result.linked,
    unlinked: result.total - result.linked
  }
})

const filteredDrawings = computed(() => {
  if (!drawingSearch.value) return drawings.value
  const search = drawingSearch.value.toLowerCase()
  return drawings.value.filter(d => 
    d.drawing_no.toLowerCase().includes(search) ||
    d.name.toLowerCase().includes(search)
  )
})

const filterBomNode = (value, data) => {
  if (!value) return true
  const search = value.toLowerCase()
  return (data.item_code || '').toLowerCase().includes(search) ||
         (data.item_sku || '').toLowerCase().includes(search) ||
         (data.item_name || '').toLowerCase().includes(search)
}

watch(bomSearch, (val) => {
  bomTreeRef.value?.filter(val)
})

const loadProjects = async () => {
  try {
    const res = await getProjectList( { params: { page_size: 1000 } })
    projects.value = res.results || res || []
  } catch (error) {
    console.error('Load projects failed:', error)
  }
}

const loadData = async () => {
  if (!projectId.value) return
  try {
    await Promise.all([loadBomTree(), loadDrawings()])
  } catch (error) {
    console.error('加载数据失败', error)
    ElMessage.error('加载数据失败')
  }
}

const loadBomTree = async () => {
  try {
    const res = await getCreoBOMTree( {
      params: { project_id: projectId.value }
    })
    bomTree.value = res.tree || []
  } catch (error) {
    console.error('Load BOM tree failed:', error)
    bomTree.value = []
  }
}

const loadDrawings = async () => {
  try {
    const res = await getDrawingList( {
      params: { project: projectId.value, page_size: 1000 }
    })
    drawings.value = res.results || res || []
  } catch (error) {
    console.error('Load drawings failed:', error)
    drawings.value = []
  }
}

const autoLink = async () => {
  linking.value = true
  try {
    const res = await autoLinkDrawings( {
      project_id: projectId.value
    })
    linkResult.value = res
    showLinkResult.value = true
    ElMessage.success(`成功关联 ${res.linked || 0} 个图纸`)
  } catch (error) {
    ElMessage.error('自动关联失败')
  } finally {
    linking.value = false
  }
}

const handleBomNodeClick = (data) => {
  selectedBom.value = data
}

const handleDrawingClick = (row) => {
  selectedDrawing.value = row
}

const linkDrawingToBom = async (drawing) => {
  if (!selectedBom.value) {
    ElMessage.warning('请先在左侧选择BOM项')
    return
  }
  
  try {
    await manualLinkDrawing( {
      drawing_id: drawing.id,
      bom_id: selectedBom.value.id
    })
    ElMessage.success('关联成功')
    loadData()
    clearSelection()
  } catch (error) {
    ElMessage.error('关联失败')
  }
}

const unlinkDrawing = async (drawing) => {
  await ElMessageBox.confirm('确定要解除该图纸与BOM的关联吗?', '确认')
  try {
    await patchDrawing(drawing.id, {
      bom_item: null,
      item: null
    })
    ElMessage.success('已解除关联')
    loadData()
  } catch (error) {
    ElMessage.error('操作失败')
  }
}

const confirmLink = async () => {
  if (!selectedBom.value || !selectedDrawing.value) return
  await linkDrawingToBom(selectedDrawing.value)
}

const clearSelection = () => {
  selectedBom.value = null
  selectedDrawing.value = null
}

const getCustomPartLabel = (type) => {
  const labels = {
    'MACHINED': '机加',
    'SHEET_METAL': '钣金',
    'WELDING': '焊接',
    'ASSEMBLY': '组装',
    'CASTING': '铸造',
    'FORGING': '锻造',
    'PLASTIC': '塑料',
    'ELECTRICAL': '电气'
  }
  return labels[type] || type || '自制'
}

const getPartTypeLabel = (type) => {
  const labels = {
    'ASSEMBLY': '装配图',
    'PART': '零件图',
    'WELDMENT': '焊接图',
    'SHEET_METAL': '钣金图',
    'TOOLING': '工装图',
    'SCHEMATIC': '示意图',
    'ELECTRICAL': '电气图',
    'PNEUMATIC': '气动图',
    'LAYOUT': '布局图'
  }
  return labels[type] || type || '其他'
}

const getMatchTypeLabel = (type) => {
  const labels = {
    'EXACT_DRAWING_NO': '图号精确',
    'EXACT_SKU': 'SKU精确',
    'EXACT_ITEM_CODE': '物料编码精确',
    'PARTIAL': '部分匹配',
    'FUZZY': '模糊匹配',
    'NOT_FOUND': '未匹配'
  }
  return labels[type] || type
}

const getMatchTypeColor = (type) => {
  if (type?.startsWith('EXACT')) return 'success'
  if (type === 'PARTIAL') return 'warning'
  if (type === 'FUZZY') return 'info'
  return 'danger'
}

onMounted(() => {
  loadProjects()
})
</script>

<style scoped>
.drawing-bom-link {
  padding: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.stats-row {
  margin-top: 20px;
}

.stat-linked {
  color: #67c23a;
  font-weight: bold;
}

.stat-unlinked {
  color: #f56c6c;
  font-weight: bold;
}

.main-content {
  margin-top: 20px;
}

.tree-node {
  display: flex;
  justify-content: space-between;
  align-items: center;
  width: 100%;
  padding-right: 10px;
}

.tree-node.has-drawing {
  background: #f0f9eb;
}

.tree-node.is-custom .node-code {
  color: #e6a23c;
}

.node-content {
  display: flex;
  align-items: center;
  gap: 8px;
}

.node-code {
  font-weight: bold;
  color: #409eff;
}

.node-name {
  color: #606266;
}

.node-qty {
  color: #909399;
  font-size: 12px;
}

.node-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.linked-icon {
  color: #67c23a;
}

.unlinked-icon {
  color: #c0c4cc;
}

.link-preview {
  margin-top: 20px;
}

.link-actions {
  margin-top: 20px;
  text-align: center;
}
</style>
