<template>
  <div class="bom-compare">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>BOM版本对比</span>
        </div>
      </template>

      <!-- 对比设置 -->
      <el-form :inline="true" class="compare-form">
        <el-form-item label="项目">
          <el-select v-model="compareForm.project_id" placeholder="选择项目" filterable @change="loadSnapshots">
            <el-option v-for="p in projects" :key="p.id" :label="`${p.code} - ${p.name}`" :value="p.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="对比方式">
          <el-radio-group v-model="compareMode">
            <el-radio value="snapshot">快照对比</el-radio>
            <el-radio value="cad">CAD导入对比</el-radio>
          </el-radio-group>
        </el-form-item>
      </el-form>

      <!-- 快照对比 -->
      <template v-if="compareMode === 'snapshot'">
        <el-row :gutter="20" class="snapshot-select">
          <el-col :span="10">
            <el-card shadow="never">
              <template #header>原版本（基准）</template>
              <el-select v-model="compareForm.snapshot_id_1" placeholder="选择快照" style="width: 100%;">
                <el-option 
                  v-for="s in snapshots" 
                  :key="s.id" 
                  :label="`${s.name} (${s.item_count}项)`" 
                  :value="s.id"
                />
              </el-select>
              <div v-if="snapshot1" class="snapshot-info">
                <p>创建时间：{{ snapshot1.created_at }}</p>
                <p>项目数量：{{ snapshot1.item_count }}</p>
                <p>总成本：¥{{ formatMoney(snapshot1.total_cost) }}</p>
              </div>
            </el-card>
          </el-col>
          <el-col :span="4" class="compare-arrow">
            <el-icon :size="40"><Right /></el-icon>
          </el-col>
          <el-col :span="10">
            <el-card shadow="never">
              <template #header>
                新版本
                <el-radio-group v-model="targetType" size="small" style="margin-left: 10px;">
                  <el-radio-button value="snapshot">快照</el-radio-button>
                  <el-radio-button value="current">当前BOM</el-radio-button>
                </el-radio-group>
              </template>
              <el-select 
                v-if="targetType === 'snapshot'"
                v-model="compareForm.snapshot_id_2" 
                placeholder="选择快照" 
                style="width: 100%;"
              >
                <el-option 
                  v-for="s in snapshots" 
                  :key="s.id" 
                  :label="`${s.name} (${s.item_count}项)`" 
                  :value="s.id"
                  :disabled="s.id === compareForm.snapshot_id_1"
                />
              </el-select>
              <div v-else class="current-bom-info">
                <p>将与项目当前BOM进行对比</p>
              </div>
            </el-card>
          </el-col>
        </el-row>
      </template>

      <!-- CAD导入对比 -->
      <template v-else>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="CAD导入会话">
              <el-select v-model="compareForm.cad_bom_session_id" placeholder="选择导入会话" style="width: 100%;">
                <el-option 
                  v-for="s in cadSessions" 
                  :key="s.id" 
                  :label="`${s.name} (${s.total_rows}项) - ${s.status_display}`" 
                  :value="s.id"
                />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
      </template>

      <!-- 操作按钮 -->
      <div class="compare-actions">
        <el-button type="primary" @click="runCompare" :loading="comparing">
          <el-icon><Connection /></el-icon> 开始对比
        </el-button>
        <el-button @click="createSnapshot" :disabled="!compareForm.project_id">
          <el-icon><Plus /></el-icon> 创建快照
        </el-button>
        <el-button @click="exportExcel" :disabled="!compareResult" :loading="exporting">
          <el-icon><Download /></el-icon> 导出Excel
        </el-button>
      </div>
    </el-card>

    <!-- 对比结果 -->
    <el-card v-if="compareResult" class="result-card">
      <template #header>
        <div class="card-header">
          <span>对比结果</span>
          <span class="compare-time">对比时间：{{ compareResult.generated_at }}</span>
        </div>
      </template>

      <!-- 汇总统计 -->
      <el-row :gutter="20" class="summary-row">
        <el-col :span="6">
          <el-statistic title="新增" :value="compareResult.summary?.新增项目 || 0">
            <template #suffix>
              <el-tag type="success" size="small">项</el-tag>
            </template>
          </el-statistic>
        </el-col>
        <el-col :span="6">
          <el-statistic title="删除" :value="compareResult.summary?.删除项目 || 0">
            <template #suffix>
              <el-tag type="danger" size="small">项</el-tag>
            </template>
          </el-statistic>
        </el-col>
        <el-col :span="6">
          <el-statistic title="修改" :value="compareResult.summary?.修改项目 || 0">
            <template #suffix>
              <el-tag type="warning" size="small">项</el-tag>
            </template>
          </el-statistic>
        </el-col>
        <el-col :span="6">
          <el-statistic title="未变更" :value="compareResult.summary?.未变更项目 || 0">
            <template #suffix>
              <el-tag type="info" size="small">项</el-tag>
            </template>
          </el-statistic>
        </el-col>
      </el-row>

      <!-- 变更类型筛选 -->
      <el-radio-group v-model="changeFilter" style="margin: 20px 0;">
        <el-radio-button value="all">全部</el-radio-button>
        <el-radio-button value="added">新增 ({{ compareResult.changes?.added?.length || 0 }})</el-radio-button>
        <el-radio-button value="removed">删除 ({{ compareResult.changes?.removed?.length || 0 }})</el-radio-button>
        <el-radio-button value="modified">修改 ({{ compareResult.changes?.modified?.length || 0 }})</el-radio-button>
      </el-radio-group>

      <!-- 变更明细 -->
      <el-table :data="filteredChanges" border stripe max-height="500">
        <el-table-column prop="item_sku" label="物料编码" width="150" />
        <el-table-column prop="item_name" label="物料名称" min-width="200" show-overflow-tooltip />
        <el-table-column label="变更类型" width="100">
          <template #default="{ row }">
            <el-tag :type="getChangeTypeColor(row.change_type)" size="small">
              {{ getChangeTypeLabel(row.change_type) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="原数量" width="100" align="right">
          <template #default="{ row }">
            {{ row.old_qty || 0 }}
          </template>
        </el-table-column>
        <el-table-column label="新数量" width="100" align="right">
          <template #default="{ row }">
            {{ row.new_qty || 0 }}
          </template>
        </el-table-column>
        <el-table-column label="数量差异" width="100" align="right">
          <template #default="{ row }">
            <span :class="getDiffClass(row.new_qty - row.old_qty)">
              {{ row.new_qty - row.old_qty > 0 ? '+' : '' }}{{ row.new_qty - row.old_qty }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="变更详情" min-width="250">
          <template #default="{ row }">
            <div v-if="row.changes && row.changes.length">
              <el-tag 
                v-for="(c, idx) in row.changes" 
                :key="idx" 
                size="small" 
                type="info"
                style="margin-right: 5px;"
              >
                {{ c.field }}: {{ c.old_value }} → {{ c.new_value }}
              </el-tag>
            </div>
            <span v-else>-</span>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 创建快照对话框 -->
    <el-dialog v-model="snapshotDialogVisible" title="创建BOM快照" width="500px">
      <el-form :model="snapshotForm" label-width="100px">
        <el-form-item label="快照名称" required>
          <el-input v-model="snapshotForm.name" placeholder="如：设计评审版V1.0" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="snapshotForm.description" type="textarea" :rows="3" placeholder="快照说明" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="snapshotDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="confirmCreateSnapshot" :loading="creatingSnapshot">创建</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { getProjectList } from '@/api/projects/project'
import { getBOMSnapshotList, createBOMSnapshot, compareBOMWithCurrent, compareBOM, exportBOMCompare } from '@/api/plm/bom-compare'
import { getCreoBOMImportList } from '@/api/plm/creo'
import { ElMessage } from 'element-plus'
import { Right, Connection, Plus, Download } from '@element-plus/icons-vue'

const projects = ref([])
const snapshots = ref([])
const cadSessions = ref([])
const comparing = ref(false)
const exporting = ref(false)
const creatingSnapshot = ref(false)
const snapshotDialogVisible = ref(false)

const compareMode = ref('snapshot')
const targetType = ref('current')
const changeFilter = ref('all')

const compareForm = reactive({
  project_id: null,
  snapshot_id_1: null,
  snapshot_id_2: null,
  cad_bom_session_id: null
})

const snapshotForm = reactive({
  name: '',
  description: ''
})

const compareResult = ref(null)

const snapshot1 = computed(() => {
  return snapshots.value.find(s => s.id === compareForm.snapshot_id_1)
})

const filteredChanges = computed(() => {
  if (!compareResult.value?.changes) return []
  
  const all = [
    ...(compareResult.value.changes.added || []),
    ...(compareResult.value.changes.removed || []),
    ...(compareResult.value.changes.modified || [])
  ]
  
  if (changeFilter.value === 'all') return all
  return compareResult.value.changes[changeFilter.value] || []
})

const formatMoney = (val) => Number(val || 0).toLocaleString('zh-CN', { minimumFractionDigits: 2 })

const getChangeTypeColor = (type) => {
  const colors = {
    'ADDED': 'success',
    'REMOVED': 'danger',
    'QTY_CHANGED': 'warning',
    'SPEC_CHANGED': 'info',
    'MATERIAL_CHANGED': 'info',
    'PRICE_CHANGED': 'warning'
  }
  return colors[type] || 'info'
}

const getChangeTypeLabel = (type) => {
  const labels = {
    'ADDED': '新增',
    'REMOVED': '删除',
    'QTY_CHANGED': '数量变化',
    'SPEC_CHANGED': '规格变化',
    'MATERIAL_CHANGED': '材质变化',
    'PRICE_CHANGED': '价格变化'
  }
  return labels[type] || type
}

const getDiffClass = (diff) => {
  if (diff > 0) return 'diff-positive'
  if (diff < 0) return 'diff-negative'
  return ''
}

const loadProjects = async () => {
  try {
    const res = await getProjectList({ page_size: 1000 })
    projects.value = res.results || res || []
  } catch (error) {
    console.error('Load projects failed:', error)
  }
}

const loadSnapshots = async () => {
  if (!compareForm.project_id) {
    snapshots.value = []
    return
  }
  try {
    const res = await getBOMSnapshotList({ params: { project: compareForm.project_id } 
    })
    snapshots.value = res.results || res || []
  } catch (error) {
    console.error('Load snapshots failed:', error)
  }
  
  // 同时加载CAD导入会话
  try {
    const res = await getCreoBOMImportList({ params: { project_id: compareForm.project_id } 
    })
    cadSessions.value = res.results || res || []
  } catch (error) {
    console.error('Load CAD sessions failed:', error)
  }
}

const runCompare = async () => {
  if (!compareForm.project_id) {
    ElMessage.warning('请选择项目')
    return
  }
  
  comparing.value = true
  try {
    let params = { project_id: compareForm.project_id }
    
    if (compareMode.value === 'snapshot') {
      if (targetType.value === 'current') {
        // 与当前BOM对比
        if (!compareForm.snapshot_id_1) {
          ElMessage.warning('请选择基准快照')
          return
        }
        const res = await compareBOMWithCurrent(compareForm.snapshot_id_1)
        compareResult.value = res
      } else {
        // 快照对比
        if (!compareForm.snapshot_id_1 || !compareForm.snapshot_id_2) {
          ElMessage.warning('请选择两个快照')
          return
        }
        params.snapshot_id_1 = compareForm.snapshot_id_1
        params.snapshot_id_2 = compareForm.snapshot_id_2
        const res = await compareBOM(params)
        compareResult.value = res
      }
    } else {
      // CAD对比
      if (!compareForm.cad_bom_session_id) {
        ElMessage.warning('请选择CAD导入会话')
        return
      }
      params.cad_bom_session_id = compareForm.cad_bom_session_id
      const res = await compareBOM(params)
      compareResult.value = res
    }
    
    ElMessage.success('对比完成')
  } catch (error) {
    ElMessage.error('对比失败')
    console.error(error)
  } finally {
    comparing.value = false
  }
}

const createSnapshot = () => {
  snapshotForm.name = `快照_${new Date().toISOString().slice(0, 10)}`
  snapshotForm.description = ''
  snapshotDialogVisible.value = true
}

const confirmCreateSnapshot = async () => {
  if (!snapshotForm.name) {
    ElMessage.warning('请输入快照名称')
    return
  }
  
  creatingSnapshot.value = true
  try {
    await createBOMSnapshot( {
      project_id: compareForm.project_id,
      name: snapshotForm.name,
      description: snapshotForm.description
    })
    ElMessage.success('快照创建成功')
    snapshotDialogVisible.value = false
    loadSnapshots()
  } catch (error) {
    ElMessage.error('创建失败')
  } finally {
    creatingSnapshot.value = false
  }
}

const exportExcel = async () => {
  exporting.value = true
  try {
    const params = {
      project_id: compareForm.project_id,
      output_format: 'excel'
    }
    
    if (compareMode.value === 'snapshot') {
      params.snapshot_id_1 = compareForm.snapshot_id_1
      params.snapshot_id_2 = compareForm.snapshot_id_2
    } else {
      params.cad_bom_session_id = compareForm.cad_bom_session_id
    }
    
    const res = await exportBOMCompare(params, {
      responseType: 'blob'
    })
    
    const url = window.URL.createObjectURL(new Blob([res]))
    const link = document.createElement('a')
    link.href = url
    link.setAttribute('download', `BOM对比报告_${new Date().toISOString().slice(0, 10)}.xlsx`)
    document.body.appendChild(link)
    link.click()
    link.remove()
    
    ElMessage.success('导出成功')
  } catch (error) {
    ElMessage.error('导出失败')
  } finally {
    exporting.value = false
  }
}

onMounted(() => {
  loadProjects()
})
</script>

<style scoped>
.bom-compare {
  padding: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.compare-form {
  margin-bottom: 20px;
}

.snapshot-select {
  margin: 20px 0;
}

.compare-arrow {
  display: flex;
  align-items: center;
  justify-content: center;
}

.snapshot-info {
  margin-top: 10px;
  padding: 10px;
  background: #f5f7fa;
  border-radius: 4px;
  font-size: 13px;
  color: #666;
}

.snapshot-info p {
  margin: 5px 0;
}

.current-bom-info {
  padding: 20px;
  text-align: center;
  color: #909399;
}

.compare-actions {
  margin: 20px 0;
  display: flex;
  gap: 10px;
}

.result-card {
  margin-top: 20px;
}

.compare-time {
  font-size: 12px;
  color: #909399;
}

.summary-row {
  margin-bottom: 20px;
}

.diff-positive {
  color: #67c23a;
  font-weight: bold;
}

.diff-negative {
  color: #f56c6c;
  font-weight: bold;
}
</style>
