<template>
  <div class="outsource-list">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>外协加工管理</span>
          <el-button type="primary" v-permission="'purchase:outsource_order:create'" @click="handleAdd">
            <el-icon><Plus /></el-icon>
            新建外协单
          </el-button>
        </div>
      </template>

      <!-- 搜索表单 -->
      <el-form :inline="true" :model="searchForm" class="search-form">
        <el-form-item label="供应商">
          <el-select v-model="searchForm.supplier" placeholder="选择供应商" clearable filterable style="width: 180px;">
            <el-option v-for="s in suppliers" :key="s.id" :label="s.name" :value="s.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="searchForm.status" placeholder="选择状态" clearable style="width: 120px;">
            <el-option label="草稿" value="DRAFT" />
            <el-option label="已确认" value="CONFIRMED" />
            <el-option label="加工中" value="PROCESSING" />
            <el-option label="部分完成" value="PARTIAL" />
            <el-option label="已完成" value="COMPLETED" />
            <el-option label="已取消" value="CANCELLED" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="loadOrders">查询</el-button>
          <el-button @click="resetSearch">重置</el-button>
        </el-form-item>
      </el-form>

      <!-- 数据表格 -->
      <!-- 批量操作 -->
      <div v-if="selectedRows.length > 0" class="batch-toolbar">
        <span class="batch-info">已选择 {{ selectedRows.length }} 项</span>
        <el-button type="danger" size="small" @click="batchDelete">批量删除</el-button>
        <el-button size="small" @click="batchExport">导出选中</el-button>
      </div>
      <el-table :data="orders" v-loading="loading" stripe border @selection-change="handleSelectionChange">
        <el-table-column type="selection" width="45" />
        <el-table-column prop="order_no" label="外协单号" width="140" />
        <el-table-column prop="supplier_name" label="外协供应商" width="150" show-overflow-tooltip />
        <el-table-column prop="project_name" label="关联项目" width="150" show-overflow-tooltip />
        <el-table-column prop="lines_count" label="加工项数" width="80" align="center" />
        <el-table-column prop="total_with_tax" label="含税金额" width="120" align="right">
          <template #default="{ row }">
            ¥{{ parseFloat(row.total_with_tax || 0).toFixed(2) }}
          </template>
        </el-table-column>
        <el-table-column prop="order_date" label="下单日期" width="110" />
        <el-table-column prop="required_date" label="要求完成" width="110" />
        <el-table-column prop="status_display" label="状态" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)" size="small">{{ row.status_display }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="320" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="handleView(row)">查看</el-button>
            <el-button size="small" v-permission="'purchase:outsource_order:edit'" @click="handleEdit(row)" v-if="row.status === 'DRAFT'">编辑</el-button>
            <el-button size="small" type="warning" @click="handleConfirm(row)" v-if="row.status === 'DRAFT'">确认</el-button>
            <el-button size="small" type="primary" @click="handleIssue(row)" v-if="row.status === 'CONFIRMED' || row.status === 'PROCESSING'">发料</el-button>
            <el-button size="small" type="success" @click="handleReceipt(row)" v-if="row.status === 'PROCESSING' || row.status === 'PARTIAL'">收货</el-button>
            <el-button size="small" type="danger" @click="handleCancel(row)" v-if="row.status === 'DRAFT' || row.status === 'CONFIRMED'">取消</el-button>
          </template>
        </el-table-column>
      </el-table>

      <!-- 分页 -->
      <el-pagination
        v-model:current-page="pagination.page"
        v-model:page-size="pagination.pageSize"
        :total="pagination.total"
        :page-sizes="[10, 20, 50, 100]"
        layout="total, sizes, prev, pager, next"
        @size-change="loadOrders"
        @current-change="loadOrders"
        style="margin-top: 16px; justify-content: flex-end;"
      />
    </el-card>

    <!-- 新建/编辑对话框 -->
    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="1000px" destroy-on-close>
      <el-form :model="form" :rules="rules" ref="formRef" label-width="100px">
        <el-row :gutter="20">
          <el-col :span="8">
            <el-form-item label="外协供应商" prop="supplier">
              <el-select v-model="form.supplier" placeholder="选择供应商" filterable style="width: 100%;">
                <el-option v-for="s in suppliers" :key="s.id" :label="s.name" :value="s.id" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="关联项目">
              <el-select v-model="form.project" placeholder="选择项目" filterable clearable style="width: 100%;">
                <el-option v-for="p in projects" :key="p.id" :label="p.name" :value="p.id" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="要求完成日期" prop="required_date">
              <el-date-picker v-model="form.required_date" type="date" value-format="YYYY-MM-DD" placeholder="选择日期" style="width: 100%;" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="8">
            <el-form-item label="联系人">
              <el-input v-model="form.contact_person" placeholder="联系人" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="联系电话">
              <el-input v-model="form.contact_phone" placeholder="联系电话" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="税率">
              <el-select v-model="form.tax_rate" style="width: 100%;">
                <el-option :value="0" label="0%" />
                <el-option :value="3" label="3%" />
                <el-option :value="6" label="6%" />
                <el-option :value="13" label="13%" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="送货地址">
          <el-input v-model="form.delivery_address" placeholder="送货地址" />
        </el-form-item>
        
        <!-- 加工明细 -->
        <el-divider content-position="left">加工明细</el-divider>
        <el-button type="primary" size="small" @click="addLine" style="margin-bottom: 10px;">
          <el-icon><Plus /></el-icon>
          添加加工项
        </el-button>
        
        <el-table :data="form.lines" border size="small">
          <el-table-column label="物料" min-width="180">
            <template #default="{ row }">
              <el-select v-model="row.item" placeholder="选择物料" filterable style="width: 100%;">
                <el-option v-for="item in items" :key="item.id" :label="`${item.sku} - ${item.name}`" :value="item.id" />
              </el-select>
            </template>
          </el-table-column>
          <el-table-column label="加工类型" width="120">
            <template #default="{ row }">
              <el-select v-model="row.process_type" size="small" style="width: 100%;">
                <el-option label="车削" value="TURNING" />
                <el-option label="铣削" value="MILLING" />
                <el-option label="磨削" value="GRINDING" />
                <el-option label="钻孔" value="DRILLING" />
                <el-option label="线切割" value="WIRE_CUT" />
                <el-option label="电火花" value="EDM" />
                <el-option label="激光切割" value="LASER_CUT" />
                <el-option label="折弯" value="BENDING" />
                <el-option label="焊接" value="WELDING" />
                <el-option label="表面处理" value="SURFACE" />
                <el-option label="热处理" value="HEAT_TREAT" />
                <el-option label="其他" value="OTHER" />
              </el-select>
            </template>
          </el-table-column>
          <el-table-column label="加工内容" min-width="150">
            <template #default="{ row }">
              <el-input v-model="row.process_content" size="small" placeholder="加工内容" />
            </template>
          </el-table-column>
          <el-table-column label="图纸号" width="100">
            <template #default="{ row }">
              <el-input v-model="row.drawing_no" size="small" placeholder="图纸号" />
            </template>
          </el-table-column>
          <el-table-column label="数量" width="80">
            <template #default="{ row }">
              <el-input-number v-model="row.qty" :min="1" :precision="0" size="small" controls-position="right" style="width: 100%;" />
            </template>
          </el-table-column>
          <el-table-column label="单价" width="100">
            <template #default="{ row }">
              <el-input-number v-model="row.unit_price" :min="0" :precision="2" size="small" controls-position="right" style="width: 100%;" />
            </template>
          </el-table-column>
          <el-table-column label="加工费" width="100" align="right">
            <template #default="{ row }">
              ¥{{ ((row.qty || 0) * (row.unit_price || 0)).toFixed(2) }}
            </template>
          </el-table-column>
          <el-table-column label="操作" width="60" align="center" fixed="right">
            <template #default="{ $index }">
              <el-button type="danger" size="small" link @click="removeLine($index)">
                <el-icon><Delete /></el-icon>
              </el-button>
            </template>
          </el-table-column>
        </el-table>
        
        <div class="total-section">
          <div class="total-row">
            <span class="label">加工费合计：</span>
            <span class="value">¥{{ calculateTotal().toFixed(2) }}</span>
          </div>
          <div class="total-row">
            <span class="label">税额 ({{ form.tax_rate }}%)：</span>
            <span class="value">¥{{ calculateTax().toFixed(2) }}</span>
          </div>
          <div class="total-row total">
            <span class="label">含税总额：</span>
            <span class="amount">¥{{ calculateTotalWithTax().toFixed(2) }}</span>
          </div>
        </div>
        
        <el-form-item label="备注">
          <el-input v-model="form.notes" type="textarea" :rows="2" placeholder="备注" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSave" :loading="saving">保存</el-button>
      </template>
    </el-dialog>

    <!-- 查看详情对话框 -->
    <el-dialog v-model="viewDialogVisible" title="外协单详情" width="900px">
      <el-descriptions :column="3" border v-if="currentOrder">
        <el-descriptions-item label="外协单号">{{ currentOrder.order_no }}</el-descriptions-item>
        <el-descriptions-item label="状态">
          <el-tag :type="getStatusType(currentOrder.status)">{{ currentOrder.status_display }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="下单日期">{{ currentOrder.order_date }}</el-descriptions-item>
        <el-descriptions-item label="供应商">{{ currentOrder.supplier_name }}</el-descriptions-item>
        <el-descriptions-item label="关联项目">{{ currentOrder.project_name || '-' }}</el-descriptions-item>
        <el-descriptions-item label="要求完成日期">{{ currentOrder.required_date }}</el-descriptions-item>
        <el-descriptions-item label="联系人">{{ currentOrder.contact_person || '-' }}</el-descriptions-item>
        <el-descriptions-item label="联系电话">{{ currentOrder.contact_phone || '-' }}</el-descriptions-item>
        <el-descriptions-item label="含税总额">¥{{ parseFloat(currentOrder.total_with_tax || 0).toFixed(2) }}</el-descriptions-item>
      </el-descriptions>
      
      <el-divider content-position="left">加工明细</el-divider>
      <el-table :data="currentOrder?.lines || []" border size="small">
        <el-table-column prop="item_sku" label="物料编码" width="100" />
        <el-table-column prop="item_name" label="物料名称" min-width="150" />
        <el-table-column prop="process_type_display" label="加工类型" width="100" />
        <el-table-column prop="process_content" label="加工内容" min-width="150" show-overflow-tooltip />
        <el-table-column prop="drawing_no" label="图纸号" width="100" />
        <el-table-column prop="qty" label="数量" width="70" align="right" />
        <el-table-column label="单价" width="90" align="right">
          <template #default="{ row }">¥{{ parseFloat(row.unit_price || 0).toFixed(2) }}</template>
        </el-table-column>
        <el-table-column label="加工费" width="100" align="right">
          <template #default="{ row }">¥{{ parseFloat(row.process_amount || 0).toFixed(2) }}</template>
        </el-table-column>
        <el-table-column label="进度" width="120" align="center">
          <template #default="{ row }">
            <span class="progress-text">发{{ row.sent_qty }}/收{{ row.received_qty }}/{{ row.qty }}</span>
          </template>
        </el-table-column>
      </el-table>
    </el-dialog>

    <!-- 发料对话框 -->
    <el-dialog v-model="issueDialogVisible" title="外协发料" width="800px" destroy-on-close>
      <el-form :model="issueForm" ref="issueFormRef" label-width="100px">
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="发料仓库" prop="warehouse" required>
              <el-select v-model="issueForm.warehouse" placeholder="选择仓库" style="width: 100%;">
                <el-option v-for="w in warehouses" :key="w.id" :label="w.name" :value="w.id" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="发料日期" prop="issue_date" required>
              <el-date-picker v-model="issueForm.issue_date" type="date" value-format="YYYY-MM-DD" style="width: 100%;" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="物流公司">
              <el-input v-model="issueForm.logistics_company" placeholder="物流公司" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="运单号">
              <el-input v-model="issueForm.tracking_number" placeholder="运单号" />
            </el-form-item>
          </el-col>
        </el-row>
        
        <el-divider content-position="left">发料明细</el-divider>
        <el-table :data="issueForm.lines" border size="small">
          <el-table-column prop="item_name" label="物料" min-width="150" />
          <el-table-column prop="process_content" label="加工内容" min-width="120" show-overflow-tooltip />
          <el-table-column label="待发数量" width="90" align="right">
            <template #default="{ row }">{{ row.remaining_qty }}</template>
          </el-table-column>
          <el-table-column label="本次发料" width="100">
            <template #default="{ row }">
              <el-input-number v-model="row.qty" :min="0" :max="row.remaining_qty" :precision="0" size="small" style="width: 100%;" />
            </template>
          </el-table-column>
          <el-table-column label="重量(kg)" width="100">
            <template #default="{ row }">
              <el-input-number v-model="row.weight" :min="0" :precision="3" size="small" style="width: 100%;" />
            </template>
          </el-table-column>
        </el-table>
      </el-form>
      <template #footer>
        <el-button @click="issueDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitIssue" :loading="saving">确认发料</el-button>
      </template>
    </el-dialog>

    <!-- 收货对话框 -->
    <el-dialog v-model="receiptDialogVisible" title="外协收货" width="900px" destroy-on-close>
      <el-form :model="receiptForm" ref="receiptFormRef" label-width="100px">
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="入库仓库" prop="warehouse" required>
              <el-select v-model="receiptForm.warehouse" placeholder="选择仓库" style="width: 100%;">
                <el-option v-for="w in warehouses" :key="w.id" :label="w.name" :value="w.id" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="收货日期" prop="receipt_date" required>
              <el-date-picker v-model="receiptForm.receipt_date" type="date" value-format="YYYY-MM-DD" style="width: 100%;" />
            </el-form-item>
          </el-col>
        </el-row>
        
        <el-divider content-position="left">收货明细</el-divider>
        <el-table :data="receiptForm.lines" border size="small">
          <el-table-column prop="item_name" label="物料" min-width="150" />
          <el-table-column prop="process_content" label="加工内容" min-width="120" show-overflow-tooltip />
          <el-table-column label="已发料" width="70" align="right">
            <template #default="{ row }">{{ row.sent_qty }}</template>
          </el-table-column>
          <el-table-column label="已收货" width="70" align="right">
            <template #default="{ row }">{{ row.received_qty }}</template>
          </el-table-column>
          <el-table-column label="本次收货" width="90">
            <template #default="{ row }">
              <el-input-number v-model="row.qty" :min="0" :max="row.sent_qty - row.received_qty" :precision="0" size="small" style="width: 100%;" />
            </template>
          </el-table-column>
          <el-table-column label="合格数量" width="90">
            <template #default="{ row }">
              <el-input-number v-model="row.qualified_qty" :min="0" :max="row.qty" :precision="0" size="small" style="width: 100%;" />
            </template>
          </el-table-column>
          <el-table-column label="不合格数量" width="90">
            <template #default="{ row }">
              {{ (row.qty || 0) - (row.qualified_qty || 0) }}
            </template>
          </el-table-column>
        </el-table>
      </el-form>
      <template #footer>
        <el-button @click="receiptDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitReceipt" :loading="saving">确认收货</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Delete } from '@element-plus/icons-vue'
