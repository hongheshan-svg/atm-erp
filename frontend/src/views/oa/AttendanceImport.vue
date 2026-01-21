<template>
  <div class="attendance-import-page">
    <!-- 页面头部 -->
    <div class="page-header">
      <h2>
        <el-icon><Upload /></el-icon>
        考勤数据导入
      </h2>
    </div>

    <el-row :gutter="20">
      <!-- 左侧：导入操作 -->
      <el-col :span="14">
        <el-card class="import-card">
          <template #header>
            <span>导入企业微信考勤数据</span>
          </template>
          
          <!-- 操作指南 -->
          <el-alert type="info" :closable="false" class="guide-alert">
            <template #title>
              <strong>操作步骤</strong>
            </template>
            <ol class="guide-steps">
              <li>登录 <a href="https://work.weixin.qq.com/wework_admin/loginpage_wx" target="_blank">企业微信管理后台</a></li>
              <li>进入 <strong>应用管理</strong> → <strong>打卡</strong></li>
              <li>点击 <strong>打卡统计</strong> → 选择日期范围</li>
              <li>点击 <strong>导出</strong> 按钮下载Excel文件</li>
              <li>在下方上传导出的Excel文件</li>
            </ol>
          </el-alert>

          <!-- 文件上传 -->
          <div class="upload-section">
            <el-upload
              ref="uploadRef"
              class="upload-area"
              drag
              :auto-upload="false"
              :limit="1"
              accept=".xlsx,.xls,.csv"
              :on-change="handleFileChange"
              :on-exceed="handleExceed"
              :file-list="fileList"
            >
              <el-icon class="el-icon--upload"><UploadFilled /></el-icon>
              <div class="el-upload__text">
                将企业微信导出的Excel文件拖到此处，或 <em>点击上传</em>
              </div>
              <template #tip>
                <div class="el-upload__tip">
                  支持 .xlsx、.xls、.csv 格式，文件大小不超过 10MB
                </div>
              </template>
            </el-upload>
          </div>

          <!-- 导入月份选择 -->
          <el-form :model="importForm" label-width="100px" class="import-form">
            <el-form-item label="考勤月份">
              <el-date-picker
                v-model="importForm.month"
                type="month"
                placeholder="选择月份"
                format="YYYY年MM月"
                value-format="YYYY-MM"
              />
            </el-form-item>
            <el-form-item label="数据来源">
              <el-select v-model="importForm.source" style="width: 200px">
                <el-option label="企业微信导出" value="WECHAT_WORK" />
                <el-option label="钉钉导出" value="DINGTALK" />
                <el-option label="其他系统" value="OTHER" />
              </el-select>
            </el-form-item>
            <el-form-item label="覆盖模式">
              <el-radio-group v-model="importForm.overwrite">
                <el-radio :label="false">跳过已有记录</el-radio>
                <el-radio :label="true">覆盖已有记录</el-radio>
              </el-radio-group>
            </el-form-item>
          </el-form>

          <!-- 操作按钮 -->
          <div class="action-buttons">
            <el-button type="primary" @click="handlePreview" :loading="previewing" :disabled="!fileList.length">
              <el-icon><View /></el-icon> 预览数据
            </el-button>
            <el-button type="success" @click="handleImport" :loading="importing" :disabled="!previewData.length">
              <el-icon><Check /></el-icon> 确认导入
            </el-button>
            <el-button @click="handleDownloadTemplate">
              <el-icon><Download /></el-icon> 下载模板
            </el-button>
          </div>
        </el-card>

        <!-- 数据预览 -->
        <el-card v-if="previewData.length" class="preview-card">
          <template #header>
            <div class="card-header">
              <span>数据预览 (共 {{ previewData.length }} 条)</span>
              <el-tag type="success" v-if="previewStats.valid">有效: {{ previewStats.valid }}</el-tag>
              <el-tag type="warning" v-if="previewStats.skip">跳过: {{ previewStats.skip }}</el-tag>
              <el-tag type="danger" v-if="previewStats.error">错误: {{ previewStats.error }}</el-tag>
            </div>
          </template>
          
          <el-table :data="previewData" max-height="400" size="small" stripe>
            <el-table-column type="index" width="50" label="#" />
            <el-table-column prop="employee_name" label="姓名" width="100" />
            <el-table-column prop="employee_id" label="工号" width="100" />
            <el-table-column prop="date" label="日期" width="110" />
            <el-table-column prop="check_in" label="签到时间" width="90" />
            <el-table-column prop="check_out" label="签退时间" width="90" />
            <el-table-column prop="work_hours" label="工时" width="70" align="center" />
            <el-table-column prop="status" label="状态" width="80">
              <template #default="{ row }">
                <el-tag :type="getStatusType(row.status)" size="small">
                  {{ row.status_text }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="remark" label="备注" min-width="120" show-overflow-tooltip />
            <el-table-column label="导入状态" width="100">
              <template #default="{ row }">
                <el-tag :type="row.import_status === 'valid' ? 'success' : row.import_status === 'skip' ? 'warning' : 'danger'" size="small">
                  {{ row.import_status === 'valid' ? '待导入' : row.import_status === 'skip' ? '将跳过' : '错误' }}
                </el-tag>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>

      <!-- 右侧：导入历史和统计 -->
      <el-col :span="10">
        <!-- 本月考勤统计 -->
        <el-card class="stats-card">
          <template #header>
            <span>本月考勤统计</span>
          </template>
          
          <el-row :gutter="15" class="stats-row">
            <el-col :span="8">
              <el-statistic title="应出勤天数" :value="monthStats.work_days" />
            </el-col>
            <el-col :span="8">
              <el-statistic title="已导入记录" :value="monthStats.imported_count" />
            </el-col>
            <el-col :span="8">
              <el-statistic title="异常记录" :value="monthStats.abnormal_count">
                <template #suffix>
                  <span style="font-size: 12px; color: #f56c6c">条</span>
                </template>
              </el-statistic>
            </el-col>
          </el-row>
        </el-card>

        <!-- 导入历史 -->
        <el-card class="history-card" style="margin-top: 20px">
          <template #header>
            <span>导入历史</span>
          </template>
          
          <el-table :data="importHistory" size="small" max-height="300">
            <el-table-column prop="import_time" label="导入时间" width="150">
              <template #default="{ row }">
                {{ formatDateTime(row.import_time) }}
              </template>
            </el-table-column>
            <el-table-column prop="month" label="考勤月份" width="100" />
            <el-table-column prop="total_count" label="记录数" width="70" align="center" />
            <el-table-column prop="success_count" label="成功" width="60" align="center">
              <template #default="{ row }">
                <span style="color: #67c23a">{{ row.success_count }}</span>
              </template>
            </el-table-column>
            <el-table-column prop="operator" label="操作人" width="80" />
          </el-table>
        </el-card>

        <!-- 快速操作 -->
        <el-card class="quick-actions-card" style="margin-top: 20px">
          <template #header>
            <span>快速操作</span>
          </template>
          
          <el-space direction="vertical" fill style="width: 100%">
            <el-button style="width: 100%" @click="handleCalculateMonth">
              <el-icon><Calendar /></el-icon> 重新计算本月考勤
            </el-button>
            <el-button style="width: 100%" @click="handleExportReport">
              <el-icon><Download /></el-icon> 导出考勤报表
            </el-button>
            <el-button style="width: 100%" @click="$router.push('/oa/attendance')">
              <el-icon><List /></el-icon> 查看考勤记录
            </el-button>
          </el-space>
        </el-card>
      </el-col>
    </el-row>

    <!-- 导入结果对话框 -->
    <el-dialog v-model="showResult" title="导入结果" width="500px">
      <el-result
        :icon="importResult.success ? 'success' : 'warning'"
        :title="importResult.success ? '导入成功' : '导入完成（部分失败）'"
      >
        <template #sub-title>
          <div class="result-details">
            <p>总记录数: <strong>{{ importResult.total }}</strong></p>
            <p>成功导入: <strong style="color: #67c23a">{{ importResult.success_count }}</strong></p>
            <p>跳过记录: <strong style="color: #e6a23c">{{ importResult.skip_count }}</strong></p>
            <p>失败记录: <strong style="color: #f56c6c">{{ importResult.error_count }}</strong></p>
          </div>
        </template>
        <template #extra>
          <el-button type="primary" @click="showResult = false">确定</el-button>
        </template>
      </el-result>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Upload, UploadFilled, View, Check, Download, Calendar, List } from '@element-plus/icons-vue'
