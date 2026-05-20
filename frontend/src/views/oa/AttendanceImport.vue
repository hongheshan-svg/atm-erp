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
            <el-table-column prop="employee_name" label="姓名" width="80" />
            <el-table-column prop="employee_id" label="账号" width="100" show-overflow-tooltip />
            <el-table-column prop="date" label="日期" width="100" />
            <el-table-column prop="status" label="状态" width="80">
              <template #default="{ row }">
                <el-tag :type="getStatusType(row.status)" size="small">
                  {{ row.status_text }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="加班" width="60" align="center">
              <template #default="{ row }">
                <span v-if="row.overtime_hours > 0" style="color: #409eff; font-weight: 500">
                  {{ row.overtime_hours }}h
                </span>
                <span v-else style="color: #c0c4cc">-</span>
              </template>
            </el-table-column>
            <el-table-column label="迟到" width="60" align="center">
              <template #default="{ row }">
                <span v-if="row.late_minutes > 0" style="color: #e6a23c">
                  {{ row.late_minutes }}′
                </span>
                <span v-else style="color: #c0c4cc">-</span>
              </template>
            </el-table-column>
            <el-table-column label="请假" width="80" align="center">
              <template #default="{ row }">
                <span v-if="row.leave_hours > 0" style="color: #909399">
                  {{ getLeaveTypeName(row.leave_type) }}{{ row.leave_hours }}h
                </span>
                <span v-else style="color: #c0c4cc">-</span>
              </template>
            </el-table-column>
            <el-table-column prop="remark" label="备注" min-width="150" show-overflow-tooltip />
            <el-table-column label="导入" width="80" fixed="right">
              <template #default="{ row }">
                <el-tag :type="row.import_status === 'valid' ? 'success' : row.import_status === 'skip' ? 'warning' : 'danger'" size="small">
                  {{ row.import_status === 'valid' ? '待导入' : row.import_status === 'skip' ? '跳过' : '错误' }}
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
import { batchImportAttendance, recalculateMonthAttendance, exportAttendanceReport, getAttendanceMonthStats, getAttendanceImportHistory } from '@/api/oa'
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
  // 检测是企业微信月报格式还是每日明细格式
  const firstRow = rawData[0] || []
  const isMonthlyReport = firstRow[0] && String(firstRow[0]).includes('月报')
  
  if (isMonthlyReport) {
    return parseWechatMonthlyReport(rawData)
  } else {
    return parseDailyDetailReport(rawData)
  }
}

