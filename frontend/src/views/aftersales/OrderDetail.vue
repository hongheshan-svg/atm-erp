<template>
  <div class="order-detail" v-loading="loading">
    <el-page-header @back="goBack" :title="'返回'" :content="`售后工单: ${order?.order_no || ''}`" />
    
    <div class="detail-content" v-if="order">
      <!-- 基本信息和状态操作 -->
      <el-row :gutter="20">
        <el-col :span="16">
          <el-card class="info-card">
            <template #header>
              <div class="card-header">
                <span>工单信息</span>
                <div>
                  <el-tag :type="getStatusTagType(order.status)" size="large">{{ order.status_display }}</el-tag>
                  <el-tag :type="getPriorityTagType(order.priority)" size="large" style="margin-left: 10px;">{{ order.priority_display }}</el-tag>
                </div>
              </div>
            </template>
            <el-descriptions :column="2" border>
              <el-descriptions-item label="工单号">{{ order.order_no }}</el-descriptions-item>
              <el-descriptions-item label="工单类型">{{ order.order_type_display }}</el-descriptions-item>
              <el-descriptions-item label="项目">{{ order.project_name }}</el-descriptions-item>
              <el-descriptions-item label="客户">{{ order.customer_name }}</el-descriptions-item>
              <el-descriptions-item label="问题标题" :span="2">{{ order.title }}</el-descriptions-item>
              <el-descriptions-item label="问题描述" :span="2">{{ order.description }}</el-descriptions-item>
              <el-descriptions-item label="设备信息">{{ order.equipment_info || '-' }}</el-descriptions-item>
              <el-descriptions-item label="故障代码">{{ order.fault_code || '-' }}</el-descriptions-item>
              <el-descriptions-item label="联系人">{{ order.contact_person }}</el-descriptions-item>
              <el-descriptions-item label="联系电话">{{ order.contact_phone }}</el-descriptions-item>
              <el-descriptions-item label="现场地址" :span="2">{{ order.site_address || '-' }}</el-descriptions-item>
              <el-descriptions-item label="负责人">{{ order.assigned_to_name || '未分配' }}</el-descriptions-item>
              <el-descriptions-item label="保修期内">
                <el-tag :type="order.is_warranty ? 'success' : 'warning'">{{ order.is_warranty ? '是' : '否' }}</el-tag>
              </el-descriptions-item>
              <el-descriptions-item label="报修时间">{{ formatDateTime(order.reported_at) }}</el-descriptions-item>
              <el-descriptions-item label="期望完成">{{ order.expected_date || '-' }}</el-descriptions-item>
            </el-descriptions>
          </el-card>
        </el-col>
        
        <el-col :span="8">
          <!-- 状态操作 -->
          <el-card class="action-card">
            <template #header>
              <span>状态操作</span>
            </template>
            <div class="action-buttons">
              <el-button type="primary" @click="handleStartService" v-if="order.status === 'ASSIGNED'" block>
                开始服务
              </el-button>
              <el-button type="warning" @click="handleOnSite" v-if="order.status === 'IN_PROGRESS'" block>
                到达现场
              </el-button>
              <el-button type="info" @click="handleWaitingParts" v-if="['IN_PROGRESS', 'ON_SITE'].includes(order.status)" block>
                等待备件
              </el-button>
              <el-button type="success" @click="showResolveDialog" v-if="['IN_PROGRESS', 'ON_SITE', 'WAITING_PARTS'].includes(order.status)" block>
                解决问题
              </el-button>
              <el-button type="primary" @click="showCloseDialog" v-if="order.status === 'RESOLVED'" block>
                关闭工单
              </el-button>
              <el-button type="danger" @click="handleCancel" v-if="['PENDING', 'ASSIGNED'].includes(order.status)" block>
                取消工单
              </el-button>
            </div>
          </el-card>
          
          <!-- 成本汇总 -->
          <el-card class="cost-card" style="margin-top: 20px;">
            <template #header>
              <div class="card-header">
                <span>成本汇总</span>
                <el-button size="small" @click="showCostDialog">编辑</el-button>
              </div>
            </template>
            <el-descriptions :column="1" border size="small">
              <el-descriptions-item label="人工费用">¥{{ (order.labor_cost || 0).toFixed(2) }}</el-descriptions-item>
              <el-descriptions-item label="差旅费用">¥{{ (order.travel_cost || 0).toFixed(2) }}</el-descriptions-item>
              <el-descriptions-item label="备件费用">¥{{ (order.parts_cost || 0).toFixed(2) }}</el-descriptions-item>
              <el-descriptions-item label="其他费用">¥{{ (order.other_cost || 0).toFixed(2) }}</el-descriptions-item>
              <el-descriptions-item label="总成本">
                <span class="total-cost">¥{{ (order.total_cost || 0).toFixed(2) }}</span>
              </el-descriptions-item>
            </el-descriptions>
          </el-card>
        </el-col>
      </el-row>
      
      <!-- 解决方案 -->
      <el-card v-if="order.solution" style="margin-top: 20px;">
        <template #header>解决方案</template>
        <el-descriptions :column="1" border>
          <el-descriptions-item label="解决方案">{{ order.solution }}</el-descriptions-item>
          <el-descriptions-item label="根本原因">{{ order.root_cause || '-' }}</el-descriptions-item>
          <el-descriptions-item label="预防措施">{{ order.preventive_action || '-' }}</el-descriptions-item>
        </el-descriptions>
      </el-card>
      
      <!-- 服务记录 -->
      <el-card style="margin-top: 20px;">
        <template #header>
          <div class="card-header">
            <span>服务记录 ({{ order.service_records?.length || 0 }})</span>
            <el-button type="primary" size="small" @click="showServiceDialog">添加服务记录</el-button>
          </div>
        </template>
        <el-table :data="order.service_records || []" border stripe>
          <el-table-column prop="service_date" label="日期" width="110" />
          <el-table-column prop="service_type_display" label="类型" width="100" />
          <el-table-column prop="technician_name" label="服务人员" width="100" />
          <el-table-column label="时间" width="120">
            <template #default="{ row }">
              {{ row.start_time?.substring(0, 5) }} - {{ row.end_time?.substring(0, 5) }}
            </template>
          </el-table-column>
          <el-table-column prop="work_hours" label="工时" width="80" align="right">
            <template #default="{ row }">{{ row.work_hours }}h</template>
          </el-table-column>
          <el-table-column prop="work_content" label="工作内容" show-overflow-tooltip />
          <el-table-column label="费用" width="100" align="right">
            <template #default="{ row }">
              ¥{{ ((row.labor_cost || 0) + (row.travel_cost || 0)).toFixed(2) }}
            </template>
          </el-table-column>
          <el-table-column label="操作" width="80">
            <template #default="{ row }">
              <el-button type="danger" link size="small" @click="deleteServiceRecord(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-card>
      
      <!-- 备件使用 -->
      <el-card style="margin-top: 20px;">
        <template #header>
          <div class="card-header">
            <span>备件使用 ({{ order.spare_parts?.length || 0 }})</span>
            <el-button type="primary" size="small" @click="showSparePartDialog">添加备件</el-button>
          </div>
        </template>
        <el-table :data="order.spare_parts || []" border stripe>
          <el-table-column prop="item_sku" label="物料编码" width="120" />
          <el-table-column prop="item_name" label="物料名称" />
          <el-table-column prop="qty" label="数量" width="80" align="right" />
          <el-table-column label="单价" width="100" align="right">
            <template #default="{ row }">¥{{ row.unit_cost }}</template>
          </el-table-column>
          <el-table-column label="小计" width="100" align="right">
            <template #default="{ row }">¥{{ (row.qty * row.unit_cost).toFixed(2) }}</template>
          </el-table-column>
          <el-table-column label="保修" width="80" align="center">
            <template #default="{ row }">
              <el-tag :type="row.is_warranty ? 'success' : 'warning'" size="small">
                {{ row.is_warranty ? '是' : '否' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="serial_no" label="序列号" width="120" />
          <el-table-column label="操作" width="80">
            <template #default="{ row }">
              <el-button type="danger" link size="small" @click="deleteSparePart(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-card>
      
      <!-- 附件管理 -->
      <el-card style="margin-top: 20px;">
        <template #header>
          <div class="card-header">
            <span>附件资料 ({{ attachments.length }})</span>
            <el-upload
              ref="uploadRef"
              action="#"
              :auto-upload="false"
              :show-file-list="false"
              :on-change="handleFileSelect"
              multiple
              accept="image/*,video/*,.pdf,.doc,.docx,.xls,.xlsx"
            >
              <el-button type="primary" size="small">
                <el-icon><Upload /></el-icon>
                上传附件
              </el-button>
            </el-upload>
          </div>
        </template>
        
        <!-- 上传进度 -->
        <div v-if="uploadingFiles.length > 0" class="upload-progress">
          <div v-for="(file, index) in uploadingFiles" :key="index" class="upload-item">
            <span>{{ file.name }}</span>
            <el-progress :percentage="file.progress" :status="file.status" style="width: 200px;" />
          </div>
        </div>
        
        <!-- 附件列表 -->
        <div class="attachment-list" v-if="attachments.length > 0">
          <div v-for="attachment in attachments" :key="attachment.id" class="attachment-item">
            <div class="attachment-preview" @click="previewAttachment(attachment)">
              <template v-if="isImage(attachment.file_type)">
                <el-image :src="attachment.file_url" fit="cover" class="preview-image" />
              </template>
              <template v-else-if="isVideo(attachment.file_type)">
                <div class="video-placeholder">
                  <el-icon :size="40"><VideoPlay /></el-icon>
                  <span>视频</span>
                </div>
              </template>
              <template v-else>
                <div class="file-placeholder">
                  <el-icon :size="40"><Document /></el-icon>
                  <span>{{ getFileExtension(attachment.original_name) }}</span>
                </div>
              </template>
            </div>
            <div class="attachment-info">
              <div class="attachment-name" :title="attachment.original_name">{{ attachment.original_name }}</div>
              <div class="attachment-meta">
                <span>{{ formatFileSize(attachment.file_size) }}</span>
                <span>{{ getCategoryLabel(attachment.category) }}</span>
              </div>
              <div class="attachment-actions">
                <el-button type="primary" link size="small" @click="downloadAttachment(attachment)">下载</el-button>
                <el-button type="danger" link size="small" @click="deleteAttachment(attachment)">删除</el-button>
              </div>
            </div>
          </div>
        </div>
        <el-empty v-else description="暂无附件" :image-size="60" />
      </el-card>
    </div>
    
    <!-- 解决问题对话框 -->
    <el-dialog v-model="resolveDialogVisible" title="解决问题" width="600px">
      <el-form :model="resolveForm" label-width="100px">
        <el-form-item label="解决方案" required>
          <el-input v-model="resolveForm.solution" type="textarea" :rows="3" placeholder="描述如何解决问题" />
        </el-form-item>
        <el-form-item label="根本原因">
          <el-input v-model="resolveForm.root_cause" type="textarea" :rows="2" placeholder="分析问题根本原因" />
        </el-form-item>
        <el-form-item label="预防措施">
          <el-input v-model="resolveForm.preventive_action" type="textarea" :rows="2" placeholder="建议的预防措施" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="resolveDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleResolve" :loading="submitting">确定解决</el-button>
      </template>
    </el-dialog>
    
    <!-- 关闭工单对话框 -->
    <el-dialog v-model="closeDialogVisible" title="关闭工单" width="500px">
      <el-form :model="closeForm" label-width="100px">
        <el-form-item label="满意度评分">
          <el-rate v-model="closeForm.satisfaction_score" :max="5" show-text :texts="['很差', '较差', '一般', '满意', '非常满意']" />
        </el-form-item>
        <el-form-item label="客户反馈">
          <el-input v-model="closeForm.customer_feedback" type="textarea" :rows="3" placeholder="客户反馈意见" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="closeDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleClose" :loading="submitting">确定关闭</el-button>
      </template>
    </el-dialog>
    
    <!-- 服务记录对话框 -->
    <el-dialog v-model="serviceDialogVisible" title="添加服务记录" width="600px">
      <el-form :model="serviceForm" :rules="serviceRules" ref="serviceFormRef" label-width="100px">
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="服务类型" prop="service_type">
              <el-select v-model="serviceForm.service_type" style="width: 100%">
                <el-option label="远程支持" value="REMOTE" />
                <el-option label="现场服务" value="ON_SITE" />
                <el-option label="电话支持" value="PHONE" />
                <el-option label="视频会议" value="VIDEO" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="服务日期" prop="service_date">
              <el-date-picker v-model="serviceForm.service_date" type="date" style="width: 100%" value-format="YYYY-MM-DD" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="8">
            <el-form-item label="开始时间">
              <el-time-picker v-model="serviceForm.start_time" format="HH:mm" value-format="HH:mm:ss" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="结束时间">
              <el-time-picker v-model="serviceForm.end_time" format="HH:mm" value-format="HH:mm:ss" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="工时(小时)" prop="work_hours">
              <el-input-number v-model="serviceForm.work_hours" :min="0" :max="24" :precision="1" style="width: 100%" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="工作内容" prop="work_content">
          <el-input v-model="serviceForm.work_content" type="textarea" :rows="3" placeholder="描述服务内容" />
        </el-form-item>
        <el-form-item label="现场发现">
          <el-input v-model="serviceForm.findings" type="textarea" :rows="2" placeholder="现场发现的情况" />
        </el-form-item>
        <el-form-item label="采取措施">
          <el-input v-model="serviceForm.actions_taken" type="textarea" :rows="2" placeholder="采取的措施" />
        </el-form-item>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="人工费用">
              <el-input-number v-model="serviceForm.labor_cost" :min="0" :precision="2" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="差旅费用">
              <el-input-number v-model="serviceForm.travel_cost" :min="0" :precision="2" style="width: 100%" />
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>
      <template #footer>
        <el-button @click="serviceDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="saveServiceRecord" :loading="submitting">保存</el-button>
      </template>
    </el-dialog>
    
    <!-- 备件对话框 -->
    <el-dialog v-model="sparePartDialogVisible" title="添加备件" width="500px">
      <el-form :model="sparePartForm" :rules="sparePartRules" ref="sparePartFormRef" label-width="80px">
        <el-form-item label="备件" prop="item">
          <el-select v-model="sparePartForm.item" placeholder="选择物料" filterable style="width: 100%" @change="handleItemChange">
            <el-option v-for="i in items" :key="i.id" :label="`${i.sku} - ${i.name}`" :value="i.id" />
          </el-select>
        </el-form-item>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="数量" prop="qty">
              <el-input-number v-model="sparePartForm.qty" :min="1" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="单价" prop="unit_cost">
              <el-input-number v-model="sparePartForm.unit_cost" :min="0" :precision="2" style="width: 100%" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="序列号">
          <el-input v-model="sparePartForm.serial_no" placeholder="备件序列号" />
        </el-form-item>
        <el-form-item label="保修范围">
          <el-switch v-model="sparePartForm.is_warranty" active-text="是" inactive-text="否" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="sparePartForm.notes" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="sparePartDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="saveSparePart" :loading="submitting">保存</el-button>
      </template>
    </el-dialog>
    
    <!-- 成本编辑对话框 -->
    <el-dialog v-model="costDialogVisible" title="编辑成本" width="400px">
      <el-form :model="costForm" label-width="80px">
        <el-form-item label="人工费用">
          <el-input-number v-model="costForm.labor_cost" :min="0" :precision="2" style="width: 100%" />
        </el-form-item>
        <el-form-item label="差旅费用">
          <el-input-number v-model="costForm.travel_cost" :min="0" :precision="2" style="width: 100%" />
        </el-form-item>
        <el-form-item label="备件费用">
          <el-input-number v-model="costForm.parts_cost" :min="0" :precision="2" style="width: 100%" />
        </el-form-item>
        <el-form-item label="其他费用">
          <el-input-number v-model="costForm.other_cost" :min="0" :precision="2" style="width: 100%" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="costDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="saveCost" :loading="submitting">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Upload, VideoPlay, Document } from '@element-plus/icons-vue'
import request from '@/utils/request'
import { useUserStore } from '@/stores/user'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()

const loading = ref(false)
const submitting = ref(false)
const order = ref(null)
const items = ref([])

// 附件相关
const attachments = ref([])
const uploadRef = ref(null)
const uploadingFiles = ref([])

const resolveDialogVisible = ref(false)
const closeDialogVisible = ref(false)
const serviceDialogVisible = ref(false)
const sparePartDialogVisible = ref(false)
const costDialogVisible = ref(false)

const serviceFormRef = ref(null)
const sparePartFormRef = ref(null)

const resolveForm = reactive({
  solution: '',
  root_cause: '',
  preventive_action: ''
})

const closeForm = reactive({
  satisfaction_score: 5,
  customer_feedback: ''
})

const serviceForm = reactive({
  service_type: 'ON_SITE',
  service_date: new Date().toISOString().split('T')[0],
  start_time: null,
  end_time: null,
  work_hours: 0,
  work_content: '',
  findings: '',
  actions_taken: '',
  labor_cost: 0,
  travel_cost: 0
})

const sparePartForm = reactive({
  item: null,
  qty: 1,
  unit_cost: 0,
  serial_no: '',
  is_warranty: true,
  notes: ''
})

const costForm = reactive({
  labor_cost: 0,
  travel_cost: 0,
  parts_cost: 0,
  other_cost: 0
})

const serviceRules = {
  service_type: [{ required: true, message: '请选择服务类型', trigger: 'change' }],
  service_date: [{ required: true, message: '请选择服务日期', trigger: 'change' }],
  work_hours: [{ required: true, message: '请输入工时', trigger: 'blur' }],
  work_content: [{ required: true, message: '请输入工作内容', trigger: 'blur' }]
}

const sparePartRules = {
  item: [{ required: true, message: '请选择备件', trigger: 'change' }],
  qty: [{ required: true, message: '请输入数量', trigger: 'blur' }],
  unit_cost: [{ required: true, message: '请输入单价', trigger: 'blur' }]
}

const formatDateTime = (dt) => {
  if (!dt) return '-'
  return new Date(dt).toLocaleString('zh-CN')
}

const getStatusTagType = (status) => {
  const map = { PENDING: 'info', ASSIGNED: '', IN_PROGRESS: 'primary', ON_SITE: 'primary', WAITING_PARTS: 'warning', RESOLVED: 'success', CLOSED: 'success', CANCELLED: 'info' }
  return map[status] || ''
}

const getPriorityTagType = (priority) => {
  const map = { URGENT: 'danger', HIGH: 'warning', MEDIUM: '', LOW: 'info' }
  return map[priority] || ''
}

const goBack = () => {
  router.push('/aftersales/orders')
}

const loadOrder = async () => {
  loading.value = true
  try {
    const res = await request.get(`/projects/aftersales/${route.params.id}/`)
    order.value = res.data || res
  } catch (error) {
    ElMessage.error('加载工单失败')
    console.error(error)
  } finally {
    loading.value = false
  }
}

const loadItems = async () => {
  try {
    const res = await request.get('/masterdata/items/')
    items.value = res.data?.results || res.results || []
  } catch (error) {
    console.error('加载物料失败:', error)
  }
}

const handleStartService = async () => {
  try {
    await request.post(`/projects/aftersales/${order.value.id}/start_service/`)
    ElMessage.success('已开始服务')
    loadOrder()
  } catch (error) {
    ElMessage.error('操作失败')
  }
}

const handleOnSite = async () => {
  try {
    await request.post(`/projects/aftersales/${order.value.id}/on_site/`)
    ElMessage.success('已到达现场')
    loadOrder()
  } catch (error) {
    ElMessage.error('操作失败')
  }
}

const handleWaitingParts = async () => {
  try {
    await request.post(`/projects/aftersales/${order.value.id}/waiting_parts/`)
    ElMessage.success('状态已更新')
    loadOrder()
  } catch (error) {
    ElMessage.error('操作失败')
  }
}

const showResolveDialog = () => {
  resolveForm.solution = order.value.solution || ''
  resolveForm.root_cause = order.value.root_cause || ''
  resolveForm.preventive_action = order.value.preventive_action || ''
  resolveDialogVisible.value = true
}

const handleResolve = async () => {
  if (!resolveForm.solution) {
    ElMessage.warning('请输入解决方案')
    return
  }
  submitting.value = true
  try {
    await request.post(`/projects/aftersales/${order.value.id}/resolve/`, resolveForm)
    ElMessage.success('问题已解决')
    resolveDialogVisible.value = false
    loadOrder()
  } catch (error) {
    ElMessage.error('操作失败')
  } finally {
    submitting.value = false
  }
}

const showCloseDialog = () => {
  closeForm.satisfaction_score = order.value.satisfaction_score || 5
  closeForm.customer_feedback = order.value.customer_feedback || ''
  closeDialogVisible.value = true
}

const handleClose = async () => {
  submitting.value = true
  try {
    await request.post(`/projects/aftersales/${order.value.id}/close/`, closeForm)
    ElMessage.success('工单已关闭')
    closeDialogVisible.value = false
    loadOrder()
  } catch (error) {
    ElMessage.error('操作失败')
  } finally {
    submitting.value = false
  }
}

const handleCancel = async () => {
  try {
    await ElMessageBox.confirm('确定要取消此工单吗？', '取消工单', { type: 'warning' })
    await request.post(`/projects/aftersales/${order.value.id}/cancel/`)
    ElMessage.success('工单已取消')
    loadOrder()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('操作失败')
    }
  }
}

const showServiceDialog = () => {
  serviceForm.service_type = 'ON_SITE'
  serviceForm.service_date = new Date().toISOString().split('T')[0]
  serviceForm.start_time = null
  serviceForm.end_time = null
  serviceForm.work_hours = 0
  serviceForm.work_content = ''
  serviceForm.findings = ''
  serviceForm.actions_taken = ''
  serviceForm.labor_cost = 0
  serviceForm.travel_cost = 0
  serviceDialogVisible.value = true
}

const saveServiceRecord = async () => {
  try {
    await serviceFormRef.value.validate()
    submitting.value = true
    
    const data = {
      aftersales_order: order.value.id,
      technician: userStore.userInfo?.id,
      ...serviceForm
    }
    
    await request.post('/projects/service-records/', data)
    ElMessage.success('服务记录已添加')
    serviceDialogVisible.value = false
    loadOrder()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('保存失败')
    }
  } finally {
    submitting.value = false
  }
}

