<template>
  <div class="kanban-wip-management">
    <!-- WIP状态概览 -->
    <el-row :gutter="16" class="stat-row">
      <el-col :span="6">
        <el-card class="stat-card">
          <el-statistic title="工序总数" :value="wipStatus.length" />
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card">
          <el-statistic title="总WIP数量" :value="totalWIP" />
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card warning">
          <el-statistic title="预警工序" :value="warningCount" value-style="color: #E6A23C" />
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card danger">
          <el-statistic title="超限工序" :value="overLimitCount" value-style="color: #F56C6C" />
        </el-card>
      </el-col>
    </el-row>

    <!-- 看板面板 -->
    <el-card>
      <template #header>
        <div class="card-header">
          <span>WIP实时看板</span>
          <el-button @click="loadWIPStatus"><el-icon><Refresh /></el-icon>刷新</el-button>
        </div>
      </template>
      <el-row :gutter="16">
        <el-col :span="6" v-for="ws in wipStatus" :key="ws.process_name">
          <div class="wip-card" :class="wipCardClass(ws)">
            <div class="wip-header">{{ ws.process_name }}</div>
            <div class="wip-body">
              <div class="wip-number">{{ ws.current_wip }}</div>
              <div class="wip-limit">/ {{ ws.wip_limit }}</div>
            </div>
            <el-progress :percentage="ws.utilization" :status="ws.utilization > 100 ? 'exception' : (ws.utilization > 80 ? 'warning' : '')" :stroke-width="10" />
          </div>
        </el-col>
      </el-row>
    </el-card>

    <el-row :gutter="16" style="margin-top: 16px;">
      <!-- WIP规则管理 -->
      <el-col :span="12">
        <el-card>
          <template #header>
            <div class="card-header">
              <span>WIP限制规则</span>
              <el-button type="primary" size="small" @click="showRuleDialog = true"><el-icon><Plus /></el-icon>新增</el-button>
            </div>
          </template>
          <!-- 批量操作 -->
          <div v-if="selectedRows.length > 0" class="batch-toolbar">
            <span class="batch-info">已选择 {{ selectedRows.length }} 项</span>
            <el-button type="danger" size="small" @click="batchDelete">批量删除</el-button>
            <el-button size="small" @click="batchExport">导出选中</el-button>
          </div>
          <el-table :data="rules" v-loading="ruleLoading" stripe size="small" @selection-change="handleSelectionChange">
            <el-table-column type="selection" width="45" />
            <el-table-column prop="process_name" label="工序" min-width="120" />
            <el-table-column prop="wip_limit" label="WIP上限" width="100" align="center" />
            <el-table-column prop="warning_threshold" label="预警阈值(%)" width="110" align="center" />
            <el-table-column label="状态" width="80" align="center">
              <template #default="{ row }">
                <el-tag :type="row.is_active ? 'success' : 'info'" size="small">{{ row.is_active ? '启用' : '停用' }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="100">
              <template #default="{ row }">
                <el-button size="small" link type="primary" @click="editRule(row)">编辑</el-button>
                <el-button size="small" link type="danger" @click="deleteRule(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>

      <!-- WIP预警 -->
      <el-col :span="12">
        <el-card>
          <template #header>
            <div class="card-header">
              <span>WIP预警记录</span>
              <el-select v-model="alertFilter" placeholder="全部" clearable size="small" style="width: 120px" @change="loadAlerts">
                <el-option label="预警" value="warning" />
                <el-option label="超限" value="critical" />
                <el-option label="阻塞" value="blocked" />
              </el-select>
            </div>
          </template>
          <el-table :data="alerts" v-loading="alertLoading" stripe size="small" max-height="400">
            <el-table-column prop="process_name" label="工序" width="100" />
            <el-table-column label="类型" width="80" align="center">
              <template #default="{ row }">
                <el-tag :type="row.alert_type === 'critical' ? 'danger' : (row.alert_type === 'warning' ? 'warning' : 'info')" size="small">
                  {{ { warning: '预警', critical: '超限', blocked: '阻塞' }[row.alert_type] || row.alert_type }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="current_wip" label="当前WIP" width="80" align="center" />
            <el-table-column prop="wip_limit" label="限制" width="60" align="center" />
            <el-table-column prop="created_at" label="时间" width="150" />
          </el-table>
        </el-card>
      </el-col>
    </el-row>

    <!-- 规则编辑对话框 -->
    <el-dialog v-model="showRuleDialog" :title="ruleForm.id ? '编辑规则' : '新增规则'" width="500px">
      <el-form :model="ruleForm" ref="ruleFormRef" label-width="110px">
        <el-form-item label="工序" prop="process_name" :rules="[{required:true,message:'必填'}]">
          <el-input v-model="ruleForm.process_name" />
        </el-form-item>
        <el-form-item label="WIP上限" prop="wip_limit" :rules="[{required:true,message:'必填'}]">
          <el-input-number v-model="ruleForm.wip_limit" :min="1" style="width: 100%" />
        </el-form-item>
        <el-form-item label="预警阈值(%)">
          <el-slider v-model="ruleForm.warning_threshold" :min="50" :max="100" show-input />
        </el-form-item>
        <el-form-item label="启用">
          <el-switch v-model="ruleForm.is_active" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showRuleDialog = false">取消</el-button>
        <el-button type="primary" @click="submitRule">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted, onUnmounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Refresh } from '@element-plus/icons-vue'
import {
getKanbanWIPStatus, getKanbanWIPRules, createKanbanWIPRule,
  updateKanbanWIPRule, deleteKanbanWIPRule, getKanbanWIPAlerts
} from '@/api/production'
import { useBatchOperation } from '@/composables/useBatchOperation'

const { selectedRows, handleSelectionChange, batchDelete, batchExport } = useBatchOperation('/api/production/')


const wipStatus = ref([])
const rules = ref([])
const alerts = ref([])
const ruleLoading = ref(false)
const alertLoading = ref(false)
const showRuleDialog = ref(false)
const alertFilter = ref('')
const ruleFormRef = ref(null)
let refreshTimer = null

const ruleForm = reactive({ id: null, process_name: '', wip_limit: 10, warning_threshold: 80, is_active: true })

const totalWIP = computed(() => wipStatus.value.reduce((s, w) => s + (w.current_wip || 0), 0))
const warningCount = computed(() => wipStatus.value.filter(w => w.utilization > 80 && w.utilization <= 100).length)
const overLimitCount = computed(() => wipStatus.value.filter(w => w.utilization > 100).length)

const wipCardClass = (ws) => ws.utilization > 100 ? 'over-limit' : ws.utilization > 80 ? 'warning' : 'normal'

const loadWIPStatus = async () => {
  try {
    const res = await getKanbanWIPStatus()
    wipStatus.value = res.data || res || []
  } catch (error) {
    console.error('KanbanWIPManagement getKanbanWIPStatus error:', error)
  }
}

const loadRules = async () => {
  ruleLoading.value = true
  try {
    const res = await getKanbanWIPRules()
    rules.value = res.data?.results || res.results || []
  } finally { ruleLoading.value = false }
}

const loadAlerts = async () => {
  alertLoading.value = true
  try {
    const params = {}
    if (alertFilter.value) params.alert_type = alertFilter.value
    const res = await getKanbanWIPAlerts(params)
    alerts.value = res.data?.results || res.results || []
  } finally { alertLoading.value = false }
}

const editRule = (row) => {
  Object.assign(ruleForm, row)
  showRuleDialog.value = true
}

const submitRule = async () => {
  await ruleFormRef.value.validate()
  try {
    if (ruleForm.id) {
      await updateKanbanWIPRule(ruleForm.id, ruleForm)
    } else {
      await createKanbanWIPRule(ruleForm)
    }
    ElMessage.success('保存成功')
    showRuleDialog.value = false
    Object.assign(ruleForm, { id: null, process_name: '', wip_limit: 10, warning_threshold: 80, is_active: true })
    loadRules()
    loadWIPStatus()
  } catch (error) {
    console.error('KanbanWIPManagement loadWIPStatus error:', error)
  }
}

const deleteRule = async (row) => {
  await ElMessageBox.confirm('确认删除？', '提示')
  await deleteKanbanWIPRule(row.id)
  ElMessage.success('删除成功')
  loadRules()
}

onMounted(() => {
  loadWIPStatus()
  loadRules()
  loadAlerts()
  refreshTimer = setInterval(loadWIPStatus, 30000)
})

onUnmounted(() => { if (refreshTimer) clearInterval(refreshTimer) })
</script>

<style scoped>
.kanban-wip-management { padding: 0; }
.stat-row { margin-bottom: 16px; }
.stat-card { text-align: center; }
.card-header { display: flex; justify-content: space-between; align-items: center; }
.wip-card { padding: 16px; border-radius: 8px; margin-bottom: 12px; border: 2px solid #dcdfe6; transition: all 0.3s; }
.wip-card.normal { border-color: #67c23a; background: #f0f9eb; }
.wip-card.warning { border-color: #e6a23c; background: #fdf6ec; }
.wip-card.over-limit { border-color: #f56c6c; background: #fef0f0; animation: pulse 1.5s infinite; }
.wip-header { font-weight: bold; font-size: 14px; margin-bottom: 8px; }
.wip-body { display: flex; align-items: baseline; margin-bottom: 8px; }
.wip-number { font-size: 28px; font-weight: bold; }
.wip-limit { font-size: 16px; color: #909399; margin-left: 4px; }
@keyframes pulse { 0%,100% { opacity: 1; } 50% { opacity: 0.7; } }
</style>
