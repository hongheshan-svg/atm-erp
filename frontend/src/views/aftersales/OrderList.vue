<template>
  <div class="aftersales-list">
    <!-- 统计卡片 -->
    <el-row :gutter="20" class="stats-row">
      <el-col :span="4">
        <el-card shadow="hover" class="stat-card">
          <el-statistic title="待处理" :value="stats.pending" />
        </el-card>
      </el-col>
      <el-col :span="4">
        <el-card shadow="hover" class="stat-card">
          <el-statistic title="处理中" :value="stats.inProgress" />
        </el-card>
      </el-col>
      <el-col :span="4">
        <el-card shadow="hover" class="stat-card">
          <el-statistic title="本月新增" :value="stats.monthlyCount" />
        </el-card>
      </el-col>
      <el-col :span="4">
        <el-card shadow="hover" class="stat-card">
          <el-statistic title="总成本" :value="stats.totalCost" prefix="¥" :precision="2" />
        </el-card>
      </el-col>
      <el-col :span="4">
        <el-card shadow="hover" class="stat-card">
          <el-statistic title="平均满意度" :value="stats.avgSatisfaction" suffix="/5" :precision="1" />
        </el-card>
      </el-col>
      <el-col :span="4">
        <el-card shadow="hover" class="stat-card">
          <el-statistic title="总工单数" :value="total" />
        </el-card>
      </el-col>
    </el-row>

    <el-card>
      <template #header>
        <div class="card-header">
          <span>售后工单管理</span>
          <div class="header-actions">
            <el-button type="primary" v-permission="'projects:aftersales:create'" @click="handleCreate">
              <el-icon><Plus /></el-icon>
              新建工单
            </el-button>
          </div>
        </div>
      </template>

      <!-- 搜索筛选 -->
      <el-form :inline="true" class="search-form">
        <el-form-item label="搜索">
          <el-input v-model="searchParams.search" placeholder="工单号/标题/联系人" clearable style="width: 200px" @keyup.enter="handleSearch" />
        </el-form-item>
        <el-form-item label="项目">
          <el-select v-model="searchParams.project" placeholder="选择项目" clearable filterable style="width: 180px">
            <el-option v-for="p in projects" :key="p.id" :label="p.name" :value="p.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="类型">
          <el-select v-model="searchParams.order_type" placeholder="全部" clearable style="width: 120px">
            <el-option label="保修服务" value="WARRANTY" />
            <el-option label="维修服务" value="REPAIR" />
            <el-option label="保养维护" value="MAINTENANCE" />
            <el-option label="升级改造" value="UPGRADE" />
            <el-option label="培训服务" value="TRAINING" />
            <el-option label="巡检服务" value="INSPECTION" />
            <el-option label="客户投诉" value="COMPLAINT" />
            <el-option label="其他" value="OTHER" />
          </el-select>
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="searchParams.status" placeholder="全部" clearable style="width: 120px">
            <el-option label="待处理" value="PENDING" />
            <el-option label="已派单" value="ASSIGNED" />
            <el-option label="处理中" value="IN_PROGRESS" />
            <el-option label="现场服务" value="ON_SITE" />
            <el-option label="等待备件" value="WAITING_PARTS" />
            <el-option label="已解决" value="RESOLVED" />
            <el-option label="已关闭" value="CLOSED" />
          </el-select>
        </el-form-item>
        <el-form-item label="优先级">
          <el-select v-model="searchParams.priority" placeholder="全部" clearable style="width: 100px">
            <el-option label="紧急" value="URGENT" />
            <el-option label="高" value="HIGH" />
            <el-option label="中" value="MEDIUM" />
            <el-option label="低" value="LOW" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="handleSearch">搜索</el-button>
          <el-button @click="handleReset">重置</el-button>
        </el-form-item>
      </el-form>

      <!-- 批量操作工具栏 -->
      <div class="table-toolbar" v-permission="'projects:aftersales:delete'" v-if="canDelete && selectedRows.length > 0">
        <span>已选择 {{ selectedRows.length }} 项</span>
        <el-button type="danger" size="small" v-permission="'projects:aftersales:delete'" @click="batchDelete" :loading="deleteLoading">批量删除</el-button>
      </div>

      <!-- 工单列表 -->
      <el-table :data="orders" border stripe v-loading="loading" @row-click="handleRowClick" @selection-change="handleSelectionChange" style="cursor: pointer;">
        <el-table-column v-permission="'projects:aftersales:delete'" v-if="canDelete" type="selection" width="55" fixed />
        <el-table-column prop="order_no" label="工单号" width="140" fixed />
        <el-table-column prop="title" label="问题标题" min-width="200" show-overflow-tooltip />
        <el-table-column prop="project_name" label="项目" width="150" show-overflow-tooltip />
        <el-table-column prop="customer_name" label="客户" width="150" show-overflow-tooltip />
        <el-table-column label="类型" width="100">
          <template #default="{ row }">
            <el-tag :type="getTypeTagType(row.order_type)" size="small">
              {{ row.order_type_display }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="优先级" width="80" align="center">
          <template #default="{ row }">
            <el-tag :type="getPriorityTagType(row.priority)" size="small">
              {{ row.priority_display }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="getStatusTagType(row.status)" size="small">
              {{ row.status_display }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="contact_person" label="联系人" width="100" />
        <el-table-column prop="assigned_to_name" label="负责人" width="100" />
        <el-table-column label="保修" width="70" align="center">
          <template #default="{ row }">
            <el-tag :type="row.is_warranty ? 'success' : 'warning'" size="small">
              {{ row.is_warranty ? '是' : '否' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="服务次数" width="90" align="center">
          <template #default="{ row }">
            {{ row.service_count || 0 }}
          </template>
        </el-table-column>
        <el-table-column label="总成本" width="110" align="right">
          <template #default="{ row }">
            ¥{{ toFixedSafe(row.total_cost) }}
          </template>
        </el-table-column>
        <el-table-column label="报修时间" width="160">
          <template #default="{ row }">
            {{ formatDateTime(row.reported_at) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click.stop="handleView(row)">查看</el-button>
            <el-button size="small" type="info" @click.stop="handleAttachments(row)">附件</el-button>
            <el-button size="small" @click.stop="handleEdit(row)" v-if="['PENDING', 'ASSIGNED'].includes(row.status)">编辑</el-button>
            <el-button size="small" type="success" @click.stop="handleAssign(row)" v-if="row.status === 'PENDING'">派单</el-button>
            <el-button v-if="canDelete" size="small" type="danger" @click.stop="deleteRow(row)" :loading="deleteLoading">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <!-- 分页 -->
      <el-pagination
        class="pagination"
        v-model:current-page="currentPage"
        v-model:page-size="pageSize"
        :page-sizes="[10, 20, 50, 100]"
        :total="total"
        layout="total, sizes, prev, pager, next, jumper"
        @size-change="loadOrders"
        @current-change="loadOrders"
      />
    </el-card>

    <!-- 新建/编辑工单对话框 -->
    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="800px" destroy-on-close>
      <el-form :model="form" :rules="rules" ref="formRef" label-width="100px">
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="项目" prop="project">
              <el-select v-model="form.project" placeholder="选择项目" filterable style="width: 100%" @change="handleProjectChange">
                <el-option v-for="p in projects" :key="p.id" :label="`${p.code} - ${p.name}`" :value="p.id" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="客户" prop="customer">
              <el-select v-model="form.customer" placeholder="选择客户" filterable style="width: 100%">
                <el-option v-for="c in customers" :key="c.id" :label="c.name" :value="c.id" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="工单类型" prop="order_type">
              <el-select v-model="form.order_type" placeholder="选择类型" style="width: 100%">
                <el-option label="保修服务" value="WARRANTY" />
                <el-option label="维修服务" value="REPAIR" />
                <el-option label="保养维护" value="MAINTENANCE" />
                <el-option label="升级改造" value="UPGRADE" />
                <el-option label="培训服务" value="TRAINING" />
                <el-option label="巡检服务" value="INSPECTION" />
                <el-option label="客户投诉" value="COMPLAINT" />
                <el-option label="其他" value="OTHER" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="优先级" prop="priority">
              <el-select v-model="form.priority" placeholder="选择优先级" style="width: 100%">
                <el-option label="紧急" value="URGENT" />
                <el-option label="高" value="HIGH" />
                <el-option label="中" value="MEDIUM" />
                <el-option label="低" value="LOW" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="问题标题" prop="title">
          <el-input v-model="form.title" placeholder="简要描述问题" />
        </el-form-item>
        <el-form-item label="问题描述" prop="description">
          <el-input v-model="form.description" type="textarea" :rows="3" placeholder="详细描述问题情况" />
        </el-form-item>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="设备信息">
              <el-input v-model="form.equipment_info" placeholder="设备型号/序列号等" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="故障代码">
              <el-input v-model="form.fault_code" placeholder="故障代码" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="联系人" prop="contact_person">
              <el-input v-model="form.contact_person" placeholder="客户联系人" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="联系电话" prop="contact_phone">
              <el-input v-model="form.contact_phone" placeholder="联系电话" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="现场地址">
          <el-input v-model="form.site_address" placeholder="如需现场服务，请填写地址" />
        </el-form-item>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="期望完成日期">
              <el-date-picker v-model="form.expected_date" type="date" placeholder="期望完成日期" style="width: 100%" value-format="YYYY-MM-DD" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="保修期内">
              <el-switch v-model="form.is_warranty" active-text="是" inactive-text="否" />
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSubmit" :loading="submitting">保存</el-button>
      </template>
    </el-dialog>

    <!-- 派单对话框 -->
    <el-dialog v-model="assignDialogVisible" title="派单" width="400px">
      <el-form label-width="80px">
        <el-form-item label="负责人">
          <el-select v-model="assignForm.assigned_to" placeholder="选择负责人" filterable style="width: 100%">
            <el-option v-for="u in users" :key="u.id" :label="u.name || u.username" :value="u.id" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="assignDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="confirmAssign" :loading="submitting">确定派单</el-button>
      </template>
    </el-dialog>

    <!-- 查看详情对话框 -->
    <el-dialog v-model="viewDialogVisible" title="工单详情" width="900px" destroy-on-close>
      <el-descriptions :column="3" border v-if="currentOrder">
        <el-descriptions-item label="工单号">{{ currentOrder.order_no }}</el-descriptions-item>
        <el-descriptions-item label="状态">
          <el-tag :type="getStatusTagType(currentOrder.status)">{{ currentOrder.status_display }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="优先级">
          <el-tag :type="getPriorityTagType(currentOrder.priority)">{{ currentOrder.priority_display }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="项目">{{ currentOrder.project_name }}</el-descriptions-item>
        <el-descriptions-item label="客户">{{ currentOrder.customer_name }}</el-descriptions-item>
        <el-descriptions-item label="工单类型">{{ currentOrder.order_type_display }}</el-descriptions-item>
        <el-descriptions-item label="问题标题" :span="3">{{ currentOrder.title }}</el-descriptions-item>
        <el-descriptions-item label="问题描述" :span="3">{{ currentOrder.description }}</el-descriptions-item>
        <el-descriptions-item label="设备信息">{{ currentOrder.equipment_info }}</el-descriptions-item>
        <el-descriptions-item label="故障代码">{{ currentOrder.fault_code }}</el-descriptions-item>
        <el-descriptions-item label="保修期内">{{ currentOrder.is_warranty ? '是' : '否' }}</el-descriptions-item>
        <el-descriptions-item label="联系人">{{ currentOrder.contact_person }}</el-descriptions-item>
        <el-descriptions-item label="联系电话">{{ currentOrder.contact_phone }}</el-descriptions-item>
        <el-descriptions-item label="现场地址">{{ currentOrder.site_address }}</el-descriptions-item>
        <el-descriptions-item label="负责人">{{ currentOrder.assigned_to_name || '未分配' }}</el-descriptions-item>
        <el-descriptions-item label="报修时间">{{ formatDateTime(currentOrder.reported_at) }}</el-descriptions-item>
        <el-descriptions-item label="期望完成">{{ currentOrder.expected_date }}</el-descriptions-item>
      </el-descriptions>

      <!-- 成本信息 -->
      <el-divider content-position="left">成本信息</el-divider>
      <el-descriptions :column="5" border v-if="currentOrder">
        <el-descriptions-item label="人工费用">¥{{ toFixedSafe(currentOrder.labor_cost) }}</el-descriptions-item>
        <el-descriptions-item label="差旅费用">¥{{ toFixedSafe(currentOrder.travel_cost) }}</el-descriptions-item>
        <el-descriptions-item label="备件费用">¥{{ toFixedSafe(currentOrder.parts_cost) }}</el-descriptions-item>
        <el-descriptions-item label="其他费用">¥{{ toFixedSafe(currentOrder.other_cost) }}</el-descriptions-item>
        <el-descriptions-item label="总成本">
          <span class="total-cost">¥{{ toFixedSafe(currentOrder.total_cost) }}</span>
        </el-descriptions-item>
      </el-descriptions>

      <!-- 解决方案 -->
      <el-divider content-position="left" v-if="currentOrder?.solution">解决方案</el-divider>
      <el-descriptions :column="1" border v-if="currentOrder?.solution">
        <el-descriptions-item label="解决方案">{{ currentOrder.solution }}</el-descriptions-item>
        <el-descriptions-item label="根本原因">{{ currentOrder.root_cause }}</el-descriptions-item>
        <el-descriptions-item label="预防措施">{{ currentOrder.preventive_action }}</el-descriptions-item>
      </el-descriptions>

      <!-- 服务记录 -->
      <el-divider content-position="left">服务记录 ({{ currentOrder?.service_records?.length || 0 }})</el-divider>
      <el-table :data="currentOrder?.service_records || []" border size="small" v-if="currentOrder">
        <el-table-column prop="service_date" label="日期" width="100" />
        <el-table-column prop="service_type_display" label="类型" width="100" />
        <el-table-column prop="technician_name" label="服务人员" width="100" />
        <el-table-column prop="work_hours" label="工时" width="80" align="right" />
        <el-table-column prop="work_content" label="工作内容" show-overflow-tooltip />
        <el-table-column label="费用" width="120" align="right">
          <template #default="{ row }">
            ¥{{ ((row.labor_cost || 0) + (row.travel_cost || 0)).toFixed(2) }}
          </template>
        </el-table-column>
      </el-table>

      <!-- 备件使用 -->
      <el-divider content-position="left">备件使用 ({{ currentOrder?.spare_parts?.length || 0 }})</el-divider>
      <el-table :data="currentOrder?.spare_parts || []" border size="small" v-if="currentOrder">
        <el-table-column prop="item_sku" label="物料编码" width="120" />
        <el-table-column prop="item_name" label="物料名称" />
        <el-table-column prop="qty" label="数量" width="80" align="right" />
        <el-table-column label="单价" width="100" align="right">
          <template #default="{ row }">¥{{ row.unit_cost }}</template>
        </el-table-column>
        <el-table-column label="小计" width="100" align="right">
          <template #default="{ row }">¥{{ (row.qty * row.unit_cost).toFixed(2) }}</template>
        </el-table-column>
        <el-table-column label="保修范围" width="90" align="center">
          <template #default="{ row }">
            <el-tag :type="row.is_warranty ? 'success' : 'warning'" size="small">
              {{ row.is_warranty ? '是' : '否' }}
            </el-tag>
          </template>
        </el-table-column>
      </el-table>

      <template #footer>
        <el-button @click="viewDialogVisible = false">关闭</el-button>
        <el-button type="primary" @click="goToDetail" v-if="currentOrder">处理工单</el-button>
      </template>
    </el-dialog>
    
    <!-- 附件对话框 -->
    <el-dialog v-model="attachmentDialogVisible" title="附件管理" width="800px" destroy-on-close>
      <div class="attachment-header">
        <el-upload
          action="#"
          :auto-upload="false"
          :show-file-list="false"
          :on-change="handleFileUpload"
          multiple
          accept="image/*,video/*,.pdf,.doc,.docx,.xls,.xlsx"
        >
          <el-button type="primary">
            <el-icon><Upload /></el-icon>
            上传附件
          </el-button>
        </el-upload>
        <span class="tip">支持图片、视频、PDF、Word、Excel等格式</span>
      </div>
      
      <el-table :data="attachmentList" border stripe v-loading="attachmentLoading" style="margin-top: 15px;">
        <el-table-column label="预览" width="80" align="center">
          <template #default="{ row }">
            <el-image 
              v-if="row.file_type?.startsWith('image/')" 
              :src="row.file_url" 
              :preview-src-list="[row.file_url]"
              fit="cover" 
              style="width: 50px; height: 50px;"
            />
            <el-icon v-else-if="row.file_type?.startsWith('video/')" :size="30" color="#409EFF"><VideoPlay /></el-icon>
            <el-icon v-else :size="30" color="#909399"><Document /></el-icon>
          </template>
        </el-table-column>
        <el-table-column prop="original_name" label="文件名" show-overflow-tooltip />
        <el-table-column label="大小" width="100">
          <template #default="{ row }">
            {{ formatFileSize(row.file_size) }}
          </template>
        </el-table-column>
        <el-table-column label="分类" width="100">
          <template #default="{ row }">
            {{ getCategoryLabel(row.category) }}
          </template>
        </el-table-column>
        <el-table-column label="上传时间" width="160">
          <template #default="{ row }">
            {{ formatDateTime(row.uploaded_at) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="120">
          <template #default="{ row }">
            <el-button type="primary" link size="small" @click="downloadAttachment(row)">下载</el-button>
            <el-button type="danger" link size="small" @click="handleDeleteAttachment(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      
      <template #footer>
        <el-button @click="attachmentDialogVisible = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Upload, VideoPlay, Document } from '@element-plus/icons-vue'
import { getAfterSalesOrderList, getAfterSalesOrder, createAfterSalesOrder, updateAfterSalesOrder, assignAfterSalesOrder, getAfterSalesStatistics } from '@/api/aftersales'
import { useBatchDelete } from '@/composables/useBatchDelete'
import { usePermission } from '@/composables/usePermission'
import { getUsers } from '@/api/auth'
import { deleteAttachment, getAttachmentList, uploadAttachment } from '@/api/core'
import { getCustomerList } from '@/api/masterdata'
import { getProjectList } from '@/api/projects/project'
import { toFixedSafe } from '@/utils/number'

const router = useRouter()

// 权限检查
const { canDelete } = usePermission()

// 批量删除功能
const { selectedRows, loading: deleteLoading, handleSelectionChange, batchDelete, deleteRow } = useBatchDelete(
  '/projects/aftersales/',
  { onSuccess: () => loadOrders(), confirmTitle: '删除工单', confirmMessage: '确定要删除该工单吗？' }
)

const loading = ref(false)
const submitting = ref(false)
const orders = ref<any[]>([])
const projects = ref<any[]>([])
const customers = ref<any[]>([])
const users = ref<any[]>([])
const total = ref(0)
const currentPage = ref(1)
const pageSize = ref(20)

const dialogVisible = ref(false)
const assignDialogVisible = ref(false)
const viewDialogVisible = ref(false)
const attachmentDialogVisible = ref(false)
const currentOrder = ref(null)
const formRef = ref(null)

// 附件相关
const attachmentList = ref<any[]>([])
const attachmentLoading = ref(false)
const currentAttachmentOrderId = ref(null)

const stats = reactive({
  pending: 0,
  inProgress: 0,
  monthlyCount: 0,
  totalCost: 0,
  avgSatisfaction: 0
})

const searchParams = reactive({
  search: '',
  project: null,
  order_type: '',
  status: '',
  priority: ''
})

const form = reactive({
  id: null,
  project: null,
  customer: null,
  order_type: 'REPAIR',
  priority: 'MEDIUM',
  title: '',
  description: '',
  equipment_info: '',
  fault_code: '',
  contact_person: '',
  contact_phone: '',
  site_address: '',
  expected_date: null,
  is_warranty: true
})

const assignForm = reactive({
  order_id: null,
  assigned_to: null
})

const rules = {
  project: [{ required: true, message: '请选择项目', trigger: 'change' }],
  customer: [{ required: true, message: '请选择客户', trigger: 'change' }],
  order_type: [{ required: true, message: '请选择工单类型', trigger: 'change' }],
  priority: [{ required: true, message: '请选择优先级', trigger: 'change' }],
  title: [{ required: true, message: '请输入问题标题', trigger: 'blur' }],
  description: [{ required: true, message: '请输入问题描述', trigger: 'blur' }],
  contact_person: [{ required: true, message: '请输入联系人', trigger: 'blur' }],
  contact_phone: [{ required: true, message: '请输入联系电话', trigger: 'blur' }]
}

const dialogTitle = computed(() => form.id ? '编辑工单' : '新建工单')

const formatDateTime = (dt) => {
  if (!dt) return '-'
  return new Date(dt).toLocaleString('zh-CN')
}

const getTypeTagType = (type) => {
  const map = {
    WARRANTY: 'success',
    REPAIR: 'warning',
    MAINTENANCE: 'info',
    UPGRADE: 'primary',
    TRAINING: '',
    INSPECTION: 'info',
    COMPLAINT: 'danger',
    OTHER: ''
  }
  return map[type] || ''
}

const getPriorityTagType = (priority) => {
  const map = {
    URGENT: 'danger',
    HIGH: 'warning',
    MEDIUM: '',
    LOW: 'info'
  }
  return map[priority] || ''
}

const getStatusTagType = (status) => {
  const map = {
    PENDING: 'info',
    ASSIGNED: '',
    IN_PROGRESS: 'primary',
    ON_SITE: 'primary',
    WAITING_PARTS: 'warning',
    RESOLVED: 'success',
    CLOSED: 'success',
    CANCELLED: 'info'
  }
  return map[status] || ''
}

const loadOrders = async () => {
  loading.value = true
  try {
    const params = {
      page: currentPage.value,
      page_size: pageSize.value,
      ...searchParams
    }
    // Remove empty values
    Object.keys(params).forEach(key => {
      if (params[key] === '' || params[key] === null) {
        delete params[key]
      }
    })
    
    const res = await getAfterSalesOrderList(params)
    orders.value = res.results || res.results || []
    total.value = res.count || res.count || 0
  } catch (error) {
    console.error('加载工单列表失败:', error)
    ElMessage.error('加载工单列表失败')
  } finally {
    loading.value = false
  }
}

const loadStatistics = async () => {
  try {
    const res = await getAfterSalesStatistics()
    const data = res
    
    stats.monthlyCount = data.monthly_count || 0
    stats.avgSatisfaction = data.satisfaction_avg || 0
    
    // 计算状态统计
    const statusStats = data.status_stats || []
    stats.pending = statusStats.filter(s => ['PENDING', 'ASSIGNED'].includes(s.status))
      .reduce((sum, s) => sum + s.count, 0)
    stats.inProgress = statusStats.filter(s => ['IN_PROGRESS', 'ON_SITE', 'WAITING_PARTS'].includes(s.status))
      .reduce((sum, s) => sum + s.count, 0)
    
    // 成本统计
    const cost = data.cost_stats || {}
    stats.totalCost = (cost.total_labor || 0) + (cost.total_travel || 0) + 
                      (cost.total_parts || 0) + (cost.total_other || 0)
  } catch (error) {
    console.error('加载统计失败:', error)
  }
}

const loadProjects = async () => {
  try {
    const res = await getProjectList()
    projects.value = res.results || res.results || []
  } catch (error) {
    console.error('加载项目列表失败:', error)
  }
}

const loadCustomers = async () => {
  try {
    const res = await getCustomerList()
    customers.value = res.results || res.results || []
  } catch (error) {
    console.error('加载客户列表失败:', error)
  }
}

const loadUsers = async () => {
  try {
    const res = await getUsers()
    users.value = res.results || res.results || []
  } catch (error) {
    console.error('加载用户列表失败:', error)
  }
}

const handleSearch = () => {
  currentPage.value = 1
  loadOrders()
}

const handleReset = () => {
  Object.keys(searchParams).forEach(key => {
    searchParams[key] = key === 'search' ? '' : (key === 'project' ? null : '')
  })
  handleSearch()
}

const resetForm = () => {
  form.id = null
  form.project = null
  form.customer = null
  form.order_type = 'REPAIR'
  form.priority = 'MEDIUM'
  form.title = ''
  form.description = ''
  form.equipment_info = ''
  form.fault_code = ''
  form.contact_person = ''
  form.contact_phone = ''
  form.site_address = ''
  form.expected_date = null
  form.is_warranty = true
}

const handleCreate = () => {
  resetForm()
  dialogVisible.value = true
}

const handleEdit = (row) => {
  Object.assign(form, {
    id: row.id,
    project: row.project,
    customer: row.customer,
    order_type: row.order_type,
    priority: row.priority,
    title: row.title,
    description: row.description,
    equipment_info: row.equipment_info,
    fault_code: row.fault_code,
    contact_person: row.contact_person,
    contact_phone: row.contact_phone,
    site_address: row.site_address,
    expected_date: row.expected_date,
    is_warranty: row.is_warranty
  })
  dialogVisible.value = true
}

const handleProjectChange = (projectId) => {
  const project = projects.value.find(p => p.id === projectId)
  if (project && project.customer) {
    form.customer = project.customer
  }
}

const handleSubmit = async () => {
  try {
    await formRef.value.validate()
    submitting.value = true
    
    const data = { ...form }
    
    if (form.id) {
      await updateAfterSalesOrder(form.id, data)
      ElMessage.success('更新成功')
    } else {
      await createAfterSalesOrder(data)
      ElMessage.success('创建成功')
    }
    
    dialogVisible.value = false
    loadOrders()
    loadStatistics()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error(error.response?.data?.detail || '操作失败')
    }
  } finally {
    submitting.value = false
  }
}

const handleView = async (row) => {
  try {
    const res = await getAfterSalesOrder(row.id)
    currentOrder.value = res
    viewDialogVisible.value = true
  } catch (error) {
    ElMessage.error('加载工单详情失败')
  }
}

const handleRowClick = (row) => {
  handleView(row)
}

const goToDetail = () => {
  viewDialogVisible.value = false
  router.push(`/aftersales/orders/${currentOrder.value.id}`)
}

const handleAssign = (row) => {
  assignForm.order_id = row.id
  assignForm.assigned_to = row.assigned_to
  assignDialogVisible.value = true
}

const confirmAssign = async () => {
  if (!assignForm.assigned_to) {
    ElMessage.warning('请选择负责人')
    return
  }
  
  submitting.value = true
  try {
    await assignAfterSalesOrder(assignForm.order_id, {
      assigned_to: assignForm.assigned_to
    })
    ElMessage.success('派单成功')
    assignDialogVisible.value = false
    loadOrders()
  } catch (error) {
    ElMessage.error('派单失败')
  } finally {
    submitting.value = false
  }
}

// handleDelete 已被 useBatchDelete 的 deleteRow 替代

// ========== 附件相关函数 ==========
const handleAttachments = async (row) => {
  currentAttachmentOrderId.value = row.id
  attachmentDialogVisible.value = true
  loadAttachments()
}

const loadAttachments = async () => {
  attachmentLoading.value = true
  try {
    const res = await getAttachmentList({
      params: {
        related_model: 'AfterSalesOrder',
        related_id: currentAttachmentOrderId.value
      }
    })
    attachmentList.value = res.results || res.results || []
  } catch (error) {
    console.error('加载附件失败:', error)
  } finally {
    attachmentLoading.value = false
  }
}

const handleFileUpload = async (file) => {
  try {
    const formData = new FormData()
    formData.append('file', file.raw)
    formData.append('related_model', 'AfterSalesOrder')
    formData.append('related_id', currentAttachmentOrderId.value)
    
    let category = 'OTHER'
    if (file.raw.type.startsWith('image/')) {
      category = 'FAULT_IMAGE'
    } else if (file.raw.type.startsWith('video/')) {
      category = 'FAULT_VIDEO'
    }
    formData.append('category', category)
    
    await uploadAttachment(formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })
    
    ElMessage.success(`${file.name} 上传成功`)
    loadAttachments()
  } catch (error) {
    ElMessage.error(`${file.name} 上传失败`)
  }
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

const downloadAttachment = (attachment) => {
  window.open(`/api/core/attachments/${attachment.id}/download/`, '_blank')
}

const handleDeleteAttachment = async (attachment) => {
  try {
    await ElMessageBox.confirm('确定要删除该附件吗？', '删除确认', { type: 'warning' })
    await deleteAttachment(attachment.id)
    ElMessage.success('删除成功')
    loadAttachments()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('删除失败')
    }
  }
}

onMounted(() => {
  loadOrders()
  loadStatistics()
  loadProjects()
  loadCustomers()
  loadUsers()
})
</script>

<style scoped>
.aftersales-list {
  padding: 20px;
}

.stats-row {
  margin-bottom: 20px;
}

.stat-card {
  text-align: center;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.search-form {
  margin-bottom: 15px;
}

.pagination {
  margin-top: 20px;
  text-align: right;
}

.total-cost {
  font-weight: bold;
  color: #e6a23c;
  font-size: 16px;
}

.attachment-header {
  display: flex;
  align-items: center;
  gap: 15px;
}

.attachment-header .tip {
  color: #909399;
  font-size: 12px;
}
</style>