const deleteServiceRecord = async (row) => {
  try {
    await ElMessageBox.confirm('确定要删除此服务记录吗？', '删除确认', { type: 'warning' })
    await request.delete(`/projects/service-records/${row.id}/`)
    ElMessage.success('删除成功')
    loadOrder()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('删除失败')
    }
  }
}

const showSparePartDialog = () => {
  sparePartForm.item = null
  sparePartForm.qty = 1
  sparePartForm.unit_cost = 0
  sparePartForm.serial_no = ''
  sparePartForm.is_warranty = order.value.is_warranty
  sparePartForm.notes = ''
  sparePartDialogVisible.value = true
}

const handleItemChange = (itemId) => {
  const item = items.value.find(i => i.id === itemId)
  if (item) {
    sparePartForm.unit_cost = item.standard_cost || 0
  }
}

const saveSparePart = async () => {
  try {
    await sparePartFormRef.value.validate()
    submitting.value = true
    
    const data = {
      aftersales_order: order.value.id,
      ...sparePartForm
    }
    
    await request.post('/projects/spare-parts/', data)
    ElMessage.success('备件记录已添加')
    sparePartDialogVisible.value = false
    loadOrder()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('保存失败')
    }
  } finally {
    submitting.value = false
  }
}

const deleteSparePart = async (row) => {
  try {
    await ElMessageBox.confirm('确定要删除此备件记录吗？', '删除确认', { type: 'warning' })
    await request.delete(`/projects/spare-parts/${row.id}/`)
    ElMessage.success('删除成功')
    loadOrder()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('删除失败')
    }
  }
}