import request from '@/utils/request'
import * as XLSX from 'xlsx'

// 数据
const uploadRef = ref(null)
const fileList = ref([])
const previewing = ref(false)
const importing = ref(false)
const previewData = ref([])
const showResult = ref(false)

const importForm = reactive({
  month: new Date().toISOString().slice(0, 7), // 默认当月
  source: 'WECHAT_WORK',
  overwrite: false
})

const importResult = reactive({
  success: true,
  total: 0,
  success_count: 0,
  skip_count: 0,
  error_count: 0
})

const monthStats = ref({
  work_days: 22,
  imported_count: 0,
  abnormal_count: 0
})

const importHistory = ref([])

// 计算预览统计
const previewStats = computed(() => {
  const stats = { valid: 0, skip: 0, error: 0 }
  previewData.value.forEach(row => {
    if (row.import_status === 'valid') stats.valid++
    else if (row.import_status === 'skip') stats.skip++
    else stats.error++
  })
  return stats
})

// 方法
const handleFileChange = (file) => {
  fileList.value = [file]
  previewData.value = [] // 清空预览
}

const handleExceed = () => {
  ElMessage.warning('只能上传一个文件，请先删除已选文件')
}

const handlePreview = async () => {
  if (!fileList.value.length) {
    ElMessage.warning('请先选择文件')
    return
  }

  previewing.value = true
  try {
    const file = fileList.value[0].raw || fileList.value[0]
    const data = await readExcelFile(file)
    
    if (!data || !data.length) {
      ElMessage.warning('文件中没有找到有效数据')
      return
    }

    // 解析数据
    previewData.value = parseAttendanceData(data)
    ElMessage.success(`成功解析 ${previewData.value.length} 条记录`)
    
  } catch (error) {
    console.error('预览失败:', error)
    ElMessage.error('文件解析失败，请检查文件格式')
  } finally {
    previewing.value = false
  }
}