import { getItemList, getSupplierList, getWarehouseList } from '@/api/masterdata'
import { getProjectList } from '@/api/projects/project'
import {
getOutsourceOrders, getOutsourceOrder, createOutsourceOrder, updateOutsourceOrder,
  confirmOutsourceOrder, cancelOutsourceOrder,
  createOutsourceIssue, confirmOutsourceIssue,
  createOutsourceReceipt, confirmOutsourceReceipt
} from '@/api/purchase'
import { useBatchOperation } from '@/composables/useBatchOperation'

const { selectedRows, handleSelectionChange, batchDelete, batchExport } = useBatchOperation('/api/masterdata/')


const loading = ref(false)
const saving = ref(false)
const orders = ref([])
const suppliers = ref([])
const projects = ref([])
const items = ref([])
const warehouses = ref([])
const dialogVisible = ref(false)
const dialogTitle = ref('新建外协单')
const viewDialogVisible = ref(false)
const issueDialogVisible = ref(false)
const receiptDialogVisible = ref(false)
const currentOrder = ref(null)
const formRef = ref(null)
const issueFormRef = ref(null)
const receiptFormRef = ref(null)
const isEdit = ref(false)

const searchForm = reactive({
  supplier: null,
  status: null
})

const pagination = reactive({
  page: 1,
  pageSize: 20,
  total: 0
})