const showCostDialog = () => {
  costForm.labor_cost = order.value.labor_cost || 0
  costForm.travel_cost = order.value.travel_cost || 0
  costForm.parts_cost = order.value.parts_cost || 0
  costForm.other_cost = order.value.other_cost || 0
  costDialogVisible.value = true
}

const saveCost = async () => {
  submitting.value = true
  try {
    await request.post(`/projects/aftersales/${order.value.id}/update_cost/`, costForm)
    ElMessage.success('成本更新成功')
    costDialogVisible.value = false
    loadOrder()
  } catch (error) {
    ElMessage.error('更新失败')
  } finally {
    submitting.value = false
  }
}

// ========== 附件相关函数 ==========

const loadAttachments = async () => {
  try {
    const res = await request.get('/core/attachments/', {
      params: {
        related_model: 'AfterSalesOrder',
        related_id: route.params.id
      }
    })
    attachments.value = res.data?.results || res.results || []
  } catch (error) {
    console.error('加载附件失败:', error)
  }
}

const handleFileSelect = async (file) => {
  // 添加到上传队列
  const uploadItem = {
    name: file.name,
    progress: 0,
    status: ''
  }
  uploadingFiles.value.push(uploadItem)
  
  try {
    const formData = new FormData()
    formData.append('file', file.raw)
    formData.append('related_model', 'AfterSalesOrder')
    formData.append('related_id', route.params.id)
    
    // 根据文件类型设置分类
    let category = 'OTHER'
    if (file.raw.type.startsWith('image/')) {
      category = 'FAULT_IMAGE'
    } else if (file.raw.type.startsWith('video/')) {
      category = 'FAULT_VIDEO'
    }
    formData.append('category', category)
    
    await request.post('/core/attachments/', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      onUploadProgress: (progressEvent) => {
        uploadItem.progress = Math.round((progressEvent.loaded * 100) / progressEvent.total)
      }
    })
    
    uploadItem.status = 'success'
    ElMessage.success(`${file.name} 上传成功`)
    loadAttachments()
  } catch (error) {
    uploadItem.status = 'exception'
    ElMessage.error(`${file.name} 上传失败`)
  }
  
  // 清理已完成的上传项
  setTimeout(() => {
    uploadingFiles.value = uploadingFiles.value.filter(f => f.status !== 'success' && f.status !== 'exception')
  }, 2000)
}