// 解析企业微信月报格式
const parseWechatMonthlyReport = (rawData) => {
  const result = []
  
  // 从第2行获取日期范围 "统计时间:01-01 ～ 01-20"
  const dateRangeRow = rawData[1] || []
  const dateRangeStr = String(dateRangeRow[0] || '')
  let year = new Date().getFullYear()
  let startDay = 1, endDay = 31
  
  // 解析日期范围
  const rangeMatch = dateRangeStr.match(/(\d{2})-(\d{2})\s*[～~]\s*(\d{2})-(\d{2})/)
  if (rangeMatch) {
    startDay = parseInt(rangeMatch[2])
    endDay = parseInt(rangeMatch[4])
  }
  
  // 从制表时间获取年份
  const yearMatch = dateRangeStr.match(/(\d{4})-\d{2}-\d{2}/)
  if (yearMatch) {
    year = parseInt(yearMatch[1])
  }
  
  // 找到表头行（包含"姓名"的行）
  let headerRowIndex = 2
  let subHeaderRowIndex = 3
  for (let i = 0; i < Math.min(10, rawData.length); i++) {
    const row = rawData[i]
    if (row && row[0] === '姓名') {
      headerRowIndex = i
      subHeaderRowIndex = i + 1
      break
    }
  }
  
  // 获取子表头（包含日期列和列名映射）
  const subHeaders = rawData[subHeaderRowIndex] || []
  
  // 构建列索引映射（基于第4行的子表头）
  const colMap = {
    department: 3,        // 部门
    position: 4,          // 职务
    employeeId: 5,        // 工号
    expectedDays: 6,      // 应出勤天数
    actualDays: 7,        // 实际出勤天数
    restDays: 8,          // 休息天数
    normalDays: 9,        // 正常天数
    abnormalDays: 10,     // 异常天数
    expectedHours: 11,    // 标准工作时长
    actualHours: 12,      // 实际工作时长
    abnormalCount: 13,    // 异常合计
    lateCount: 14,        // 迟到次数
    lateMinutes: 15,      // 迟到时长(分钟)
    earlyCount: 16,       // 早退次数
    earlyMinutes: 17,     // 早退时长(分钟)
    absentCount: 18,      // 旷工次数
    absentMinutes: 19,    // 旷工时长(分钟)
    missCount: 20,        // 缺卡次数
    locationError: 21,    // 地点异常
    deviceError: 22,      // 设备异常
    makeupCount: 23,      // 补卡次数
    approveCount: 24,     // 审批打卡次数
    fieldCount: 25,       // 外勤次数
    outHours: 26,         // 外出(小时)
    travelDays: 27,       // 出差(天)
    annualHours: 28,      // 年假(小时)
    personalHours: 29,    // 事假(小时)
    sickHours: 30,        // 病假(小时)
    compHours: 31,        // 调休假(小时)
    marriageDay: 32,      // 婚假(天)
    maternityDay: 33,     // 产假(天)
    paternityDay: 34,     // 陪产假(天)
    bereavementDay: 35,   // 丧假(天)
    overtimeTotal: 36,    // 加班时长合计(小时)
    overtimeWeekday: 37,  // 工作日加班时长
    overtimeWeekdayComp: 38,  // 工作日加班计为调休
    overtimeWeekdayPay: 39,   // 工作日加班计为加班费
    overtimeWeekend: 40,      // 休息日加班时长
    overtimeWeekendComp: 41,  // 休息日加班计为调休
    overtimeWeekendPay: 42,   // 休息日加班计为加班费
    overtimeHoliday: 43,      // 节假日加班时长
    overtimeHolidayComp: 44,  // 节假日加班计为调休
    overtimeHolidayPay: 45,   // 节假日加班计为加班费
  }
  
  // 找到每日状态的起始列（格式如 "1\n星期四"）
  let dailyStartCol = -1
  const dailyCols = []
  for (let col = 0; col < subHeaders.length; col++) {
    const header = String(subHeaders[col] || '')
    const dayMatch = header.match(/^(\d{1,2})\n/)
    if (dayMatch) {
      if (dailyStartCol < 0) dailyStartCol = col
      dailyCols.push({
        col: col,
        day: parseInt(dayMatch[1])
      })
    }
  }
  
  // 解析选择的月份
  const selectedMonth = importForm.month // 格式: "2026-01"
  const [selectedYear, selectedMonthNum] = selectedMonth.split('-').map(Number)
  
  // 辅助函数：解析数值
  const parseNum = (val) => {
    if (val === '--' || val === '' || val === null || val === undefined) return 0
    const num = parseFloat(val)
    return isNaN(num) ? 0 : num
  }
  
  // 辅助函数：从每日状态中提取详细信息
  const parseDayDetails = (dayStatus) => {
    const details = {
      overtime: 0,        // 加班小时数
      outHours: 0,        // 外出小时数
      travelHours: 0,     // 出差小时数
      leaveType: '',      // 请假类型
      leaveHours: 0,      // 请假小时数
      lateMinutes: 0,     // 迟到分钟
      earlyMinutes: 0,    // 早退分钟
      absentMinutes: 0,   // 旷工分钟
      missCount: 0,       // 缺卡次数
    }
    
    // 提取加班时长 "加班9.5小时"
    const otMatch = dayStatus.match(/加班([\d.]+)小时/)
    if (otMatch) details.overtime = parseFloat(otMatch[1])
    
    // 提取外出时长 "外出1.5小时" 或 "外出9.0小时"
    const outMatch = dayStatus.match(/外出([\d.]+)小时/)
    if (outMatch) details.outHours = parseFloat(outMatch[1])
    
    // 提取出差时长 "出差1天9.5小时" 或 "出差12.9小时"
    const travelMatch = dayStatus.match(/出差(?:(\d+)天)?([\d.]+)小时/)
    if (travelMatch) {
      const days = travelMatch[1] ? parseFloat(travelMatch[1]) : 0
      const hours = parseFloat(travelMatch[2])
      details.travelHours = days * 8 + hours // 假设1天=8小时
    }
    
    // 提取请假类型和时长
    const leavePatterns = [
      { pattern: /年假([\d.]+)小时/, type: 'ANNUAL' },
      { pattern: /事假([\d.]+)小时/, type: 'PERSONAL' },
      { pattern: /病假([\d.]+)小时/, type: 'SICK' },
      { pattern: /调休假([\d.]+)小时/, type: 'COMP' },
      { pattern: /婚假([\d.]+)(?:天|小时)/, type: 'MARRIAGE' },
      { pattern: /产假([\d.]+)(?:天|小时)/, type: 'MATERNITY' },
      { pattern: /陪产假([\d.]+)(?:天|小时)/, type: 'PATERNITY' },
      { pattern: /丧假([\d.]+)(?:天|小时)/, type: 'BEREAVEMENT' },
    ]
    for (const { pattern, type } of leavePatterns) {
      const match = dayStatus.match(pattern)
      if (match) {
        details.leaveType = type
        details.leaveHours = parseFloat(match[1])
        break
      }
    }
    
    // 提取迟到分钟
    const lateMatch = dayStatus.match(/迟到(\d+)分钟/)
    if (lateMatch) details.lateMinutes = parseInt(lateMatch[1])
    
    // 提取早退分钟
    const earlyMatch = dayStatus.match(/早退(\d+)分钟/)
    if (earlyMatch) details.earlyMinutes = parseInt(earlyMatch[1])
    
    // 提取旷工分钟
    const absentMatch = dayStatus.match(/旷工(\d+)分钟/)
    if (absentMatch) details.absentMinutes = parseInt(absentMatch[1])
    
    // 提取缺卡次数
    const missMatch = dayStatus.match(/缺卡(\d+)次/)
    if (missMatch) details.missCount = parseInt(missMatch[1])
    
    return details
  }
  
  // 解析数据行（从表头后开始）
  for (let i = subHeaderRowIndex + 1; i < rawData.length; i++) {
    const row = rawData[i]
    if (!row || !row.length) continue
    
    const name = String(row[0] || '').trim()
    const account = String(row[1] || '').trim()
    
    if (!name || name === '姓名') continue
    
    // 获取汇总数据
    const summary = {
      department: String(row[colMap.department] || '').trim(),
      position: String(row[colMap.position] || '').trim(),
      employeeId: String(row[colMap.employeeId] || '').trim(),
      expectedDays: parseNum(row[colMap.expectedDays]),
      actualDays: parseNum(row[colMap.actualDays]),
      restDays: parseNum(row[colMap.restDays]),
      actualHours: parseNum(row[colMap.actualHours]),
      lateCount: parseNum(row[colMap.lateCount]),
      lateMinutes: parseNum(row[colMap.lateMinutes]),
      earlyCount: parseNum(row[colMap.earlyCount]),
      earlyMinutes: parseNum(row[colMap.earlyMinutes]),
      absentMinutes: parseNum(row[colMap.absentMinutes]),
      missCount: parseNum(row[colMap.missCount]),
      outHours: parseNum(row[colMap.outHours]),
      travelDays: parseNum(row[colMap.travelDays]),
      overtimeTotal: parseNum(row[colMap.overtimeTotal]),
    }
    
    // 解析每天的状态
    for (const dayCol of dailyCols) {
      const dayStatus = String(row[dayCol.col] || '').trim()
      if (!dayStatus) continue
      
      // 构建日期
      const dateStr = `${selectedYear}-${String(selectedMonthNum).padStart(2, '0')}-${String(dayCol.day).padStart(2, '0')}`
      
      // 解析每日详细信息
      const dayDetails = parseDayDetails(dayStatus)
      
      // 解析状态（改进逻辑：正确处理复合状态）
      let statusCode = 'NORMAL'
      let statusText = '正常'
      const isRest = dayStatus.includes('休息')
      
      if (dayStatus.includes('旷工')) {
        statusCode = 'ABSENT'
        statusText = '旷工'
      } else if (dayStatus.includes('缺卡') && !dayStatus.includes('正常')) {
        statusCode = 'ABNORMAL'
        statusText = '缺卡'
      } else if (dayStatus.includes('迟到') && dayStatus.includes('早退')) {
        statusCode = 'LATE'  // 优先标记迟到
        statusText = '迟到+早退'
      } else if (dayStatus.includes('迟到')) {
        statusCode = 'LATE'
        statusText = '迟到'
      } else if (dayStatus.includes('早退')) {
        statusCode = 'EARLY'
        statusText = '早退'
      } else if (dayStatus.includes('请假') || dayDetails.leaveHours > 0) {
        statusCode = 'LEAVE'
        statusText = dayDetails.leaveType ? getLeaveTypeName(dayDetails.leaveType) : '请假'
      } else if (dayStatus.includes('出差') || dayDetails.travelHours > 0) {
        statusCode = 'TRAVEL'
        statusText = '出差'
      } else if (isRest && dayDetails.overtime > 0) {
        // 休息日加班算加班
        statusCode = 'OVERTIME'
        statusText = '休息日加班'
      } else if (isRest) {
        statusCode = 'REST'
        statusText = '休息'
      } else if (dayDetails.overtime > 0) {
        statusCode = 'OVERTIME'
        statusText = '加班'
      } else if (dayStatus.includes('正常')) {
        statusCode = 'NORMAL'
        statusText = '正常'
      }
      
      // 生成详细备注
      const remarkParts = []
      if (dayDetails.lateMinutes > 0) remarkParts.push(`迟到${dayDetails.lateMinutes}分钟`)
      if (dayDetails.earlyMinutes > 0) remarkParts.push(`早退${dayDetails.earlyMinutes}分钟`)
      if (dayDetails.absentMinutes > 0) remarkParts.push(`旷工${dayDetails.absentMinutes}分钟`)
      if (dayDetails.missCount > 0) remarkParts.push(`缺卡${dayDetails.missCount}次`)
      if (dayDetails.overtime > 0) remarkParts.push(`加班${dayDetails.overtime}小时`)
      if (dayDetails.outHours > 0) remarkParts.push(`外出${dayDetails.outHours}小时`)
      if (dayDetails.travelHours > 0) remarkParts.push(`出差${dayDetails.travelHours}小时`)
      if (dayDetails.leaveHours > 0) {
        const leaveTypeName = getLeaveTypeName(dayDetails.leaveType)
        remarkParts.push(`${leaveTypeName}${dayDetails.leaveHours}小时`)
      }
      
      // 决定是否导入（纯休息日且无加班跳过）
      const shouldImport = !(statusCode === 'REST' && dayDetails.overtime === 0)
      
      result.push({
        employee_name: name,
        employee_id: account || summary.employeeId,
        date: dateStr,
        check_in: '',  // 月报没有具体打卡时间
        check_out: '',
        work_hours: dayDetails.overtime > 0 ? dayDetails.overtime : '',
        overtime_hours: dayDetails.overtime,
        out_hours: dayDetails.outHours,
        travel_hours: dayDetails.travelHours,
        leave_type: dayDetails.leaveType,
        leave_hours: dayDetails.leaveHours,
        late_minutes: dayDetails.lateMinutes,
        early_minutes: dayDetails.earlyMinutes,
        absent_minutes: dayDetails.absentMinutes,
        miss_count: dayDetails.missCount,
        status: statusCode,
        status_text: statusText,
        remark: remarkParts.length > 0 ? remarkParts.join('；') : (isRest ? '休息日' : ''),
        department: summary.department,
        import_status: shouldImport ? 'valid' : 'skip'
      })
    }
  }
  
  return result
}