const form = reactive({
  id: null,
  supplier: null,
  project: null,
  required_date: '',
  tax_rate: 13,
  contact_person: '',
  contact_phone: '',
  delivery_address: '',
  notes: '',
  lines: []
})

const issueForm = reactive({
  outsource_order: null,
  warehouse: null,
  issue_date: new Date().toISOString().split('T')[0],
  logistics_company: '',
  tracking_number: '',
  lines: []
})

const receiptForm = reactive({
  outsource_order: null,
  warehouse: null,
  receipt_date: new Date().toISOString().split('T')[0],
  lines: []
})

const rules = {
  supplier: [{ required: true, message: '请选择供应商', trigger: 'change' }],
  required_date: [{ required: true, message: '请选择要求完成日期', trigger: 'change' }]
}

const getStatusType = (status) => {
  const types = {
    'DRAFT': 'info',
    'CONFIRMED': 'warning',
    'PROCESSING': 'primary',
    'PARTIAL': 'warning',
    'COMPLETED': 'success',
    'CANCELLED': 'danger'
  }
  return types[status] || 'info'
}

const loadOrders = async () => {
  loading.value = true
  try {
    const params = {
      page: pagination.page,
      page_size: pagination.pageSize,
      ...searchForm
    }
    Object.keys(params).forEach(k => { if (!params[k]) delete params[k] })
    
    const res = await getOutsourceOrders(params)
    orders.value = res.results || res || []
    pagination.total = res.count || 0
  } catch (error) {
    ElMessage.error('加载外协单列表失败')
  } finally {
    loading.value = false
  }
}