const isImage = (fileType) => {
  return fileType && fileType.startsWith('image/')
}

const isVideo = (fileType) => {
  return fileType && fileType.startsWith('video/')
}

const getFileExtension = (filename) => {
  const ext = filename.split('.').pop()
  return ext ? ext.toUpperCase() : 'FILE'
}

const formatFileSize = (bytes) => {
  if (!bytes) return '0 B'
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
}

const getCategoryLabel = (category) => {
  const map = {
    'FAULT_IMAGE': '故障图片',
    'FAULT_VIDEO': '故障视频',
    'IMAGE': '图片',
    'VIDEO': '视频',
    'OTHER': '其他'
  }
  return map[category] || category
}

const previewAttachment = (attachment) => {
  if (isImage(attachment.file_type)) {
    // 图片预览
    window.open(attachment.file_url, '_blank')
  } else if (isVideo(attachment.file_type)) {
    // 视频预览
    window.open(attachment.file_url, '_blank')
  } else {
    // 其他文件直接下载
    downloadAttachment(attachment)
  }
}

const downloadAttachment = (attachment) => {
  window.open(`/api/core/attachments/${attachment.id}/download/`, '_blank')
}

const deleteAttachment = async (attachment) => {
  try {
    await ElMessageBox.confirm('确定要删除该附件吗？', '删除确认', { type: 'warning' })
    await request.delete(`/core/attachments/${attachment.id}/`)
    ElMessage.success('删除成功')
    loadAttachments()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('删除失败')
    }
  }
}