const readExcelFile = (file) => {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = (e) => {
      try {
        const workbook = XLSX.read(e.target.result, { type: 'binary' })
        const sheetName = workbook.SheetNames[0]
        const worksheet = workbook.Sheets[sheetName]
        const data = XLSX.utils.sheet_to_json(worksheet, { header: 1 })
        resolve(data)
      } catch (error) {
        reject(error)
      }
    }
    reader.onerror = reject
    reader.readAsBinaryString(file)
  })
}

const parseAttendanceData = (rawData) => {
  // 找到表头行
  let headerIndex = 0
  for (let i = 0; i < Math.min(10, rawData.length); i++) {
    const row = rawData[i]
    if (row && (row.includes('姓名') || row.includes('员工') || row.includes('日期'))) {
      headerIndex = i
      break
    }
  }

  const headers = rawData[headerIndex] || []
  const result = []

  // 列映射（适配企业微信导出格式）
  const colMap = {
    name: headers.findIndex(h => h && (h.includes('姓名') || h.includes('员工姓名') || h === '成员')),
    id: headers.findIndex(h => h && (h.includes('工号') || h.includes('员工编号') || h.includes('账号'))),
    date: headers.findIndex(h => h && (h.includes('日期') || h.includes('打卡日期'))),
    checkIn: headers.findIndex(h => h && (h.includes('上班') || h.includes('签到') || h.includes('最早'))),
    checkOut: headers.findIndex(h => h && (h.includes('下班') || h.includes('签退') || h.includes('最晚'))),
    workHours: headers.findIndex(h => h && (h.includes('工时') || h.includes('时长'))),
    status: headers.findIndex(h => h && (h.includes('状态') || h.includes('结果') || h.includes('异常'))),
    remark: headers.findIndex(h => h && (h.includes('备注') || h.includes('说明')))
  }

  // 解析数据行
  for (let i = headerIndex + 1; i < rawData.length; i++) {
    const row = rawData[i]
    if (!row || !row.length) continue

    const name = colMap.name >= 0 ? row[colMap.name] : ''
    const date = colMap.date >= 0 ? row[colMap.date] : ''
    
    if (!name || !date) continue

    // 解析日期
    let parsedDate = ''
    if (typeof date === 'number') {
      // Excel日期序列号
      const excelDate = new Date((date - 25569) * 86400 * 1000)
      parsedDate = excelDate.toISOString().slice(0, 10)
    } else if (typeof date === 'string') {
      // 尝试解析字符串日期
      const dateStr = date.replace(/[年月]/g, '-').replace(/日/g, '')
      parsedDate = dateStr.includes('-') ? dateStr : date
    }

    // 解析时间
    const parseTime = (val) => {
      if (!val) return ''
      if (typeof val === 'number') {
        // Excel时间小数
        const totalMinutes = Math.round(val * 24 * 60)
        const hours = Math.floor(totalMinutes / 60)
        const minutes = totalMinutes % 60
        return `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}`
      }
      return String(val).trim()
    }

    const checkIn = parseTime(colMap.checkIn >= 0 ? row[colMap.checkIn] : '')
    const checkOut = parseTime(colMap.checkOut >= 0 ? row[colMap.checkOut] : '')
    
    // 计算工时
    let workHours = colMap.workHours >= 0 ? row[colMap.workHours] : ''
    if (!workHours && checkIn && checkOut) {
      const [inH, inM] = checkIn.split(':').map(Number)
      const [outH, outM] = checkOut.split(':').map(Number)
      if (!isNaN(inH) && !isNaN(outH)) {
        const hours = (outH * 60 + outM - inH * 60 - inM) / 60
        workHours = hours > 0 ? hours.toFixed(1) : ''
      }
    }

    // 判断状态
    let status = colMap.status >= 0 ? row[colMap.status] : ''
    let statusCode = 'NORMAL'
    const statusText = String(status).toLowerCase()
    if (statusText.includes('迟到')) statusCode = 'LATE'
    else if (statusText.includes('早退')) statusCode = 'EARLY'
    else if (statusText.includes('缺卡') || statusText.includes('异常')) statusCode = 'ABNORMAL'
    else if (statusText.includes('休息') || statusText.includes('周末')) statusCode = 'REST'
    else if (statusText.includes('请假')) statusCode = 'LEAVE'
    else if (!checkIn && !checkOut) statusCode = 'ABSENT'

    result.push({
      employee_name: String(name).trim(),
      employee_id: colMap.id >= 0 ? String(row[colMap.id] || '').trim() : '',
      date: parsedDate,
      check_in: checkIn,
      check_out: checkOut,
      work_hours: workHours,
      status: statusCode,
      status_text: getStatusText(statusCode),
      remark: colMap.remark >= 0 ? String(row[colMap.remark] || '') : '',
      import_status: 'valid' // valid, skip, error
    })
  }

  return result
}