const loadSuppliers = async () => {
  try {
    const res = await getSupplierList({ page_size: 500 })
    suppliers.value = res.results || res || []
  } catch (error) {
    console.error('加载供应商失败:', error)
  }
}

const loadProjects = async () => {
  try {
    const res = await getProjectList({ page_size: 200 })
    projects.value = res.results || res || []
  } catch (error) {
    console.error('加载项目失败:', error)
  }
}

const loadItems = async () => {
  try {
    const res = await getItemList({ page_size: 1000 })
    items.value = res.results || res || []
  } catch (error) {
    console.error('加载物料失败:', error)
  }
}

const loadWarehouses = async () => {
  try {
    const res = await getWarehouseList()
    warehouses.value = res.results || res || []
  } catch (error) {
    console.error('加载仓库失败:', error)
  }
}

const resetSearch = () => {
  searchForm.supplier = null
  searchForm.status = null
  pagination.page = 1
  loadOrders()
}

const handleAdd = () => {
  dialogTitle.value = '新建外协单'
  isEdit.value = false
  Object.assign(form, {
    id: null,
    supplier: null,
    project: null,
    required_date: '',
    tax_rate: 13,
    contact_person: '',
    contact_phone: '',
    delivery_address: '',
    notes: '',
    lines: [{ item: null, process_type: 'OTHER', process_content: '', drawing_no: '', qty: 1, unit_price: 0, material_provided: true }]
  })
  dialogVisible.value = true
}