onMounted(() => {
  loadOrder()
  loadItems()
  loadAttachments()
})
</script>

<style scoped>
.order-detail {
  padding: 20px;
}

.detail-content {
  margin-top: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.action-buttons .el-button {
  width: 100%;
  margin-bottom: 10px;
}

.total-cost {
  font-weight: bold;
  color: #e6a23c;
  font-size: 18px;
}

.info-card, .action-card, .cost-card {
  height: 100%;
}

/* 附件样式 */
.upload-progress {
  margin-bottom: 15px;
}

.upload-item {
  display: flex;
  align-items: center;
  gap: 15px;
  margin-bottom: 8px;
}

.attachment-list {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 15px;
}

.attachment-item {
  border: 1px solid #ebeef5;
  border-radius: 8px;
  overflow: hidden;
  transition: box-shadow 0.3s;
}

.attachment-item:hover {
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
}

.attachment-preview {
  height: 120px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #f5f7fa;
  cursor: pointer;
}

.preview-image {
  width: 100%;
  height: 100%;
}

.video-placeholder,
.file-placeholder {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: #909399;
}

.video-placeholder span,
.file-placeholder span {
  margin-top: 8px;
  font-size: 12px;
}

.attachment-info {
  padding: 10px;
}

.attachment-name {
  font-size: 13px;
  color: #303133;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.attachment-meta {
  margin-top: 5px;
  font-size: 12px;
  color: #909399;
  display: flex;
  gap: 10px;
}

.attachment-actions {
  margin-top: 8px;
  display: flex;
  gap: 5px;
}
</style>