// 获取请假类型名称
const getLeaveTypeName = (type) => {
  const names = {
    'ANNUAL': '年假',
    'PERSONAL': '事假',
    'SICK': '病假',
    'COMP': '调休假',
    'MARRIAGE': '婚假',
    'MATERNITY': '产假',
    'PATERNITY': '陪产假',
    'BEREAVEMENT': '丧假',
  }
  return names[type] || '请假'
}

// 解析每日明细格式（原有逻辑）
const parseDailyDetailReport = (rawData) => {
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
    'LEAVE': '请假',
    'OVERTIME': '加班',
    'TRAVEL': '出差',
    'REMOTE': '远程'
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
    'LEAVE': 'info',
    'OVERTIME': 'primary',
    'TRAVEL': '',
    'REMOTE': ''
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
  } catch (error) {
    console.error(error)
    return
  }

  importing.value = true
  try {
    const res = await batchImportAttendance({
      month: importForm.month,
      source: importForm.source,
      overwrite: importForm.overwrite,
      records: previewData.value
        .filter(r => r.import_status !== 'skip')  // 只导入非跳过的记录
        .map(r => ({
          employee_name: r.employee_name,
          employee_id: r.employee_id,
          date: r.date,
          check_in_time: r.check_in,
          check_out_time: r.check_out,
          work_hours: r.work_hours,
          overtime_hours: r.overtime_hours || 0,
          out_hours: r.out_hours || 0,
          travel_hours: r.travel_hours || 0,
          leave_type: r.leave_type || '',
          leave_hours: r.leave_hours || 0,
          late_minutes: r.late_minutes || 0,
          early_minutes: r.early_minutes || 0,
          absent_minutes: r.absent_minutes || 0,
          miss_count: r.miss_count || 0,
          status: r.status,
          remarks: r.remark,
          department: r.department || ''
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
    
    const res = await recalculateMonthAttendance({
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
    const res = await exportAttendanceReport({ month: importForm.month }, { responseType: 'blob' })
    
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
    const res = await getAttendanceMonthStats({
      params: { month: importForm.month }
    })
    monthStats.value = res || monthStats.value
  } catch (error) {
    console.error('加载统计失败:', error)
  }
}

const loadImportHistory = async () => {
  try {
    const res = await getAttendanceImportHistory()
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