const handleEdit = async (row) => {
  dialogTitle.value = '编辑外协单'
  isEdit.value = true
  
  try {
    const res = await getOutsourceOrder(row.id)
    const data = res.data || res
    
    Object.assign(form, {
      id: data.id,
      supplier: data.supplier,
      project: data.project,
      required_date: data.required_date,
      tax_rate: data.tax_rate,
      contact_person: data.contact_person || '',
      contact_phone: data.contact_phone || '',
      delivery_address: data.delivery_address || '',
      notes: data.notes || '',
      lines: (data.lines || []).map(line => ({
        item: line.item,
        process_type: line.process_type,
        process_content: line.process_content || '',
        drawing_no: line.drawing_no || '',
        qty: line.qty,
        unit_price: parseFloat(line.unit_price || 0),
        material_provided: line.material_provided
      }))
    })
    
    if (form.lines.length === 0) {
      form.lines = [{ item: null, process_type: 'OTHER', process_content: '', drawing_no: '', qty: 1, unit_price: 0, material_provided: true }]
    }
    
    dialogVisible.value = true
  } catch (error) {
    ElMessage.error('获取外协单详情失败')
  }
}

const handleView = async (row) => {
  try {
    const res = await getOutsourceOrder(row.id)
    currentOrder.value = res.data || res
    viewDialogVisible.value = true
  } catch (error) {
    ElMessage.error('获取外协单详情失败')
  }
}

