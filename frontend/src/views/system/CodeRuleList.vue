<template>
  <div class="code-rule-list">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>编码规则管理</span>
          <div>
            <el-button type="primary" @click="handleInitDefault" :loading="initializing">
              <el-icon><Setting /></el-icon>
              初始化默认规则
            </el-button>
            <el-button type="success" @click="handleAdd">
              <el-icon><Plus /></el-icon>
              添加规则
            </el-button>
          </div>
        </div>
      </template>

      <!-- 搜索栏 -->
      <el-form :inline="true" class="search-form">
        <el-form-item label="规则类型">
          <el-select v-model="searchForm.rule_type" placeholder="全部" clearable style="width: 200px;" @change="fetchRules">
            <el-option label="全部" :value="null" />
            <el-option v-for="type in ruleTypes" :key="type.value" :label="type.label" :value="type.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="searchForm.is_active" placeholder="全部" clearable style="width: 120px;" @change="fetchRules">
            <el-option label="全部" :value="null" />
            <el-option label="启用" :value="true" />
            <el-option label="停用" :value="false" />
          </el-select>
        </el-form-item>
      </el-form>

      <!-- 数据表格 -->
      <el-table :data="rules" v-loading="loading" stripe border>
        <el-table-column prop="rule_type_display" label="规则类型" width="140" />
        <el-table-column prop="rule_name" label="规则名称" width="150" />
        <el-table-column label="编码格式" min-width="200">
          <template #default="{ row }">
            <el-tag type="info" size="small">{{ row.example }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="配置详情" min-width="250">
          <template #default="{ row }">
            <div style="font-size: 12px; line-height: 1.8;">
              <div v-if="row.prefix"><strong>前缀:</strong> {{ row.prefix }}</div>
              <div v-if="row.date_format"><strong>日期:</strong> {{ row.date_format }}</div>
              <div><strong>序列号:</strong> {{ row.seq_start }} ~ {{ row.current_seq }} (长度{{ row.seq_length }}位)</div>
              <div><strong>重置:</strong> {{ row.reset_mode_display }}</div>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="current_seq" label="当前序号" width="100" align="right" />
        <el-table-column label="状态" width="80" align="center">
          <template #default="{ row }">
            <el-tag :type="row.is_active ? 'success' : 'danger'" size="small">
              {{ row.is_active ? '启用' : '停用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="300" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="handleEdit(row)">编辑</el-button>
            <el-button size="small" type="warning" @click="handleResetSeq(row)">重置序号</el-button>
            <el-button size="small" type="info" @click="handleViewHistory(row)">历史</el-button>
            <el-button size="small" type="danger" @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 添加/编辑对话框 -->
    <el-dialog
      v-model="dialogVisible"
      :title="dialogTitle"
      width="700px"
      destroy-on-close
    >
      <!-- 物料编码特殊提示 -->
      <el-alert
        v-if="form.rule_type === 'ITEM'"
        title="⚠️ 物料编码使用特殊规则"
        type="warning"
        :closable="false"
        show-icon
        style="margin-bottom: 20px;"
      >
        <p>物料编码采用特殊的10位编码规则，不通过此处配置：</p>
        <p style="margin-top: 8px; font-weight: bold;">
          一级代码(1位) + 二级代码(1位) + 年份(2位) + 流水号(6位)
        </p>
        <p style="margin-top: 8px; color: #E6A23C;">
          • 一级代码：1=有图，2=无图<br/>
          • 二级代码：1-8（机加/钣金/特殊工艺等）<br/>
          • 年份：有图=当前年份，无图=99<br/>
          • 流水号：自动累加（6位）
        </p>
        <p style="margin-top: 12px; color: #409EFF;">
          📌 请在"物料管理"页面使用"生成编码"功能创建物料编码。
        </p>
      </el-alert>

      <el-form :model="form" :rules="rules" ref="formRef" label-width="120px">
        <el-form-item label="规则类型" prop="rule_type">
          <el-select v-model="form.rule_type" placeholder="选择规则类型" :disabled="isEdit" style="width: 100%;">
            <el-option v-for="type in ruleTypes" :key="type.value" :label="type.label" :value="type.value" />
          </el-select>
        </el-form-item>

        <el-form-item label="规则名称" prop="rule_name">
          <el-input v-model="form.rule_name" placeholder="输入规则名称" :disabled="form.rule_type === 'ITEM'" />
        </el-form-item>

        <el-divider content-position="left">编码格式配置</el-divider>

        <el-form-item label="固定前缀">
          <el-input v-model="form.prefix" placeholder="如：PRJ、SC等" maxlength="20" show-word-limit :disabled="form.rule_type === 'ITEM'" />
          <div class="el-form-item__extra">编码的固定前缀部分</div>
        </el-form-item>

        <el-form-item label="日期格式">
          <el-input v-model="form.date_format" placeholder="如：YYYYMMDD、YYYY-MM等" :disabled="form.rule_type === 'ITEM'" />
          <div class="el-form-item__extra">
            支持：YYYY(年)、YY(年后两位)、MM(月)、DD(日)，可自由组合
          </div>
        </el-form-item>

        <el-form-item label="分隔符">
          <el-input v-model="form.separator" placeholder="如：-、_等" maxlength="5" style="width: 100px;" :disabled="form.rule_type === 'ITEM'" />
          <div class="el-form-item__extra">各部分之间的分隔符，留空表示无分隔符</div>
        </el-form-item>

        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="序列号长度" prop="seq_length">
              <el-input-number v-model="form.seq_length" :min="1" :max="10" style="width: 100%;" :disabled="form.rule_type === 'ITEM'" />
              <div class="el-form-item__extra">不足位数时前面补0</div>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="序列号起始" prop="seq_start">
              <el-input-number v-model="form.seq_start" :min="1" :max="99999" style="width: 100%;" :disabled="form.rule_type === 'ITEM'" />
            </el-form-item>
          </el-col>
        </el-row>

        <el-form-item label="重置模式" prop="reset_mode">
          <el-radio-group v-model="form.reset_mode" :disabled="form.rule_type === 'ITEM'">
            <el-radio label="NONE">不重置</el-radio>
            <el-radio label="DAILY">每日重置</el-radio>
            <el-radio label="MONTHLY">每月重置</el-radio>
            <el-radio label="YEARLY">每年重置</el-radio>
          </el-radio-group>
          <div class="el-form-item__extra">序列号在指定周期后自动重置为起始值</div>
        </el-form-item>

        <el-form-item label="是否启用">
          <el-switch v-model="form.is_active" />
        </el-form-item>

        <el-form-item label="说明">
          <el-input v-model="form.description" type="textarea" :rows="3" placeholder="规则说明" />
        </el-form-item>

        <el-divider content-position="left">示例预览</el-divider>
        
        <el-alert
          v-if="form.rule_type !== 'ITEM'"
          :title="`示例编码：${generateExample()}`"
          type="success"
          :closable="false"
          show-icon
        />
        <el-alert
          v-else
          title="物料编码示例：1125000001（有图+机加+2025年+流水号1）"
          type="info"
          :closable="false"
          show-icon
        />
      </el-form>

      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSubmit" :loading="saving">保存</el-button>
      </template>
    </el-dialog>

    <!-- 历史记录对话框 -->
    <el-dialog
      v-model="historyVisible"
      title="编码生成历史"
      width="800px"
    >
      <el-table :data="historyList" v-loading="historyLoading" stripe max-height="400">
        <el-table-column prop="generated_code" label="生成的编码" width="150" />
        <el-table-column prop="sequence_number" label="序列号" width="100" align="right" />
        <el-table-column prop="generated_by_name" label="生成人" width="120" />
        <el-table-column prop="generated_at" label="生成时间" width="180" />
        <el-table-column prop="business_model" label="业务模型" width="120" />
      </el-table>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Setting } from '@element-plus/icons-vue'
import request from '@/utils/request'

const loading = ref(false)
const saving = ref(false)
const initializing = ref(false)
const dialogVisible = ref(false)
const historyVisible = ref(false)
const historyLoading = ref(false)
const dialogTitle = ref('添加编码规则')
const isEdit = ref(false)
const formRef = ref(null)

const rules = ref([])
const historyList = ref([])

const searchForm = reactive({
  rule_type: null,
  is_active: null
})

const form = reactive({
  id: null,
  rule_type: '',
  rule_name: '',
  prefix: '',
  date_format: '',
  seq_length: 4,
  seq_start: 1,
  reset_mode: 'YEARLY',
  separator: '-',
  is_active: true,
  description: ''
})

const ruleTypes = [
  { value: 'PROJECT', label: '项目编号' },
  { value: 'ITEM', label: '物料编码' },
  { value: 'PURCHASE_CONTRACT', label: '采购合同' },
  { value: 'SALES_CONTRACT', label: '销售合同' },
  { value: 'PURCHASE_REQUEST', label: '采购申请' },
  { value: 'PURCHASE_ORDER', label: '采购订单' },
  { value: 'SALES_ORDER', label: '销售订单' },
  { value: 'SALES_QUOTE', label: '销售报价' },
  { value: 'DELIVERY_ORDER', label: '发货单' },
  { value: 'INVOICE', label: '发票' },
  { value: 'GOODS_RECEIPT', label: '收货单' },
  { value: 'STOCK_MOVE', label: '库存移动' },
  { value: 'STOCK_ADJUSTMENT', label: '库存调整' },
]

const formRules = {
  rule_type: [{ required: true, message: '请选择规则类型', trigger: 'change' }],
  rule_name: [{ required: true, message: '请输入规则名称', trigger: 'blur' }],
  seq_length: [{ required: true, message: '请输入序列号长度', trigger: 'blur' }],
  seq_start: [{ required: true, message: '请输入序列号起始值', trigger: 'blur' }],
  reset_mode: [{ required: true, message: '请选择重置模式', trigger: 'change' }],
}

const fetchRules = async () => {
  loading.value = true
  try {
    const params = {}
    if (searchForm.rule_type) params.rule_type = searchForm.rule_type
    if (searchForm.is_active !== null) params.is_active = searchForm.is_active
    
    const res = await request.get('/core/code-rules/', { params })
    rules.value = res.data?.results || res.results || res.data || []
  } catch (error) {
    ElMessage.error('加载编码规则失败')
  } finally {
    loading.value = false
  }
}

const handleAdd = () => {
  dialogTitle.value = '添加编码规则'
  isEdit.value = false
  Object.assign(form, {
    id: null,
    rule_type: '',
    rule_name: '',
    prefix: '',
    date_format: '',
    seq_length: 4,
    seq_start: 1,
    reset_mode: 'YEARLY',
    separator: '-',
    is_active: true,
    description: ''
  })
  dialogVisible.value = true
}

const handleEdit = (row) => {
  dialogTitle.value = '编辑编码规则'
  isEdit.value = true
  Object.assign(form, {
    id: row.id,
    rule_type: row.rule_type,
    rule_name: row.rule_name,
    prefix: row.prefix || '',
    date_format: row.date_format || '',
    seq_length: row.seq_length,
    seq_start: row.seq_start,
    reset_mode: row.reset_mode,
    separator: row.separator || '',
    is_active: row.is_active,
    description: row.description || ''
  })
  dialogVisible.value = true
}

const handleSubmit = async () => {
  try {
    await formRef.value.validate()
    saving.value = true
    
    const data = { ...form }
    
    if (form.id) {
      await request.put(`/core/code-rules/${form.id}/`, data)
      ElMessage.success('更新成功')
    } else {
      await request.post('/core/code-rules/', data)
      ElMessage.success('添加成功')
    }
    
    dialogVisible.value = false
    fetchRules()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('操作失败')
    }
  } finally {
    saving.value = false
  }
}

const handleResetSeq = async (row) => {
  try {
    await ElMessageBox.confirm(
      `确定要重置 ${row.rule_name} 的序列号吗？序列号将重置为起始值 ${row.seq_start}`,
      '重置序列号',
      { type: 'warning' }
    )
    
    await request.post(`/core/code-rules/${row.id}/reset_sequence/`)
    ElMessage.success('序列号已重置')
    fetchRules()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('重置失败')
    }
  }
}

