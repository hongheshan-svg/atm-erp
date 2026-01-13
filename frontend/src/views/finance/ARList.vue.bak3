<template>
  <div class="ar-list">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>应收账款管理</span>
        </div>
      </template>

      <el-tabs v-model="activeTab" @tab-change="handleTabChange">
        <!-- 银行流水（收入） -->
        <el-tab-pane label="银行流水" name="bankStatements">
          <div class="tab-header">
            <el-upload
              ref="uploadRef"
              :action="uploadUrl"
              :headers="uploadHeaders"
              :on-success="handleUploadSuccess"
              :on-error="handleUploadError"
              :before-upload="beforeUpload"
              :show-file-list="false"
              accept=".xlsx,.xls"
            >
              <el-button type="primary">
                <el-icon><Upload /></el-icon> 导入银行流水
              </el-button>
            </el-upload>
            <el-button @click="exportBankStatements">
              <el-icon><Download /></el-icon> 导出
            </el-button>
            <el-button @click="autoMatchAll" :loading="autoMatching">
              <el-icon><Connection /></el-icon> 自动匹配
            </el-button>
            <el-button @click="exportAR" type="success">
              <el-icon><Download /></el-icon> 导出应收账款
            </el-button>
          </div>

          <!-- 筛选条件 -->
          <el-form :inline="true" :model="bankSearchForm" class="search-form" style="margin-top: 15px;">
            <el-form-item label="状态">
              <el-select v-model="bankSearchForm.status" placeholder="请选择" clearable style="width: 120px;">
                <el-option label="待匹配" value="PENDING" />
                <el-option label="已匹配" value="MATCHED" />
                <el-option label="已忽略" value="IGNORED" />
              </el-select>
            </el-form-item>
            <el-form-item label="类型">
              <el-select v-model="bankSearchForm.transaction_type" placeholder="请选择" clearable style="width: 100px;">
                <el-option label="收入" value="CREDIT" />
                <el-option label="支出" value="DEBIT" />
              </el-select>
            </el-form-item>
            <el-form-item label="客户">
              <el-select v-model="bankSearchForm.customer" placeholder="请选择" clearable filterable style="width: 180px;">
                <el-option v-for="c in customers" :key="c.id" :label="c.name" :value="c.id" />
              </el-select>
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="loadBankStatements">查询</el-button>
              <el-button @click="resetBankSearch">重置</el-button>
            </el-form-item>
          </el-form>

          <div class="batch-actions" v-if="selectedBankStatements.length > 0" style="margin-bottom: 10px;">
            <el-button type="danger" size="small" @click="handleBatchDeleteBankStatements">
              批量删除 ({{ selectedBankStatements.length }})
            </el-button>
          </div>
          
          <el-table :data="bankStatements" v-loading="bankLoading" border stripe style="width: 100%;" @selection-change="handleBankSelectionChange">
            <el-table-column type="selection" width="45" />
            <el-table-column type="index" label="序号" width="55" align="center" :index="(index) => (bankPagination.page - 1) * bankPagination.pageSize + index + 1" />
            <el-table-column prop="transaction_time" label="交易时间" width="150">
              <template #default="{ row }">
                {{ formatDateTime(row.transaction_time) }}
              </template>
            </el-table-column>
            <el-table-column label="借贷" width="55" align="center">
              <template #default="{ row }">
                <el-tag :type="row.transaction_type === 'DEBIT' ? 'danger' : 'success'" size="small">
                  {{ row.transaction_type === 'DEBIT' ? '借' : '贷' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="counterparty_name" label="对方单位" min-width="150" show-overflow-tooltip />
            <el-table-column label="金额" width="100" align="right">
              <template #default="{ row }">
                <span :class="row.transaction_type === 'DEBIT' ? 'text-danger' : 'text-success'">
                  ¥{{ formatNumber(row.amount) }}
                </span>
              </template>
            </el-table-column>
            <el-table-column prop="purpose" label="用途" width="80" show-overflow-tooltip />
            <el-table-column prop="postscript" label="附言" width="120" show-overflow-tooltip />
            <el-table-column label="匹配客户" width="120" show-overflow-tooltip>
              <template #default="{ row }">
                <span v-if="row.customer_name" class="text-success">{{ row.customer_name }}</span>
                <span v-else class="text-muted">未匹配</span>
              </template>
            </el-table-column>
            <el-table-column label="关联项目" width="120" show-overflow-tooltip>
              <template #default="{ row }">
                <span v-if="row.project_code" class="text-primary">{{ row.project_code }}</span>
                <span v-else class="text-muted">-</span>
              </template>
            </el-table-column>
            <el-table-column label="置信度" width="70" align="center">
              <template #default="{ row }">
                <el-tag v-if="row.match_confidence >= 70" type="success" size="small">{{ row.match_confidence }}%</el-tag>
                <el-tag v-else-if="row.match_confidence > 0" type="warning" size="small">{{ row.match_confidence }}%</el-tag>
                <span v-else>-</span>
              </template>
            </el-table-column>
            <el-table-column label="状态" width="80" align="center">
              <template #default="{ row }">
                <el-tag :type="getBankStatusType(row.status)" size="small">{{ row.status_display || getBankStatusLabel(row.status) }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="180" fixed="right">
              <template #default="{ row }">
                <el-button size="small" link @click="handleMatchBank(row)" v-if="row.status === 'PENDING'">匹配</el-button>
                <el-button size="small" link type="warning" @click="handleIgnoreBank(row)" v-if="row.status === 'PENDING'">忽略</el-button>
                <el-button size="small" link @click="handleViewBank(row)">详情</el-button>
                <el-button size="small" link type="danger" @click="handleDeleteBankStatement(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>

          <el-pagination
            v-model:current-page="bankPagination.page"
            v-model:page-size="bankPagination.pageSize"
            :total="bankPagination.total"
            layout="total, sizes, prev, pager, next"
            @size-change="handleBankSizeChange"
            @current-change="loadBankStatements"
            style="margin-top: 20px; justify-content: flex-end;"
          />
        </el-tab-pane>

        <!-- 应收账款列表 -->
        <el-tab-pane label="应收账款" name="receivables">
          <el-form :inline="true" :model="searchForm" class="search-form">
            <el-form-item label="客户">
              <el-select v-model="searchForm.customer" placeholder="请选择客户" clearable filterable style="width: 200px;">
                <el-option v-for="c in customers" :key="c.id" :label="c.name" :value="c.id" />
              </el-select>
            </el-form-item>
            <el-form-item label="状态">
              <el-select v-model="searchForm.status" placeholder="请选择状态" clearable style="width: 120px;">
                <el-option label="未收款" value="UNPAID" />
                <el-option label="部分收款" value="PARTIAL" />
                <el-option label="已收款" value="PAID" />
                <el-option label="已逾期" value="OVERDUE" />
              </el-select>
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="loadARList">查询</el-button>
              <el-button @click="resetSearch">重置</el-button>
            </el-form-item>
          </el-form>

          <el-table :data="arList" v-loading="loading" border stripe style="width: 100%;">
            <el-table-column prop="ar_no" label="应收单号" width="140" show-overflow-tooltip />
            <el-table-column prop="customer_name" label="客户" min-width="100" show-overflow-tooltip />
            <el-table-column prop="sales_order_no" label="销售订单" width="120" show-overflow-tooltip />
            <el-table-column prop="due_date" label="到期日" width="95" />
            <el-table-column label="应收/已收" width="120" align="right">
              <template #default="{ row }">
                <div>¥{{ formatNumber(row.amount_due) }}</div>
                <div style="color: #67c23a; font-size: 12px;">已收: ¥{{ formatNumber(row.amount_paid) }}</div>
              </template>
            </el-table-column>
            <el-table-column label="收款进度" width="100" align="center">
              <template #default="{ row }">
                <el-progress 
                  :percentage="getPaymentProgress(row)" 
                  :stroke-width="8"
                  :color="getProgressColor(getPaymentProgress(row))"
                  :format="() => getPaymentProgress(row) + '%'"
                />
              </template>
            </el-table-column>
            <el-table-column label="发货状态" width="80" align="center">
              <template #default="{ row }">
                <el-tag :type="getDeliveryStatusType(row.delivery_status)" size="small">
                  {{ getDeliveryStatusLabel(row.delivery_status) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="status" label="状态" width="80">
              <template #default="{ row }">
                <el-tag :type="getARStatusType(row.status)" size="small">{{ getARStatusLabel(row.status) }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="150" fixed="right">
              <template #default="{ row }">
                <el-button size="small" link @click="handleView(row)">查看</el-button>
                <el-button size="small" link type="primary" @click="handlePayment(row)" v-if="row.status !== 'PAID'">收款</el-button>
                <el-button size="small" link type="danger" @click="handleDelete(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>

          <el-pagination
            v-model:current-page="pagination.page"
            v-model:page-size="pagination.pageSize"
            :total="pagination.total"
            layout="total, sizes, prev, pager, next"
            @size-change="loadARList"
            @current-change="loadARList"
            style="margin-top: 20px; justify-content: flex-end;"
          />
        </el-tab-pane>

        <!-- 收款计划 -->
        <el-tab-pane label="收款计划" name="paymentSchedule">
          <!-- 统计卡片 -->
          <el-row :gutter="16" class="summary-cards" style="margin-bottom: 16px;">
            <el-col :span="6">
              <el-card shadow="hover" class="summary-card">
                <div class="summary-content">
                  <div class="summary-label">待收款总额</div>
                  <div class="summary-value text-primary">¥{{ formatNumber(scheduleSummary.total_remaining || 0) }}</div>
                </div>
              </el-card>
            </el-col>
            <el-col :span="6">
              <el-card shadow="hover" class="summary-card">
                <div class="summary-content">
                  <div class="summary-label">收款进度</div>
                  <div class="summary-value">
                    <el-progress 
                      :percentage="scheduleSummary.overall_progress || 0" 
                      :color="getProgressColor(scheduleSummary.overall_progress)"
                      :stroke-width="12"
                    />
                  </div>
                </div>
              </el-card>
            </el-col>
            <el-col :span="6">
              <el-card shadow="hover" class="summary-card">
                <div class="summary-content">
                  <div class="summary-label">待收款笔数</div>
                  <div class="summary-value">{{ (scheduleSummary.pending_count || 0) + (scheduleSummary.partial_count || 0) }} 笔</div>
                </div>
              </el-card>
            </el-col>
            <el-col :span="6">
              <el-card shadow="hover" class="summary-card" style="border-left: 4px solid #f56c6c;">
                <div class="summary-content">
                  <div class="summary-label">已逾期</div>
                  <div class="summary-value text-danger">{{ scheduleSummary.overdue_count || 0 }} 笔</div>
                </div>
              </el-card>
            </el-col>
          </el-row>

          <!-- 筛选条件 -->
          <el-form :inline="true" class="search-form">
            <el-form-item label="状态">
              <el-select v-model="scheduleFilters.status" placeholder="全部状态" clearable @change="loadPaymentSchedules" style="width: 120px;">
                <el-option label="待收款" value="PENDING" />
                <el-option label="部分收款" value="PARTIAL" />
                <el-option label="已收款" value="PAID" />
                <el-option label="已逾期" value="OVERDUE" />
              </el-select>
            </el-form-item>
            <el-form-item label="付款节点">
              <el-select v-model="scheduleFilters.milestone_type" placeholder="全部类型" clearable @change="loadPaymentSchedules" style="width: 120px;">
                <el-option label="预付款" value="PREPAY" />
                <el-option label="发货款" value="ON_DELIVERY" />
                <el-option label="验收款" value="ON_ACCEPTANCE" />
                <el-option label="质保金" value="WARRANTY" />
                <el-option label="尾款" value="FINAL" />
              </el-select>
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="loadPaymentSchedules">查询</el-button>
              <el-button @click="resetScheduleFilters">重置</el-button>
            </el-form-item>
          </el-form>

          <!-- 数据表格 -->
          <el-table :data="paymentSchedules" stripe border v-loading="scheduleLoading">
            <el-table-column type="index" label="序号" width="55" align="center" :index="(idx) => (schedulePagination.page - 1) * schedulePagination.pageSize + idx + 1" />
            <el-table-column prop="sales_order_no" label="销售订单" width="130" />
            <el-table-column prop="customer_name" label="客户" width="150" show-overflow-tooltip />
            <el-table-column prop="project_name" label="项目" width="120" show-overflow-tooltip>
              <template #default="{ row }">
                <span v-if="row.project_name">{{ row.project_name }}</span>
                <span v-else class="text-muted">-</span>
              </template>
            </el-table-column>
            <el-table-column prop="milestone_name" label="付款节点" width="100" />
            <el-table-column prop="percentage" label="比例" width="70" align="right">
              <template #default="{ row }">{{ row.percentage }}%</template>
            </el-table-column>
            <el-table-column label="应收金额" width="110" align="right">
              <template #default="{ row }">
                <span class="text-primary">¥{{ formatNumber(row.amount_due) }}</span>
              </template>
            </el-table-column>
            <el-table-column label="已收金额" width="110" align="right">
              <template #default="{ row }">
                <span class="text-success">¥{{ formatNumber(row.amount_paid) }}</span>
              </template>
            </el-table-column>
            <el-table-column label="收款进度" width="130">
              <template #default="{ row }">
                <el-progress 
                  :percentage="row.payment_progress || 0" 
                  :color="getProgressColor(row.payment_progress)"
                  :stroke-width="8"
                  :show-text="true"
                />
              </template>
            </el-table-column>
            <el-table-column prop="due_date" label="计划收款日" width="100">
              <template #default="{ row }">
                <span :class="{ 'text-danger': row.is_overdue }">{{ row.due_date }}</span>
              </template>
            </el-table-column>
            <el-table-column label="距离到期" width="90" align="center">
              <template #default="{ row }">
                <el-tag v-if="row.status === 'PAID'" type="success" size="small">已收款</el-tag>
                <el-tag v-else-if="row.is_overdue" type="danger" size="small">逾期{{ Math.abs(row.days_until_due) }}天</el-tag>
                <el-tag v-else-if="row.days_until_due <= 7" type="warning" size="small">{{ row.days_until_due }}天</el-tag>
                <span v-else class="text-muted">{{ row.days_until_due }}天</span>
              </template>
            </el-table-column>
            <el-table-column prop="status" label="状态" width="80" align="center">
              <template #default="{ row }">
                <el-tag :type="getScheduleStatusType(row.status)" size="small">{{ row.status_display || getScheduleStatusLabel(row.status) }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="130" fixed="right">
              <template #default="{ row }">
                <el-button type="primary" link size="small" @click="handleRecordSchedulePayment(row)" v-if="row.status !== 'PAID'">登记收款</el-button>
                <el-button type="info" link size="small" @click="handleViewScheduleDetail(row)">详情</el-button>
              </template>
            </el-table-column>
          </el-table>

          <el-pagination
            v-model:current-page="schedulePagination.page"
            v-model:page-size="schedulePagination.pageSize"
            :total="schedulePagination.total"
            layout="total, sizes, prev, pager, next"
            @size-change="handleScheduleSizeChange"
            @current-change="loadPaymentSchedules"
            style="margin-top: 20px; justify-content: flex-end;"
          />

          <!-- 提醒信息 -->
          <el-row :gutter="16" style="margin-top: 16px;" v-if="scheduleSummary.overdue_payments?.length || scheduleSummary.upcoming_payments?.length">
            <el-col :span="12" v-if="scheduleSummary.overdue_payments?.length">
              <el-card shadow="hover" style="border-top: 3px solid #f56c6c;">
                <template #header><span>⚠️ 已逾期款项</span></template>
                <el-table :data="scheduleSummary.overdue_payments" size="small" stripe>
                  <el-table-column prop="sales_order_no" label="订单" width="120" />
                  <el-table-column prop="customer_name" label="客户" show-overflow-tooltip />
                  <el-table-column prop="milestone_name" label="节点" width="90" />
                  <el-table-column label="待收" width="100" align="right">
                    <template #default="{ row }">¥{{ formatNumber(row.amount_due - row.amount_paid) }}</template>
                  </el-table-column>
                  <el-table-column label="逾期" width="70" align="center">
                    <template #default="{ row }"><span class="text-danger">{{ Math.abs(row.days_until_due) }}天</span></template>
                  </el-table-column>
                </el-table>
              </el-card>
            </el-col>
            <el-col :span="12" v-if="scheduleSummary.upcoming_payments?.length">
              <el-card shadow="hover" style="border-top: 3px solid #e6a23c;">
                <template #header><span>📅 即将到期款项 (7天内)</span></template>
                <el-table :data="scheduleSummary.upcoming_payments" size="small" stripe>
                  <el-table-column prop="sales_order_no" label="订单" width="120" />
                  <el-table-column prop="customer_name" label="客户" show-overflow-tooltip />
                  <el-table-column prop="milestone_name" label="节点" width="90" />
                  <el-table-column label="待收" width="100" align="right">
                    <template #default="{ row }">¥{{ formatNumber(row.amount_due - row.amount_paid) }}</template>
                  </el-table-column>
                  <el-table-column label="到期" width="70" align="center">
                    <template #default="{ row }"><span class="text-warning">{{ row.days_until_due }}天</span></template>
                  </el-table-column>
                </el-table>
              </el-card>
            </el-col>
          </el-row>
        </el-tab-pane>

        <!-- 销售对账 -->
        <el-tab-pane label="销售对账" name="reconciliation">
          <div class="tab-header">
            <el-button type="primary" @click="handleAddReconciliation">
              <el-icon><Plus /></el-icon> 新建对账单
            </el-button>
            <el-button @click="loadCustomerSummary">
              <el-icon><DataAnalysis /></el-icon> 客户汇总
            </el-button>
          </div>
          
          <el-table :data="reconciliationList" v-loading="reconciliationLoading" stripe border style="margin-top: 15px;">
            <el-table-column prop="reconciliation_no" label="对账单号" width="140" />
            <el-table-column prop="customer_name" label="客户" min-width="120" />
            <el-table-column prop="period_start" label="开始" width="100" />
            <el-table-column prop="period_end" label="结束" width="100" />
            <el-table-column prop="total_order_amount" label="订单金额" width="110" align="right">
              <template #default="{ row }">¥{{ formatNumber(row.total_order_amount) }}</template>
            </el-table-column>
            <el-table-column prop="total_delivered_amount" label="发货金额" width="110" align="right">
              <template #default="{ row }">¥{{ formatNumber(row.total_delivered_amount) }}</template>
            </el-table-column>
            <el-table-column prop="total_invoice_amount" label="发票金额" width="110" align="right">
              <template #default="{ row }">¥{{ formatNumber(row.total_invoice_amount) }}</template>
            </el-table-column>
            <el-table-column prop="total_received_amount" label="已收款" width="100" align="right">
              <template #default="{ row }">¥{{ formatNumber(row.total_received_amount) }}</template>
            </el-table-column>
            <el-table-column prop="balance_amount" label="应收" width="100" align="right">
              <template #default="{ row }">
                <span :class="row.balance_amount > 0 ? 'text-warning' : ''">¥{{ formatNumber(row.balance_amount) }}</span>
              </template>
            </el-table-column>
            <el-table-column prop="status_display" label="状态" width="100" align="center">
              <template #default="{ row }">
                <el-tag :type="getReconciliationStatusType(row.status)">{{ row.status_display || getReconciliationStatusLabel(row.status) }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="200" fixed="right">
              <template #default="{ row }">
                <el-button size="small" @click="handleViewReconciliation(row)">查看</el-button>
                <el-button size="small" type="primary" @click="handleGenerateReconciliation(row)" v-if="row.status === 'DRAFT'">生成明细</el-button>
                <el-button size="small" type="success" @click="handleConfirmReconciliation(row)" v-if="row.status === 'PENDING'">确认</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>
      </el-tabs>
    </el-card>

    <!-- 应收账款详情对话框 -->
    <el-dialog v-model="viewDialogVisible" title="应收账款详情" width="700px">
      <el-descriptions :column="2" border v-if="currentAR">
        <el-descriptions-item label="应收单号">{{ currentAR.ar_no }}</el-descriptions-item>
        <el-descriptions-item label="状态">
          <el-tag :type="getARStatusType(currentAR.status)">{{ getARStatusLabel(currentAR.status) }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="客户">{{ currentAR.customer_name }}</el-descriptions-item>
        <el-descriptions-item label="销售订单">{{ currentAR.sales_order_no || '-' }}</el-descriptions-item>
        <el-descriptions-item label="发票号">{{ currentAR.invoice_no || '-' }}</el-descriptions-item>
        <el-descriptions-item label="发票日期">{{ currentAR.invoice_date || '-' }}</el-descriptions-item>
        <el-descriptions-item label="到期日期">{{ currentAR.due_date || '-' }}</el-descriptions-item>
        <el-descriptions-item label="关联项目">{{ currentAR.project_name || '-' }}</el-descriptions-item>
        <el-descriptions-item label="应收金额">
          <span class="amount-primary">¥{{ formatNumber(currentAR.amount_due) }}</span>
        </el-descriptions-item>
        <el-descriptions-item label="已收金额">
          <span class="amount-success">¥{{ formatNumber(currentAR.amount_paid) }}</span>
        </el-descriptions-item>
        <el-descriptions-item label="未收金额" :span="2">
          <span class="amount-warning">¥{{ formatNumber((currentAR.amount_due || 0) - (currentAR.amount_paid || 0)) }}</span>
        </el-descriptions-item>
        <el-descriptions-item label="创建时间" :span="2">{{ currentAR.created_at }}</el-descriptions-item>
        <el-descriptions-item label="备注" :span="2">{{ currentAR.notes || '-' }}</el-descriptions-item>
      </el-descriptions>
    </el-dialog>

    <!-- 收款登记对话框 -->
    <el-dialog v-model="paymentVisible" title="登记收款" width="500px">
      <el-form :model="paymentForm" label-width="100px">
        <el-form-item label="应收金额">
          <span class="amount-lg">¥{{ formatNumber(currentAR.amount_due) }}</span>
        </el-form-item>
        <el-form-item label="已收金额">
          <span>¥{{ formatNumber(currentAR.amount_paid) }}</span>
        </el-form-item>
        <el-form-item label="未收金额">
          <span class="text-warning">¥{{ formatNumber((currentAR.amount_due || 0) - (currentAR.amount_paid || 0)) }}</span>
        </el-form-item>
        <el-form-item label="本次收款" required>
          <el-input-number v-model="paymentForm.amount" :min="0" :max="(currentAR.amount_due || 0) - (currentAR.amount_paid || 0)" :precision="2" style="width: 100%" />
        </el-form-item>
        <el-form-item label="收款日期" required>
          <el-date-picker v-model="paymentForm.payment_date" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
        </el-form-item>
        <el-form-item label="收款方式">
          <el-select v-model="paymentForm.payment_method" style="width: 100%">
            <el-option label="现金" value="CASH" />
            <el-option label="银行转账" value="BANK" />
            <el-option label="支票" value="CHECK" />
            <el-option label="其他" value="OTHER" />
          </el-select>
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="paymentForm.notes" type="textarea" :rows="3" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="paymentVisible = false">取消</el-button>
        <el-button type="primary" @click="submitPayment">确定</el-button>
      </template>
    </el-dialog>

    <!-- 新建对账单对话框 -->
    <el-dialog v-model="reconciliationDialogVisible" title="新建销售对账单" width="500px">
      <el-form :model="reconciliationForm" label-width="100px" :rules="reconciliationRules" ref="reconciliationFormRef">
        <el-form-item label="客户" prop="customer">
          <el-select v-model="reconciliationForm.customer" placeholder="选择客户" filterable style="width: 100%;">
            <el-option v-for="c in customers" :key="c.id" :label="c.name" :value="c.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="期间开始" prop="period_start">
          <el-date-picker v-model="reconciliationForm.period_start" type="date" value-format="YYYY-MM-DD" style="width: 100%;" />
        </el-form-item>
        <el-form-item label="期间结束" prop="period_end">
          <el-date-picker v-model="reconciliationForm.period_end" type="date" value-format="YYYY-MM-DD" style="width: 100%;" />
        </el-form-item>
        <el-form-item label="期初余额">
          <el-input-number v-model="reconciliationForm.opening_balance" :precision="2" style="width: 100%;" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="reconciliationForm.notes" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="reconciliationDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="saveReconciliation" :loading="saving">保存</el-button>
      </template>
    </el-dialog>

    <!-- 对账详情对话框 -->
    <el-dialog v-model="detailDialogVisible" :title="detailTitle" width="1000px">
      <el-descriptions :column="4" border v-if="currentReconciliation">
        <el-descriptions-item label="对账单号">{{ currentReconciliation.reconciliation_no }}</el-descriptions-item>
        <el-descriptions-item label="状态">
          <el-tag :type="getReconciliationStatusType(currentReconciliation.status)">{{ currentReconciliation.status_display || getReconciliationStatusLabel(currentReconciliation.status) }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="客户">{{ currentReconciliation.customer_name }}</el-descriptions-item>
        <el-descriptions-item label="期间">{{ currentReconciliation.period_start }} ~ {{ currentReconciliation.period_end }}</el-descriptions-item>
      </el-descriptions>
      
      <el-descriptions :column="5" border v-if="currentReconciliation" style="margin-top: 15px;">
        <el-descriptions-item label="订单金额">
          <span class="text-primary">¥{{ formatNumber(currentReconciliation.total_order_amount) }}</span>
        </el-descriptions-item>
        <el-descriptions-item label="发货金额">
          <span class="text-info">¥{{ formatNumber(currentReconciliation.total_delivered_amount) }}</span>
        </el-descriptions-item>
        <el-descriptions-item label="发票金额">
          <span class="text-warning">¥{{ formatNumber(currentReconciliation.total_invoice_amount) }}</span>
        </el-descriptions-item>
        <el-descriptions-item label="已收款">
          <span class="text-success">¥{{ formatNumber(currentReconciliation.total_received_amount) }}</span>
        </el-descriptions-item>
        <el-descriptions-item label="应收">
          <span :class="currentReconciliation.balance_amount > 0 ? 'text-warning' : 'text-success'">
            ¥{{ formatNumber(currentReconciliation.balance_amount) }}
          </span>
        </el-descriptions-item>
      </el-descriptions>
      
      <el-divider>对账明细</el-divider>
      
      <div v-if="currentReconciliation?.status === 'PENDING'" style="margin-bottom: 10px;">
        <el-button type="primary" size="small" @click="batchConfirmDelivery">批量确认发货</el-button>
      </div>
      
      <el-table :data="currentReconciliation?.lines || []" border size="small" max-height="400"
                @selection-change="handleLineSelectionChange">
        <el-table-column type="selection" width="45" v-if="currentReconciliation?.status === 'PENDING'" />
        <el-table-column prop="reference_date" label="日期" width="90" />
        <el-table-column prop="line_type_display" label="类型" width="80" />
        <el-table-column prop="reference_no" label="单据号" width="130" />
        <el-table-column label="发货进度" width="100" align="center">
          <template #default="{ row }">
            <span v-if="row.line_type === 'ORDER'">{{ row.delivered_qty }}/{{ row.order_qty }}</span>
          </template>
        </el-table-column>
        <el-table-column label="发货状态" width="90" align="center">
          <template #default="{ row }">
            <el-tag v-if="row.line_type === 'ORDER'" :type="getDeliveryStatusType(row.delivery_status)" size="small">
              {{ row.delivery_status_display || getDeliveryStatusText(row.delivery_status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="收款进度" width="140" align="center">
          <template #default="{ row }">
            <div v-if="row.line_type === 'ORDER'" style="display: flex; align-items: center; gap: 5px;">
              <el-progress 
                :percentage="Number(row.collection_progress || 0)" 
                :stroke-width="10"
                :show-text="false"
                :color="getProgressColor(row.collection_progress)"
                style="flex: 1;"
              />
              <span style="font-size: 12px; min-width: 40px;">{{ row.collection_progress || 0 }}%</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="已收/应收" width="120" align="right">
          <template #default="{ row }">
            <span v-if="row.line_type === 'ORDER'" style="font-size: 12px;">
              ¥{{ formatNumber(row.received_amount) }}<br/>
              <span style="color: #909399;">/¥{{ formatNumber(row.receivable_amount) }}</span>
            </span>
          </template>
        </el-table-column>
        <el-table-column label="确认" width="60" align="center">
          <template #default="{ row }">
            <el-icon v-if="row.delivery_confirmed" color="#67c23a"><CircleCheck /></el-icon>
            <el-button v-else-if="row.line_type === 'ORDER' && currentReconciliation?.status === 'PENDING'" 
                       size="small" type="primary" link @click="confirmDeliveryLine(row)">确认</el-button>
          </template>
        </el-table-column>
        <el-table-column prop="notes" label="备注" min-width="100" />
      </el-table>
    </el-dialog>

    <!-- 汇总对话框 -->
    <el-dialog v-model="summaryDialogVisible" title="客户对账汇总" width="800px">
      <el-table :data="summaryData" stripe border>
        <el-table-column prop="name" label="客户名称" />
        <el-table-column prop="code" label="编码" width="120" />
        <el-table-column label="应收金额" width="130" align="right">
          <template #default="{ row }">¥{{ formatNumber(row.total_receivable) }}</template>
        </el-table-column>
        <el-table-column label="已收款" width="130" align="right">
          <template #default="{ row }">¥{{ formatNumber(row.total_received) }}</template>
        </el-table-column>
        <el-table-column label="余额" width="130" align="right">
          <template #default="{ row }">
            <span :class="row.balance > 0 ? 'text-warning' : ''">¥{{ formatNumber(row.balance) }}</span>
          </template>
        </el-table-column>
      </el-table>
    </el-dialog>

    <!-- 银行流水详情对话框 -->
    <el-dialog v-model="bankDetailVisible" title="银行流水详情" width="700px">
      <el-descriptions :column="2" border v-if="currentBankStatement">
        <el-descriptions-item label="交易时间">{{ formatDateTime(currentBankStatement.transaction_time) }}</el-descriptions-item>
        <el-descriptions-item label="借贷标志">
          <el-tag :type="currentBankStatement.transaction_type === 'DEBIT' ? 'danger' : 'success'" size="small">
            {{ currentBankStatement.transaction_type === 'DEBIT' ? '借（支出）' : '贷（收入）' }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="对方单位" :span="2">{{ currentBankStatement.counterparty_name }}</el-descriptions-item>
        <el-descriptions-item label="对方账号">{{ currentBankStatement.counterparty_account }}</el-descriptions-item>
        <el-descriptions-item label="对方行号">{{ currentBankStatement.counterparty_bank || '-' }}</el-descriptions-item>
        <el-descriptions-item label="转入金额">
          <span class="text-success">¥{{ formatNumber(currentBankStatement.credit_amount) }}</span>
        </el-descriptions-item>
        <el-descriptions-item label="转出金额">
          <span class="text-danger">¥{{ formatNumber(currentBankStatement.debit_amount) }}</span>
        </el-descriptions-item>
        <el-descriptions-item label="用途">{{ currentBankStatement.purpose || '-' }}</el-descriptions-item>
        <el-descriptions-item label="摘要">{{ currentBankStatement.summary || '-' }}</el-descriptions-item>
        <el-descriptions-item label="附言" :span="2">{{ currentBankStatement.postscript || '-' }}</el-descriptions-item>
        <el-descriptions-item label="匹配状态">
          <el-tag :type="getBankStatusType(currentBankStatement.status)" size="small">{{ currentBankStatement.status_display || getBankStatusLabel(currentBankStatement.status) }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="匹配客户">
          {{ currentBankStatement.customer_name || '-' }}
        </el-descriptions-item>
        <el-descriptions-item label="置信度">{{ currentBankStatement.match_confidence }}%</el-descriptions-item>
        <el-descriptions-item label="关联应收单">{{ currentBankStatement.related_ar_no || '-' }}</el-descriptions-item>
        <el-descriptions-item label="导入批次" :span="2">{{ currentBankStatement.import_batch }}</el-descriptions-item>
      </el-descriptions>
    </el-dialog>

    <!-- 银行流水匹配对话框 -->
    <el-dialog v-model="bankMatchVisible" title="匹配银行流水" width="600px">
      <el-form :model="bankMatchForm" label-width="100px" v-if="currentBankStatement">
        <el-form-item label="对方单位">
          <span style="font-weight: bold;">{{ currentBankStatement.counterparty_name }}</span>
        </el-form-item>
        <el-form-item label="金额">
          <span :class="currentBankStatement.transaction_type === 'DEBIT' ? 'text-danger' : 'text-success'" style="font-weight: bold; font-size: 16px;">
            ¥{{ formatNumber(currentBankStatement.amount) }}
          </span>
        </el-form-item>
        <el-form-item label="匹配类型">
          <el-radio-group v-model="bankMatchForm.match_type">
            <el-radio label="AR">应收账款（客户收款）</el-radio>
            <el-radio label="OTHER">其他</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="选择客户" v-if="bankMatchForm.match_type === 'AR'">
          <el-select v-model="bankMatchForm.customer_id" placeholder="请选择客户" filterable style="width: 100%;">
            <el-option v-for="c in customers" :key="c.id" :label="c.name" :value="c.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="关联应收单" v-if="bankMatchForm.match_type === 'AR' && bankMatchForm.customer_id">
          <el-select v-model="bankMatchForm.ar_id" placeholder="请选择应收单（可选）" filterable clearable style="width: 100%;">
            <el-option v-for="ar in customerARList" :key="ar.id" :label="`${ar.ar_no} - ¥${formatNumber(ar.amount_remaining)}`" :value="ar.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="bankMatchForm.notes" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="bankMatchVisible = false">取消</el-button>
        <el-button type="primary" @click="submitBankMatch" :loading="matching">确定匹配</el-button>
      </template>
    </el-dialog>

    <!-- 登记收款计划收款对话框 -->
    <el-dialog v-model="schedulePaymentVisible" title="登记收款" width="450px">
      <el-form :model="schedulePaymentForm" label-width="100px">
        <el-form-item label="销售订单">
          <el-input :value="currentSchedule?.sales_order_no" disabled />
        </el-form-item>
        <el-form-item label="客户">
          <el-input :value="currentSchedule?.customer_name" disabled />
        </el-form-item>
        <el-form-item label="付款节点">
          <el-input :value="currentSchedule?.milestone_name" disabled />
        </el-form-item>
        <el-form-item label="应收金额">
          <el-input :value="'¥' + formatNumber(currentSchedule?.amount_due)" disabled />
        </el-form-item>
        <el-form-item label="已收金额">
          <el-input :value="'¥' + formatNumber(currentSchedule?.amount_paid)" disabled />
        </el-form-item>
        <el-form-item label="本次收款" required>
          <el-input-number v-model="schedulePaymentForm.amount" :min="0" :precision="2" style="width: 100%" />
        </el-form-item>
        <el-form-item label="收款日期">
          <el-date-picker v-model="schedulePaymentForm.payment_date" type="date" value-format="YYYY-MM-DD" placeholder="选择日期" style="width: 100%" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="schedulePaymentVisible = false">取消</el-button>
        <el-button type="primary" @click="submitSchedulePayment" :loading="scheduleSubmitting">确认</el-button>
      </template>
    </el-dialog>

    <!-- 导入结果对话框 -->
    <el-dialog v-model="importResultVisible" title="导入结果" width="500px">
      <el-descriptions :column="2" border v-if="importResult">
        <el-descriptions-item label="批次号" :span="2">{{ importResult.batch_no }}</el-descriptions-item>
        <el-descriptions-item label="成功导入">
          <span class="text-success">{{ importResult.success_count }} 条</span>
        </el-descriptions-item>
        <el-descriptions-item label="跳过记录">
          <span class="text-muted">{{ importResult.skipped_count || 0 }} 条</span>
          <el-tooltip content="未匹配客户或非业务流水（工资/税费等）" placement="top">
            <el-icon style="margin-left: 4px; cursor: help;"><QuestionFilled /></el-icon>
          </el-tooltip>
        </el-descriptions-item>
        <el-descriptions-item label="错误数">
          <span :class="importResult.error_count > 0 ? 'text-danger' : ''">{{ importResult.error_count }} 条</span>
        </el-descriptions-item>
        <el-descriptions-item label="自动匹配客户">
          <span class="text-primary">{{ importResult.matched_count }} 条</span>
        </el-descriptions-item>
        <el-descriptions-item label="收入总额" :span="2">
          <span class="text-success" style="font-size: 16px; font-weight: bold;">¥{{ formatNumber(importResult.credit_total) }}</span>
        </el-descriptions-item>
      </el-descriptions>
      <div v-if="importResult?.errors?.length > 0" style="margin-top: 15px;">
        <el-alert title="导入错误详情" type="error" :closable="false">
          <div v-for="(err, idx) in importResult.errors" :key="idx">
            第 {{ err.row }} 行: {{ err.error }}
          </div>
        </el-alert>
      </div>
      <template #footer>
        <el-button type="primary" @click="importResultVisible = false; loadBankStatements()">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, DataAnalysis, CircleCheck, Upload, Download, Connection, QuestionFilled } from '@element-plus/icons-vue'
import request from '@/utils/request'

const loading = ref(false)
const reconciliationLoading = ref(false)
const bankLoading = ref(false)
const scheduleLoading = ref(false)
const saving = ref(false)
const autoMatching = ref(false)
const matching = ref(false)
const scheduleSubmitting = ref(false)
const activeTab = ref('bankStatements')

const arList = ref([])
const reconciliationList = ref([])
const bankStatements = ref([])
const selectedBankStatements = ref([])
const customers = ref([])
const summaryData = ref([])
const selectedLines = ref([])
const customerARList = ref([])

// 收款计划相关
const paymentSchedules = ref([])
const scheduleSummary = ref({
  total_remaining: 0, overall_progress: 0, pending_count: 0, partial_count: 0, overdue_count: 0,
  overdue_payments: [], upcoming_payments: []
})
const schedulePagination = reactive({ page: 1, pageSize: 20, total: 0 })
const scheduleFilters = reactive({ status: '', milestone_type: '' })
const schedulePaymentVisible = ref(false)
const currentSchedule = ref(null)
const schedulePaymentForm = reactive({ amount: 0, payment_date: new Date().toISOString().split('T')[0] })

const paymentVisible = ref(false)
const viewDialogVisible = ref(false)
const reconciliationDialogVisible = ref(false)
const detailDialogVisible = ref(false)
const summaryDialogVisible = ref(false)
const bankDetailVisible = ref(false)
const bankMatchVisible = ref(false)
const importResultVisible = ref(false)

const currentAR = ref({})
const currentReconciliation = ref(null)
const currentBankStatement = ref(null)
const detailTitle = ref('')
const importResult = ref(null)

const reconciliationFormRef = ref(null)
const uploadRef = ref(null)

// Upload URL and headers for bank statement import
const uploadUrl = computed(() => {
  const baseUrl = import.meta.env.VITE_API_BASE_URL || '/api'
  return `${baseUrl}/finance/bank-statements/import_excel/`
})
const uploadHeaders = computed(() => {
  const token = localStorage.getItem('access_token')
  return token ? { Authorization: `Bearer ${token}` } : {}
})

const searchForm = reactive({ customer: null, status: null })
const pagination = reactive({ page: 1, pageSize: 20, total: 0 })
const bankPagination = reactive({ page: 1, pageSize: 20, total: 0 })
const bankSearchForm = reactive({ status: null, transaction_type: 'CREDIT', customer: null })
const bankMatchForm = reactive({ match_type: 'AR', customer_id: null, ar_id: null, notes: '' })
const paymentForm = reactive({ amount: 0, payment_date: new Date().toISOString().split('T')[0], payment_method: 'BANK', notes: '' })

const reconciliationForm = reactive({
  customer: null,
  period_start: '',
  period_end: '',
  opening_balance: 0,
  notes: ''
})

const reconciliationRules = {
  customer: [{ required: true, message: '请选择客户' }],
  period_start: [{ required: true, message: '请选择开始日期' }],
  period_end: [{ required: true, message: '请选择结束日期' }]
}

const formatNumber = (num) => parseFloat(num || 0).toFixed(2)

const getARStatusType = (s) => ({ 'PENDING': 'warning', 'UNPAID': 'warning', 'PARTIAL': 'primary', 'PAID': 'success', 'OVERDUE': 'danger', 'CANCELLED': 'info' }[s] || 'info')
const getARStatusLabel = (s) => ({ 'PENDING': '待收款', 'UNPAID': '未收款', 'PARTIAL': '部分收款', 'PAID': '已收款', 'OVERDUE': '已逾期', 'CANCELLED': '已取消' }[s] || s)

const getPaymentProgress = (row) => {
  const due = parseFloat(row.amount_due || 0)
  const paid = parseFloat(row.amount_paid || 0)
  if (due <= 0) return 0
  return Math.min(100, Math.round((paid / due) * 100))
}

const getDeliveryStatusType = (status) => {
  const types = { 'NOT_DELIVERED': 'danger', 'PARTIAL': 'warning', 'DELIVERED': 'success', 'SIGNED': 'success' }
  return types[status] || 'info'
}

const getDeliveryStatusLabel = (status) => {
  const labels = { 'NOT_DELIVERED': '未发货', 'PARTIAL': '部分', 'DELIVERED': '已发货', 'SIGNED': '已签收' }
  return labels[status] || status || '未知'
}

const getReconciliationStatusType = (status) => {
  const types = { DRAFT: 'info', PENDING: 'warning', CONFIRMED: 'success', DISPUTED: 'danger', CLOSED: '' }
  return types[status] || 'info'
}

const getReconciliationStatusLabel = (status) => {
  const labels = { DRAFT: '草稿', PENDING: '待确认', CONFIRMED: '已确认', DISPUTED: '有争议', CLOSED: '已关闭' }
  return labels[status] || status
}

const getProgressColor = (progress) => {
  const p = Number(progress || 0)
  if (p >= 100) return '#67c23a'
  if (p >= 50) return '#409eff'
  if (p > 0) return '#e6a23c'
  return '#909399'
}

const handleTabChange = (tab) => {
  if (tab === 'receivables') loadARList()
  else if (tab === 'reconciliation') loadReconciliationList()
  else if (tab === 'bankStatements') loadBankStatements()
  else if (tab === 'paymentSchedule') { loadPaymentSchedules(); loadScheduleSummary() }
}

// Bank statement related functions
const formatDateTime = (dt) => {
  if (!dt) return '-'
  return new Date(dt).toLocaleString('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
}

const getBankStatusType = (status) => {
  const types = { 'PENDING': 'warning', 'MATCHED': 'success', 'IGNORED': 'info', 'ERROR': 'danger' }
  return types[status] || 'info'
}

const getBankStatusLabel = (status) => {
  const labels = { 'PENDING': '待匹配', 'MATCHED': '已匹配', 'IGNORED': '已忽略', 'ERROR': '匹配错误' }
  return labels[status] || status
}

const loadBankStatements = async () => {
  bankLoading.value = true
  try {
    const params = { 
      page: bankPagination.page, 
      page_size: bankPagination.pageSize,
      ...bankSearchForm 
    }
    Object.keys(params).forEach(k => { if (params[k] === null || params[k] === '') delete params[k] })
    const response = await request.get('/finance/bank-statements/', { params })
    bankStatements.value = response.results || []
    bankPagination.total = response.count || 0
  } catch (error) {
    ElMessage.error('加载银行流水失败')
  } finally {
    bankLoading.value = false
  }
}

const resetBankSearch = () => {
  bankSearchForm.status = null
  bankSearchForm.transaction_type = 'CREDIT'
  bankSearchForm.customer = null
  bankPagination.page = 1
  loadBankStatements()
}

const handleBankSizeChange = (size) => {
  bankPagination.pageSize = size
  bankPagination.page = 1
  loadBankStatements()
}

const beforeUpload = (file) => {
  const isExcel = file.type === 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' ||
                  file.type === 'application/vnd.ms-excel' ||
                  file.name.endsWith('.xlsx') ||
                  file.name.endsWith('.xls')
  if (!isExcel) {
    ElMessage.error('只支持Excel文件格式(.xlsx, .xls)')
    return false
  }
  return true
}

const handleUploadSuccess = (response) => {
  importResult.value = response
  importResultVisible.value = true
  ElMessage.success(`成功导入 ${response.success_count} 条记录，自动匹配 ${response.matched_count} 条`)
}

const handleUploadError = (error) => {
  console.error('Upload error:', error)
  ElMessage.error('导入失败，请检查文件格式')
}

const handleBankSelectionChange = (selection) => {
  selectedBankStatements.value = selection
}

const handleBatchDeleteBankStatements = async () => {
  if (selectedBankStatements.value.length === 0) {
    ElMessage.warning('请先选择要删除的流水记录')
    return
  }
  
  try {
    await ElMessageBox.confirm(
      `确定要删除选中的 ${selectedBankStatements.value.length} 条银行流水吗？`, 
      '批量删除', 
      { type: 'warning' }
    )
    
    const ids = selectedBankStatements.value.map(item => item.id)
    const response = await request.post('/finance/bank-statements/bulk_delete/', { ids })
    
    ElMessage.success(`成功删除 ${response.deleted_count} 条记录`)
    selectedBankStatements.value = []
    loadBankStatements()
  } catch (error) {
    if (error !== 'cancel') ElMessage.error('批量删除失败')
  }
}

const handleDeleteBankStatement = async (row) => {
  try {
    await ElMessageBox.confirm(
      `确定要删除这条银行流水吗？\n对方单位: ${row.counterparty_name}\n金额: ¥${formatNumber(row.amount)}`, 
      '删除银行流水', 
      { type: 'warning' }
    )
    
    await request.delete(`/finance/bank-statements/${row.id}/`)
    ElMessage.success('删除成功')
    loadBankStatements()
  } catch (error) {
    if (error !== 'cancel') ElMessage.error('删除失败')
  }
}

const exportBankStatements = async () => {
  try {
    const params = { ...bankSearchForm }
    Object.keys(params).forEach(k => { if (params[k] === null || params[k] === '') delete params[k] })
    
    const response = await request.get('/finance/bank-statements/export_excel/', {
      params,
      responseType: 'blob'
    })
    
    const filename = `银行流水_${new Date().toISOString().split('T')[0]}.xlsx`
    const blob = response.data
    
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.style.display = 'none'
    link.href = url
    link.download = filename
    document.body.appendChild(link)
    link.click()
    
    setTimeout(() => {
      document.body.removeChild(link)
      window.URL.revokeObjectURL(url)
    }, 100)
    
    ElMessage.success('导出成功')
  } catch (error) {
    ElMessage.error('导出失败')
  }
}

const exportAR = async () => {
  try {
    const params = { ...searchForm }
    Object.keys(params).forEach(k => { if (params[k] === null || params[k] === '') delete params[k] })
    
    const response = await request.get('/core/export/ar/', {
      params,
      responseType: 'blob'
    })
    
    const filename = `应收账款_${new Date().toISOString().split('T')[0]}.xlsx`
    const blob = response.data
    
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.style.display = 'none'
    link.href = url
    link.download = filename
    document.body.appendChild(link)
    link.click()
    
    setTimeout(() => {
      document.body.removeChild(link)
      window.URL.revokeObjectURL(url)
    }, 100)
    
    ElMessage.success('导出成功')
  } catch (error) {
    ElMessage.error('导出失败')
  }
}

const autoMatchAll = async () => {
  autoMatching.value = true
  try {
    const response = await request.post('/finance/bank-statements/auto_match_all/')
    ElMessage.success(`成功自动匹配 ${response.matched_count} 条记录`)
    loadBankStatements()
  } catch (error) {
    ElMessage.error('自动匹配失败')
  } finally {
    autoMatching.value = false
  }
}

const handleViewBank = (row) => {
  currentBankStatement.value = row
  bankDetailVisible.value = true
}

const handleMatchBank = (row) => {
  currentBankStatement.value = row
  bankMatchForm.match_type = 'AR'
  bankMatchForm.customer_id = row.customer || null
  bankMatchForm.ar_id = null
  bankMatchForm.notes = ''
  bankMatchVisible.value = true
}

const handleIgnoreBank = async (row) => {
  try {
    await ElMessageBox.confirm('确定要忽略此银行流水记录吗？', '确认忽略', { type: 'warning' })
    await request.post(`/finance/bank-statements/${row.id}/ignore/`, { notes: '手动忽略' })
    ElMessage.success('已忽略')
    loadBankStatements()
  } catch (error) {
    if (error !== 'cancel') ElMessage.error('操作失败')
  }
}

const loadCustomerARList = async (customerId) => {
  if (!customerId) {
    customerARList.value = []
    return
  }
  try {
    const response = await request.get('/finance/receivables/', {
      params: { customer: customerId, status__in: 'PENDING,PARTIAL', page_size: 100 }
    })
    customerARList.value = response.results || []
  } catch (error) {
    customerARList.value = []
  }
}

// Watch for customer selection change in match form
watch(() => bankMatchForm.customer_id, (newVal) => {
  if (newVal) {
    loadCustomerARList(newVal)
  } else {
    customerARList.value = []
  }
})

const submitBankMatch = async () => {
  if (bankMatchForm.match_type === 'AR' && !bankMatchForm.customer_id) {
    return ElMessage.warning('请选择客户')
  }
  
  matching.value = true
  try {
    await request.post(`/finance/bank-statements/${currentBankStatement.value.id}/match/`, bankMatchForm)
    ElMessage.success('匹配成功')
    bankMatchVisible.value = false
    loadBankStatements()
  } catch (error) {
    ElMessage.error('匹配失败: ' + (error.response?.data?.error || error.message))
  } finally {
    matching.value = false
  }
}

const loadARList = async () => {
  loading.value = true
  try {
    const params = { page: pagination.page, page_size: pagination.pageSize, ...searchForm }
    Object.keys(params).forEach(k => { if (params[k] === null) delete params[k] })
    const response = await request.get('/finance/receivables/', { params })
    arList.value = response.results || []
    pagination.total = response.count || 0
  } catch (error) {
    ElMessage.error('加载应收账款失败')
  } finally {
    loading.value = false
  }
}

const loadCustomers = async () => {
  try {
    const response = await request.get('/masterdata/customers/', { params: { page_size: 100 } })
    customers.value = response.results || response || []
  } catch (error) {
    console.error('加载客户失败:', error)
  }
}

const loadReconciliationList = async () => {
  reconciliationLoading.value = true
  try {
    const res = await request.get('/finance/sales-reconciliations/')
    reconciliationList.value = res.results || res || []
  } catch (error) {
    ElMessage.error('加载销售对账单失败')
  } finally {
    reconciliationLoading.value = false
  }
}

const resetSearch = () => {
  searchForm.customer = null
  searchForm.status = null
  pagination.page = 1
  loadARList()
}

const handleView = (row) => {
  currentAR.value = row
  viewDialogVisible.value = true
}

const handlePayment = (row) => {
  currentAR.value = row
  paymentForm.amount = (row.amount_due || 0) - (row.amount_paid || 0)
  paymentVisible.value = true
}

const submitPayment = async () => {
  if (!paymentForm.amount || paymentForm.amount <= 0) return ElMessage.warning('请输入收款金额')
  try {
    await request.post(`/finance/receivables/${currentAR.value.id}/record_payment/`, paymentForm)
    ElMessage.success('收款登记成功')
    paymentVisible.value = false
    loadARList()
  } catch (error) {
    ElMessage.error('收款登记失败')
  }
}

const handleDelete = async (row) => {
  try {
    await ElMessageBox.confirm('确定要删除此应收账款记录吗？此操作不可恢复！', '删除应收账款', { type: 'warning' })
    await request.delete(`/finance/receivables/${row.id}/`)
    ElMessage.success('应收账款已删除')
    loadARList()
  } catch (error) {
    if (error !== 'cancel') ElMessage.error('删除应收账款失败')
  }
}

// 对账功能
const handleAddReconciliation = () => {
  Object.assign(reconciliationForm, { customer: null, period_start: '', period_end: '', opening_balance: 0, notes: '' })
  reconciliationDialogVisible.value = true
}

const saveReconciliation = async () => {
  try {
    await reconciliationFormRef.value.validate()
    saving.value = true
    await request.post('/finance/sales-reconciliations/', reconciliationForm)
    ElMessage.success('创建成功')
    reconciliationDialogVisible.value = false
    loadReconciliationList()
  } catch (error) {
    if (error !== 'cancel') ElMessage.error('保存失败')
  } finally {
    saving.value = false
  }
}

const handleViewReconciliation = async (row) => {
  try {
    const res = await request.get(`/finance/sales-reconciliations/${row.id}/`)
    currentReconciliation.value = res
    detailTitle.value = `销售对账单 - ${row.reconciliation_no}`
    detailDialogVisible.value = true
  } catch (error) {
    ElMessage.error('加载详情失败')
  }
}

const handleGenerateReconciliation = async (row) => {
  try {
    await ElMessageBox.confirm('确定要生成对账明细吗？', '确认')
    await request.post(`/finance/sales-reconciliations/${row.id}/generate_lines/`)
    ElMessage.success('生成成功')
    loadReconciliationList()
  } catch (error) {
    if (error !== 'cancel') ElMessage.error('生成失败: ' + (error.response?.data?.error || error.message))
  }
}

const handleConfirmReconciliation = async (row) => {
  try {
    await ElMessageBox.confirm('确定要确认该对账单吗？', '确认')
    await request.post(`/finance/sales-reconciliations/${row.id}/confirm/`)
    ElMessage.success('确认成功')
    loadReconciliationList()
  } catch (error) {
    if (error !== 'cancel') ElMessage.error('确认失败')
  }
}

const loadCustomerSummary = async () => {
  try {
    const res = await request.get('/finance/sales-reconciliations/customer_summary/')
    summaryData.value = res
    summaryDialogVisible.value = true
  } catch (error) {
    ElMessage.error('加载汇总失败')
  }
}

const handleLineSelectionChange = (selection) => {
  selectedLines.value = selection
}

const confirmDeliveryLine = async (row) => {
  try {
    await request.post(`/finance/sales-reconciliations/${currentReconciliation.value.id}/confirm_delivery/${row.id}/`, { delivery_status: 'DELIVERED' })
    ElMessage.success('发货确认成功')
    handleViewReconciliation(currentReconciliation.value)
  } catch (error) {
    ElMessage.error('确认失败: ' + (error.response?.data?.error || error.message))
  }
}

const batchConfirmDelivery = async () => {
  if (selectedLines.value.length === 0) return ElMessage.warning('请选择要确认的明细')
  try {
    const lineIds = selectedLines.value.filter(l => l.line_type === 'ORDER').map(l => l.id)
    if (lineIds.length === 0) return ElMessage.warning('请选择订单类型的明细')
    await request.post(`/finance/sales-reconciliations/${currentReconciliation.value.id}/batch_confirm_delivery/`, { line_ids: lineIds })
    ElMessage.success('批量确认成功')
    handleViewReconciliation(currentReconciliation.value)
  } catch (error) {
    ElMessage.error('确认失败: ' + (error.response?.data?.error || error.message))
  }
}

// 收款计划相关函数
const loadPaymentSchedules = async () => {
  scheduleLoading.value = true
  try {
    const params = { page: schedulePagination.page, page_size: schedulePagination.pageSize, ...scheduleFilters }
    Object.keys(params).forEach(k => { if (!params[k]) delete params[k] })
    const response = await request.get('/finance/payment-schedules/', { params })
    paymentSchedules.value = response.results || []
    schedulePagination.total = response.count || 0
  } catch (error) {
    ElMessage.error('加载收款计划失败')
  } finally {
    scheduleLoading.value = false
  }
}

const loadScheduleSummary = async () => {
  try {
    const response = await request.get('/finance/payment-schedules/summary/')
    scheduleSummary.value = response
  } catch (error) {
    console.error('加载统计信息失败:', error)
  }
}

const resetScheduleFilters = () => {
  scheduleFilters.status = ''
  scheduleFilters.milestone_type = ''
  schedulePagination.page = 1
  loadPaymentSchedules()
  loadScheduleSummary()
}

const handleScheduleSizeChange = (size) => {
  schedulePagination.pageSize = size
  schedulePagination.page = 1
  loadPaymentSchedules()
}

const getScheduleStatusType = (status) => {
  const types = { 'PENDING': 'info', 'PARTIAL': 'warning', 'PAID': 'success', 'OVERDUE': 'danger', 'CANCELLED': '' }
  return types[status] || 'info'
}

const getScheduleStatusLabel = (status) => {
  const labels = { 'PENDING': '待收款', 'PARTIAL': '部分收款', 'PAID': '已收款', 'OVERDUE': '已逾期', 'CANCELLED': '已取消' }
  return labels[status] || status
}

const handleRecordSchedulePayment = (row) => {
  currentSchedule.value = row
  schedulePaymentForm.amount = Number(row.amount_due) - Number(row.amount_paid)
  schedulePaymentForm.payment_date = new Date().toISOString().split('T')[0]
  schedulePaymentVisible.value = true
}

const submitSchedulePayment = async () => {
  if (!schedulePaymentForm.amount || schedulePaymentForm.amount <= 0) {
    ElMessage.warning('请输入有效的收款金额')
    return
  }
  scheduleSubmitting.value = true
  try {
    await request.post(`/finance/payment-schedules/${currentSchedule.value.id}/record_payment/`, schedulePaymentForm)
    ElMessage.success('收款登记成功')
    schedulePaymentVisible.value = false
    loadPaymentSchedules()
    loadScheduleSummary()
  } catch (error) {
    ElMessage.error('收款登记失败: ' + (error.response?.data?.error || error.message))
  } finally {
    scheduleSubmitting.value = false
  }
}

const handleViewScheduleDetail = (row) => {
  ElMessage.info(`订单: ${row.sales_order_no}, 节点: ${row.milestone_name}`)
}

onMounted(() => {
  loadBankStatements()
  loadCustomers()
})
</script>

<style scoped>
.ar-list { padding: 20px; }
.card-header { display: flex; justify-content: space-between; align-items: center; }
.search-form { margin-bottom: 20px; }
.tab-header { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.text-danger { color: #f56c6c; font-weight: bold; }
.text-warning { color: #e6a23c; font-weight: bold; }
.text-success { color: #67c23a; font-weight: bold; }
.text-primary { color: #409eff; font-weight: bold; }
.text-info { color: #909399; font-weight: bold; }
.text-muted { color: #909399; }
.amount-primary { font-size: 16px; font-weight: 600; color: #409EFF; }
.amount-success { font-size: 16px; font-weight: 600; color: #67C23A; }
.amount-warning { font-size: 18px; font-weight: 600; color: #E6A23C; }
.amount-lg { font-size: 16px; font-weight: 600; }
.summary-card { text-align: center; }
.summary-content { padding: 8px 0; }
.summary-label { font-size: 14px; color: #606266; margin-bottom: 8px; }
.summary-value { font-size: 24px; font-weight: bold; }
</style>