const addLine = () => {
  form.lines.push({ item: null, process_type: 'OTHER', process_content: '', drawing_no: '', qty: 1, unit_price: 0, material_provided: true })
}

const removeLine = (index) => {
  if (form.lines.length > 1) {
    form.lines.splice(index, 1)
  } else {
    ElMessage.warning('至少保留一行明细')
  }
}

const calculateTotal = () => {
  return form.lines.reduce((sum, line) => sum + (line.qty || 0) * (line.unit_price || 0), 0)
}

const calculateTax = () => {
  return calculateTotal() * (form.tax_rate || 0) / 100
}

const calculateTotalWithTax = () => {
  return calculateTotal() + calculateTax()
}

const handleSave = async () => {
  try {
    await formRef.value?.validate()
    
    const validLines = form.lines.filter(line => line.item && line.qty > 0)
    if (validLines.length === 0) {
      ElMessage.warning('请至少添加一行有效的加工明细')
      return
    }
    
    saving.value = true
    
    const payload = {
      supplier: form.supplier,
      project: form.project,
      required_date: form.required_date,
      tax_rate: form.tax_rate,
      contact_person: form.contact_person,
      contact_phone: form.contact_phone,
      delivery_address: form.delivery_address,
      notes: form.notes,
      lines: validLines
    }
    
    if (isEdit.value) {
      await updateOutsourceOrder(form.id, payload)
      ElMessage.success('更新外协单成功')
    } else {
      await createOutsourceOrder(payload)
      ElMessage.success('创建外协单成功')
    }
    
    dialogVisible.value = false
    loadOrders()
  } catch (error) {
    ElMessage.error(error.response?.data?.error || '保存失败')
  } finally {
    saving.value = false
  }
}

const handleConfirm = async (row) => {
  try {
    await ElMessageBox.confirm('确定要确认该外协单吗？确认后将无法修改。', '确认外协单', { type: 'warning' })
    await confirmOutsourceOrder(row.id)
    ElMessage.success('外协单已确认')
    loadOrders()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error(error.response?.data?.error || '确认失败')
    }
  }
}

const handleCancel = async (row) => {
  try {
    await ElMessageBox.confirm('确定要取消该外协单吗？', '取消外协单', { type: 'warning' })
    await cancelOutsourceOrder(row.id)
    ElMessage.success('外协单已取消')
    loadOrders()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error(error.response?.data?.error || '取消失败')
    }
  }
}

const handleIssue = async (row) => {
  try {
    const res = await getOutsourceOrder(row.id)
    const data = res.data || res
    
    issueForm.outsource_order = data.id
    issueForm.warehouse = null
    issueForm.issue_date = new Date().toISOString().split('T')[0]
    issueForm.logistics_company = ''
    issueForm.tracking_number = ''
    issueForm.lines = (data.lines || [])
      .filter(line => line.qty > line.sent_qty)
      .map(line => ({
        outsource_line: line.id,
        item: line.item,
        item_name: `${line.item_sku} - ${line.item_name}`,
        process_content: line.process_content,
        remaining_qty: line.qty - line.sent_qty,
        qty: line.qty - line.sent_qty,
        weight: 0
      }))
    
    if (issueForm.lines.length === 0) {
      ElMessage.warning('没有待发料的明细')
      return
    }
    
    issueDialogVisible.value = true
  } catch (error) {
    ElMessage.error('获取外协单详情失败')
  }
}