const handleViewHistory = async (row) => {
  historyVisible.value = true
  historyLoading.value = true
  try {
    const res = await request.get(`/core/code-rules/${row.id}/history/`)
    historyList.value = res.data || res || []
  } catch (error) {
    ElMessage.error('加载历史记录失败')
  } finally {
    historyLoading.value = false
  }
}

const handleDelete = async (row) => {
  try {
    await ElMessageBox.confirm(
      `确定要删除编码规则 ${row.rule_name} 吗？删除后无法恢复！`,
      '删除规则',
      { type: 'warning' }
    )
    
    await request.delete(`/core/code-rules/${row.id}/`)
    ElMessage.success('删除成功')
    fetchRules()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('删除失败')
    }
  }
}

const handleInitDefault = async () => {
  try {
    await ElMessageBox.confirm(
      '确定要初始化默认编码规则吗？已存在的规则不会被覆盖。',
      '初始化默认规则',
      { type: 'info' }
    )
    
    initializing.value = true
    const res = await request.post('/core/code-rules/init_default_rules/')
    ElMessage.success(res.message || '初始化成功')
    fetchRules()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('初始化失败')
    }
  } finally {
    initializing.value = false
  }
}

const generateExample = () => {
  const parts = []
  
  if (form.prefix) {
    parts.push(form.prefix)
  }
  
  if (form.date_format) {
    const now = new Date()
    let dateStr = form.date_format
    dateStr = dateStr.replace('YYYY', now.getFullYear().toString())
    dateStr = dateStr.replace('YY', now.getFullYear().toString().slice(-2))
    dateStr = dateStr.replace('MM', (now.getMonth() + 1).toString().padStart(2, '0'))
    dateStr = dateStr.replace('DD', now.getDate().toString().padStart(2, '0'))
    parts.push(dateStr)
  }
  
  const seqStr = form.seq_start.toString().padStart(form.seq_length, '0')
  parts.push(seqStr)
  
  return form.separator ? parts.join(form.separator) : parts.join('')
}

// 初始化
fetchRules()
</script>

<style scoped>
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.search-form {
  margin-bottom: 20px;
}

.el-form-item__extra {
  color: #909399;
  font-size: 12px;
  margin-top: 4px;
}
</style>

