<template>
  <div class="wechat-work-config-page">
    <!-- 页面头部 -->
    <div class="page-header">
      <h2>
        <el-icon><Connection /></el-icon>
        企业微信考勤同步
      </h2>
      <el-tag type="success" v-if="config && config.is_active">已连接</el-tag>
      <el-tag type="info" v-else>未配置</el-tag>
    </div>

    <!-- 配置指南 -->
    <el-alert 
      v-if="!config || !config.corp_id" 
      type="info" 
      :closable="false" 
      class="guide-alert"
    >
      <template #title>
        <strong>如何获取企业微信打卡Secret？</strong>
      </template>
      <ol class="guide-steps">
        <li>登录 <a href="https://work.weixin.qq.com/wework_admin/loginpage_wx" target="_blank">企业微信管理后台</a></li>
        <li>进入 <strong>管理工具</strong> → <strong>通讯录同步</strong>（获取CorpID和通讯录Secret）</li>
        <li>进入 <strong>应用管理</strong> → <strong>应用</strong> → 找到 <strong>打卡</strong> 应用</li>
        <li>在打卡应用中找到 <strong>API</strong> → 点击 <strong>查看Secret</strong></li>
        <li>如果没有"打卡应用Secret"选项：
          <ul>
            <li>创建 <strong>自建应用</strong>（应用管理→自建→创建应用）</li>
            <li>获取该应用的 Secret</li>
            <li>在应用的 <strong>API权限</strong> 中添加 <strong>打卡</strong> 数据读取权限</li>
          </ul>
        </li>
      </ol>
    </el-alert>

    <el-row :gutter="20">
      <!-- 左侧：配置信息 -->
      <el-col :span="12">
        <el-card class="config-card">
          <template #header>
            <div class="card-header">
              <span>企业微信配置</span>
              <el-button v-if="config" type="primary" text @click="handleTestConnection" :loading="testing">
                测试连接
              </el-button>
            </div>
          </template>
          
          <el-form :model="form" :rules="rules" ref="formRef" label-width="120px" v-loading="loading">
            <el-form-item label="配置名称" prop="name">
              <el-input v-model="form.name" placeholder="默认配置" />
            </el-form-item>
            
            <el-form-item label="企业ID" prop="corp_id">
              <el-input v-model="form.corp_id" placeholder="在企业微信后台获取">
                <template #append>
                  <el-tooltip content="企业微信管理后台 → 我的企业 → 企业信息 → 企业ID">
                    <el-icon><QuestionFilled /></el-icon>
                  </el-tooltip>
                </template>
              </el-input>
            </el-form-item>
            
            <el-form-item label="应用Secret" prop="secret">
              <el-input 
                v-model="form.secret" 
                type="password" 
                show-password
                placeholder="自建应用的Secret"
              >
                <template #append>
                  <el-tooltip content="自建应用 → 查看Secret（需要有打卡权限）">
                    <el-icon><QuestionFilled /></el-icon>
                  </el-tooltip>
                </template>
              </el-input>
            </el-form-item>
            
            <el-form-item label="打卡Secret">
              <el-input 
                v-model="form.checkin_secret" 
                type="password" 
                show-password
                placeholder="打卡应用专用Secret（可选）"
              >
                <template #append>
                  <el-tooltip content="如果打卡应用有单独的Secret，填写在此；否则使用上面的应用Secret">
                    <el-icon><QuestionFilled /></el-icon>
                  </el-tooltip>
                </template>
              </el-input>
            </el-form-item>
            
            <el-form-item label="应用AgentID">
              <el-input v-model="form.agent_id" placeholder="可选，用于消息推送" />
            </el-form-item>
            
            <el-divider content-position="left">同步设置</el-divider>
            
            <el-form-item label="启用自动同步">
              <el-switch v-model="form.sync_enabled" />
              <span class="form-tip">启用后将自动定时同步企业微信打卡数据</span>
            </el-form-item>
            
            <el-form-item label="同步间隔" v-if="form.sync_enabled">
              <el-select v-model="form.sync_interval" style="width: 200px">
                <el-option label="每5分钟" :value="300" />
                <el-option label="每10分钟" :value="600" />
                <el-option label="每15分钟" :value="900" />
                <el-option label="每30分钟" :value="1800" />
                <el-option label="每小时" :value="3600" />
              </el-select>
            </el-form-item>
            
            <el-form-item label="同步天数">
              <el-input-number v-model="form.sync_days" :min="1" :max="30" />
              <span class="form-tip">每次同步获取最近N天的数据</span>
            </el-form-item>
            
            <el-form-item label="启用配置">
              <el-switch v-model="form.is_active" />
            </el-form-item>
            
            <el-form-item>
              <el-button type="primary" @click="handleSave" :loading="saving">保存配置</el-button>
              <el-button @click="handleReset">重置</el-button>
            </el-form-item>
          </el-form>
        </el-card>
      </el-col>
      
      <!-- 右侧：同步状态 -->
      <el-col :span="12">
        <!-- 同步操作 -->
        <el-card class="sync-card">
          <template #header>
            <div class="card-header">
              <span>同步操作</span>
              <el-tag v-if="config?.last_sync_time" type="info" size="small">
                上次同步: {{ formatDateTime(config.last_sync_time) }}
              </el-tag>
            </div>
          </template>
          
          <div class="sync-actions">
            <el-row :gutter="10">
              <el-col :span="12">
                <el-button 
                  type="primary" 
                  @click="handleSyncNow(7)" 
                  :loading="syncing" 
                  :disabled="!config?.is_active"
                  style="width: 100%"
                >
                  <el-icon><Refresh /></el-icon>
                  同步近7天
                </el-button>
              </el-col>
              <el-col :span="12">
                <el-button 
                  type="success" 
                  @click="handleSyncNow(30)" 
                  :loading="syncing" 
                  :disabled="!config?.is_active"
                  style="width: 100%"
                >
                  <el-icon><Calendar /></el-icon>
                  同步近30天
                </el-button>
              </el-col>
            </el-row>
            
            <el-row :gutter="10" style="margin-top: 10px">
              <el-col :span="12">
                <el-button 
                  @click="handleAutoMatchUsers" 
                  :loading="matching" 
                  :disabled="!config?.is_active"
                  style="width: 100%"
                >
                  <el-icon><User /></el-icon>
                  自动匹配用户
                </el-button>
              </el-col>
              <el-col :span="12">
                <el-button 
                  @click="showMappings = true" 
                  :disabled="!config?.is_active"
                  style="width: 100%"
                >
                  <el-icon><List /></el-icon>
                  查看用户映射
                </el-button>
              </el-col>
            </el-row>
          </div>
          
          <!-- 同步结果 -->
          <div v-if="syncResult" class="sync-result" :class="syncResult.success ? 'success' : 'error'">
            <p><strong>{{ syncResult.success ? '✅ 同步成功' : '❌ 同步失败' }}</strong></p>
            <p>{{ syncResult.message }}</p>
            <div v-if="syncResult.details" class="sync-details">
              <el-descriptions :column="2" size="small" border>
                <el-descriptions-item label="总记录数">{{ syncResult.details.total }}</el-descriptions-item>
                <el-descriptions-item label="新增记录">{{ syncResult.details.new }}</el-descriptions-item>
                <el-descriptions-item label="处理记录">{{ syncResult.details.processed }}</el-descriptions-item>
                <el-descriptions-item label="错误数">{{ syncResult.details.errors?.length || 0 }}</el-descriptions-item>
              </el-descriptions>
            </div>
          </div>
        </el-card>
        
        <!-- 用户映射统计 -->
        <el-card class="mapping-stats-card" style="margin-top: 20px">
          <template #header>
            <span>用户映射状态</span>
          </template>
          
          <el-row :gutter="20" class="stats-row">
            <el-col :span="8">
              <el-statistic title="已映射用户" :value="mappingStats.mapped_count" />
            </el-col>
            <el-col :span="8">
              <el-statistic title="未映射用户" :value="mappingStats.unmapped_count" />
            </el-col>
            <el-col :span="8">
              <el-statistic title="打卡记录" :value="mappingStats.record_count" />
            </el-col>
          </el-row>
        </el-card>
        
        <!-- 最近同步日志 -->
        <el-card class="sync-logs-card" style="margin-top: 20px">
          <template #header>
            <span>同步日志</span>
          </template>
          
          <el-table :data="syncLogs" size="small" max-height="200">
            <el-table-column label="时间" width="160">
              <template #default="{ row }">
                {{ formatDateTime(row.start_time) }}
              </template>
            </el-table-column>
            <el-table-column label="范围" width="150">
              <template #default="{ row }">
                {{ row.sync_date_from }} ~ {{ row.sync_date_to }}
              </template>
            </el-table-column>
            <el-table-column label="状态" width="80">
              <template #default="{ row }">
                <el-tag :type="getLogStatusType(row.status)" size="small">
                  {{ row.status_display }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="记录数" width="80" align="center">
              <template #default="{ row }">
                {{ row.new_records }} / {{ row.total_records }}
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>
    </el-row>
    
    <!-- 用户映射对话框 -->
    <el-dialog v-model="showMappings" title="企业微信用户映射" width="900px">
      <el-alert type="info" :closable="false" style="margin-bottom: 15px">
        用户映射将企业微信中的用户(UserID)与系统员工关联，关联后才能同步该用户的打卡数据到系统考勤记录。
      </el-alert>
      
      <el-table :data="mappings" v-loading="loadingMappings" max-height="400">
        <el-table-column prop="wechat_userid" label="企业微信UserID" width="150" />
        <el-table-column prop="wechat_name" label="企业微信姓名" width="120" />
        <el-table-column prop="employee_name" label="关联员工" width="150">
          <template #default="{ row }">
            <span v-if="row.employee_name">{{ row.employee_name }}</span>
            <el-tag v-else type="warning" size="small">未关联</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="employee_code" label="员工工号" width="100" />
        <el-table-column label="匹配方式" width="100">
          <template #default="{ row }">
            <el-tag :type="row.auto_matched ? 'success' : 'primary'" size="small">
              {{ row.auto_matched ? '自动' : '手动' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="160">
          <template #default="{ row }">
            {{ formatDateTime(row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="100">
          <template #default="{ row }">
            <el-button size="small" type="danger" text @click="handleDeleteMapping(row)">
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>
      
      <template #footer>
        <el-button @click="showMappings = false">关闭</el-button>
        <el-button type="primary" @click="handleAutoMatchUsers">自动匹配</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Connection, QuestionFilled, Refresh, Calendar, User, List } from '@element-plus/icons-vue'
import request from '@/utils/request'

// 数据
const loading = ref(false)
const saving = ref(false)
const testing = ref(false)
const syncing = ref(false)
const matching = ref(false)
const config = ref(null)
const formRef = ref(null)
const syncResult = ref(null)
const syncLogs = ref([])
const showMappings = ref(false)
const mappings = ref([])
const loadingMappings = ref(false)

const form = reactive({
  name: '默认配置',
  corp_id: '',
  secret: '',
  checkin_secret: '',
  agent_id: '',
  is_active: true,
  sync_enabled: true,
  sync_interval: 600,
  sync_days: 7
})

const rules = {
  name: [{ required: true, message: '请输入配置名称', trigger: 'blur' }],
  corp_id: [{ required: true, message: '请输入企业ID', trigger: 'blur' }],
  secret: [{ required: true, message: '请输入应用Secret', trigger: 'blur' }]
}

const mappingStats = ref({
  mapped_count: 0,
  unmapped_count: 0,
  record_count: 0
})

// 方法
const loadConfig = async () => {
  loading.value = true
  try {
    const res = await request.get('/oa/wechat-configs/')
    const configs = res.results || res || []
    if (configs.length > 0) {
      config.value = configs[0]
      Object.assign(form, {
        name: config.value.name || '默认配置',
        corp_id: config.value.corp_id || '',
        secret: '', // Secret不返回，需要重新输入才能更新
        checkin_secret: '',
        agent_id: config.value.agent_id || '',
        is_active: config.value.is_active,
        sync_enabled: config.value.sync_enabled,
        sync_interval: config.value.sync_interval || 600,
        sync_days: config.value.sync_days || 7
      })
      
      // 加载统计
      loadMappingStats()
      loadSyncLogs()
    }
  } catch (error) {
    console.error('加载配置失败:', error)
  } finally {
    loading.value = false
  }
}

const loadMappingStats = async () => {
  if (!config.value) return
  try {
    mappingStats.value = {
      mapped_count: config.value.user_count || 0,
      unmapped_count: 0,
      record_count: config.value.record_count || 0
    }
  } catch (error) {
    console.error('加载统计失败:', error)
  }
}

const loadSyncLogs = async () => {
  if (!config.value) return
  try {
    const res = await request.get(`/oa/wechat-configs/${config.value.id}/sync_history/`)
    syncLogs.value = res || []
  } catch (error) {
    console.error('加载同步日志失败:', error)
  }
}

const loadMappings = async () => {
  if (!config.value) return
  loadingMappings.value = true
  try {
    const res = await request.get('/oa/wechat-user-mappings/', {
      params: { config: config.value.id }
    })
    mappings.value = res.results || res || []
  } catch (error) {
    console.error('加载映射失败:', error)
  } finally {
    loadingMappings.value = false
  }
}

const handleSave = async () => {
  if (!formRef.value) return
  
  await formRef.value.validate(async (valid) => {
    if (!valid) return
    
    saving.value = true
    try {
      const data = { ...form }
      // 如果Secret为空，不传递（保持原有值）
      if (!data.secret) delete data.secret
      if (!data.checkin_secret) delete data.checkin_secret
      
      if (config.value) {
        await request.put(`/oa/wechat-configs/${config.value.id}/`, data)
        ElMessage.success('配置更新成功')
      } else {
        const res = await request.post('/oa/wechat-configs/', form)
        config.value = res
        ElMessage.success('配置创建成功')
      }
      
      loadConfig()
    } catch (error) {
      ElMessage.error(error.response?.data?.detail || '保存失败')
    } finally {
      saving.value = false
    }
  })
}

const handleReset = () => {
  if (config.value) {
    Object.assign(form, {
      name: config.value.name,
      corp_id: config.value.corp_id,
      secret: '',
      checkin_secret: '',
      agent_id: config.value.agent_id,
      is_active: config.value.is_active,
      sync_enabled: config.value.sync_enabled,
      sync_interval: config.value.sync_interval,
      sync_days: config.value.sync_days
    })
  }
}

const handleTestConnection = async () => {
  if (!config.value) {
    ElMessage.warning('请先保存配置')
    return
  }
  
  testing.value = true
  try {
    const res = await request.post(`/oa/wechat-configs/${config.value.id}/test_connection/`)
    if (res.success) {
      ElMessage.success(res.message || '连接成功！')
    } else {
      ElMessage.error(res.message || '连接失败')
    }
  } catch (error) {
    ElMessage.error(error.response?.data?.message || '连接测试失败')
  } finally {
    testing.value = false
  }
}

const handleSyncNow = async (days) => {
  if (!config.value) {
    ElMessage.warning('请先配置并保存')
    return
  }
  
  syncing.value = true
  syncResult.value = null
  
  try {
    const res = await request.post(`/oa/wechat-configs/${config.value.id}/sync_now/`, {
      days: days
    })
    
    syncResult.value = res
    
    if (res.success) {
      ElMessage.success(res.message)
    } else {
      ElMessage.warning(res.message)
    }
    
    // 刷新日志
    loadSyncLogs()
    loadMappingStats()
    
  } catch (error) {
    syncResult.value = {
      success: false,
      message: error.response?.data?.message || '同步失败'
    }
    ElMessage.error(syncResult.value.message)
  } finally {
    syncing.value = false
  }
}

const handleAutoMatchUsers = async () => {
  if (!config.value) {
    ElMessage.warning('请先配置并保存')
    return
  }
  
  matching.value = true
  try {
    const res = await request.post(`/oa/wechat-configs/${config.value.id}/auto_match_users/`)
    
    if (res.success) {
      ElMessage.success(res.message)
      loadMappings()
      loadMappingStats()
    } else {
      ElMessage.warning(res.message)
    }
  } catch (error) {
    ElMessage.error(error.response?.data?.message || '自动匹配失败')
  } finally {
    matching.value = false
  }
}

const handleDeleteMapping = async (row) => {
  try {
    await ElMessageBox.confirm('确定要删除该用户映射吗？', '提示', { type: 'warning' })
    await request.delete(`/oa/wechat-user-mappings/${row.id}/`)
    ElMessage.success('删除成功')
    loadMappings()
    loadMappingStats()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('删除失败')
    }
  }
}

const getLogStatusType = (status) => {
  const types = {
    'SUCCESS': 'success',
    'PARTIAL': 'warning',
    'FAILED': 'danger',
    'PENDING': 'info'
  }
  return types[status] || 'info'
}

const formatDateTime = (dateStr) => {
  if (!dateStr) return ''
  const date = new Date(dateStr)
  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  })
}

// 监听映射对话框打开
const onMappingDialogOpen = () => {
  if (showMappings.value) {
    loadMappings()
  }
}

// 初始化
onMounted(() => {
  loadConfig()
})
</script>

<style scoped>
.wechat-work-config-page {
  padding: 20px;
}

.page-header {
  display: flex;
  align-items: center;
  gap: 15px;
  margin-bottom: 20px;
}

.page-header h2 {
  margin: 0;
  font-size: 20px;
  color: #303133;
  display: flex;
  align-items: center;
  gap: 8px;
}

.guide-alert {
  margin-bottom: 20px;
}

.guide-steps {
  margin: 10px 0 0 20px;
  padding: 0;
  line-height: 1.8;
}

.guide-steps li {
  margin-bottom: 5px;
}

.guide-steps a {
  color: #409eff;
  text-decoration: none;
}

.guide-steps a:hover {
  text-decoration: underline;
}

.guide-steps ul {
  margin: 5px 0 5px 20px;
}

.config-card, .sync-card, .mapping-stats-card, .sync-logs-card {
  height: fit-content;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.form-tip {
  margin-left: 10px;
  color: #909399;
  font-size: 12px;
}

.sync-actions {
  margin-bottom: 20px;
}

.sync-result {
  padding: 15px;
  border-radius: 4px;
  margin-top: 15px;
}

.sync-result.success {
  background: #f0f9eb;
  border: 1px solid #e1f3d8;
}

.sync-result.error {
  background: #fef0f0;
  border: 1px solid #fde2e2;
}

.sync-result p {
  margin: 5px 0;
}

.sync-details {
  margin-top: 10px;
}

.stats-row {
  text-align: center;
}

.stats-row :deep(.el-statistic__head) {
  font-size: 13px;
  color: #909399;
}

.stats-row :deep(.el-statistic__content) {
  font-size: 24px;
  font-weight: bold;
  color: #409eff;
}
</style>