const submitIssue = async () => {
  if (!issueForm.warehouse) {
    ElMessage.warning('请选择发料仓库')
    return
  }
  
  const validLines = issueForm.lines.filter(line => line.qty > 0)
  if (validLines.length === 0) {
    ElMessage.warning('请输入发料数量')
    return
  }
  
  saving.value = true
  try {
    // 创建发料单
    const issueRes = await createOutsourceIssue({
      outsource_order: issueForm.outsource_order,
      warehouse: issueForm.warehouse,
      issue_date: issueForm.issue_date,
      logistics_company: issueForm.logistics_company,
      tracking_number: issueForm.tracking_number,
      lines: validLines.map(line => ({
        outsource_line: line.outsource_line,
        item: line.item,
        qty: line.qty,
        weight: line.weight
      }))
    })
    
    // 确认发料
    await confirmOutsourceIssue(issueRes.id)
    
    ElMessage.success('发料成功')
    issueDialogVisible.value = false
    loadOrders()
  } catch (error) {
    ElMessage.error(error.response?.data?.error || '发料失败')
  } finally {
    saving.value = false
  }
}

const handleReceipt = async (row) => {
  try {
    const res = await getOutsourceOrder(row.id)
    const data = res.data || res
    
    receiptForm.outsource_order = data.id
    receiptForm.warehouse = null
    receiptForm.receipt_date = new Date().toISOString().split('T')[0]
    receiptForm.lines = (data.lines || [])
      .filter(line => line.sent_qty > line.received_qty)
      .map(line => ({
        outsource_line: line.id,
        item: line.item,
        item_name: `${line.item_sku} - ${line.item_name}`,
        process_content: line.process_content,
        sent_qty: line.sent_qty,
        received_qty: line.received_qty,
        qty: line.sent_qty - line.received_qty,
        qualified_qty: line.sent_qty - line.received_qty
      }))
    
    if (receiptForm.lines.length === 0) {
      ElMessage.warning('没有待收货的明细')
      return
    }
    
    receiptDialogVisible.value = true
  } catch (error) {
    ElMessage.error('获取外协单详情失败')
  }
}

const submitReceipt = async () => {
  if (!receiptForm.warehouse) {
    ElMessage.warning('请选择入库仓库')
    return
  }
  
  const validLines = receiptForm.lines.filter(line => line.qty > 0)
  if (validLines.length === 0) {
    ElMessage.warning('请输入收货数量')
    return
  }
  
  saving.value = true
  try {
    // 创建收货单
    const receiptRes = await createOutsourceReceipt({
      outsource_order: receiptForm.outsource_order,
      warehouse: receiptForm.warehouse,
      receipt_date: receiptForm.receipt_date,
      lines: validLines.map(line => ({
        outsource_line: line.outsource_line,
        item: line.item,
        qty: line.qty,
        qualified_qty: line.qualified_qty,
        rejected_qty: line.qty - line.qualified_qty
      }))
    })
    
    // 确认收货
    await confirmOutsourceReceipt(receiptRes.id)
    
    ElMessage.success('收货成功')
    receiptDialogVisible.value = false
    loadOrders()
  } catch (error) {
    ElMessage.error(error.response?.data?.error || '收货失败')
  } finally {
    saving.value = false
  }
}

onMounted(() => {
  loadOrders()
  loadSuppliers()
  loadProjects()
  loadItems()
  loadWarehouses()
})
</script>

<style scoped>
.outsource-list {
  padding: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.search-form {
  margin-bottom: 16px;
}

.total-section {
  text-align: right;
  margin-top: 15px;
  padding: 10px;
  background: #fafafa;
  border-radius: 4px;
}

.total-row {
  display: flex;
  justify-content: flex-end;
  align-items: center;
  margin-bottom: 5px;
}

.total-row .label {
  color: #606266;
  margin-right: 10px;
}

.total-row .value {
  min-width: 100px;
  text-align: right;
}

.total-row.total {
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px dashed #dcdfe6;
}

.total-row .amount {
  color: #f56c6c;
  font-weight: bold;
  font-size: 18px;
}

.progress-text {
  font-size: 12px;
  color: #909399;
}
</style>