const getStatusText = (status) => {
  const texts = {
    'NORMAL': '正常',
    'LATE': '迟到',
    'EARLY': '早退',
    'ABNORMAL': '异常',
    'ABSENT': '缺勤',
    'REST': '休息',
    'LEAVE': '请假'
  }
  return texts[status] || status
}

const getStatusType = (status) => {
  const types = {
    'NORMAL': 'success',
    'LATE': 'warning',
    'EARLY': 'warning',
    'ABNORMAL': 'danger',
    'ABSENT': 'danger',
    'REST': 'info',
    'LEAVE': 'info'
  }
  return types[status] || 'info'
}

const handleImport = async () => {
  if (!previewData.value.length) {
    ElMessage.warning('没有可导入的数据')
    return
  }

  try {
    await ElMessageBox.confirm(
      `确定要导入 ${previewData.value.length} 条考勤记录吗？`,
      '确认导入',
      { type: 'warning' }
    )
  } catch {
    return
  }

  importing.value = true
  try {
    const res = await request.post('/oa/attendance-records/batch_import/', {
      month: importForm.month,
      source: importForm.source,
      overwrite: importForm.overwrite,
      records: previewData.value.map(r => ({
        employee_name: r.employee_name,
        employee_id: r.employee_id,
        date: r.date,
        check_in_time: r.check_in,
        check_out_time: r.check_out,
        work_hours: r.work_hours,
        status: r.status,
        remarks: r.remark
      }))
    })

    importResult.success = res.error_count === 0
    importResult.total = res.total || previewData.value.length
    importResult.success_count = res.success_count || 0
    importResult.skip_count = res.skip_count || 0
    importResult.error_count = res.error_count || 0
    
    showResult.value = true
    
    // 刷新统计和历史
    loadMonthStats()
    loadImportHistory()
    
    // 清空预览
    if (importResult.success) {
      previewData.value = []
      fileList.value = []
    }

  } catch (error) {
    console.error('导入失败:', error)
    ElMessage.error(error.response?.data?.detail || '导入失败')
  } finally {
    importing.value = false
  }
}

const handleDownloadTemplate = () => {
  // 创建模板数据
  const templateData = [
    ['考勤数据导入模板'],
    [''],
    ['姓名', '工号', '日期', '签到时间', '签退时间', '工时', '状态', '备注'],
    ['张三', 'EMP001', '2026-01-01', '08:55', '18:05', '9.2', '正常', ''],
    ['李四', 'EMP002', '2026-01-01', '09:15', '18:00', '8.8', '迟到', '迟到15分钟'],
    ['王五', 'EMP003', '2026-01-01', '', '', '', '请假', '年假']
  ]

  const ws = XLSX.utils.aoa_to_sheet(templateData)
  const wb = XLSX.utils.book_new()
  XLSX.utils.book_append_sheet(wb, ws, '考勤模板')
  XLSX.writeFile(wb, '考勤数据导入模板.xlsx')
}

const handleCalculateMonth = async () => {
  try {
    await ElMessageBox.confirm('将根据已导入的打卡记录重新计算本月考勤统计，是否继续？', '确认', { type: 'warning' })
    
    const res = await request.post('/oa/attendance-records/recalculate_month/', {
      month: importForm.month
    })
    
    ElMessage.success(res.message || '计算完成')
    loadMonthStats()
    
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('计算失败')
    }
  }
}

const handleExportReport = async () => {
  try {
    const res = await request.get('/oa/attendance-records/export_report/', {
      params: { month: importForm.month },
      responseType: 'blob'
    })
    
    // 下载文件
    const url = window.URL.createObjectURL(new Blob([res]))
    const link = document.createElement('a')
    link.href = url
    link.setAttribute('download', `考勤报表_${importForm.month}.xlsx`)
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    
  } catch (error) {
    ElMessage.error('导出失败')
  }
}

const loadMonthStats = async () => {
  try {
    const res = await request.get('/oa/attendance-records/month_stats/', {
      params: { month: importForm.month }
    })
    monthStats.value = res || monthStats.value
  } catch (error) {
    console.error('加载统计失败:', error)
  }
}

const loadImportHistory = async () => {
  try {
    const res = await request.get('/oa/attendance-records/import_history/')
    importHistory.value = res.results || res || []
  } catch (error) {
    console.error('加载历史失败:', error)
  }
}

const formatDateTime = (dateStr) => {
  if (!dateStr) return ''
  const date = new Date(dateStr)
  return date.toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  })
}

// 初始化
onMounted(() => {
  loadMonthStats()
  loadImportHistory()
})
</script>

<style scoped>
.attendance-import-page {
  padding: 20px;
}

.page-header {
  display: flex;
  align-items: center;
  gap: 10px;
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

.import-card {
  margin-bottom: 20px;
}

.guide-alert {
  margin-bottom: 20px;
}

.guide-steps {
  margin: 10px 0 0 20px;
  padding: 0;
  line-height: 1.8;
}

.guide-steps a {
  color: #409eff;
  text-decoration: none;
}

.guide-steps a:hover {
  text-decoration: underline;
}

.upload-section {
  margin-bottom: 20px;
}

.upload-area {
  width: 100%;
}

.upload-area :deep(.el-upload-dragger) {
  width: 100%;
}

.import-form {
  margin-bottom: 20px;
}

.action-buttons {
  display: flex;
  gap: 10px;
}

.preview-card {
  margin-top: 20px;
}

.card-header {
  display: flex;
  align-items: center;
  gap: 10px;
}

.stats-card .stats-row {
  text-align: center;
}

.stats-card :deep(.el-statistic__head) {
  font-size: 13px;
  color: #909399;
}

.stats-card :deep(.el-statistic__content) {
  font-size: 24px;
  font-weight: bold;
  color: #409eff;
}

.result-details {
  text-align: left;
  padding: 10px 20px;
}

.result-details p {
  margin: 8px 0;
}
</style>
