<template>
  <div class="ap-list">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>应付账款管理</span>
        </div>
      </template>

      <el-tabs v-model="activeTab" @tab-change="handleTabChange">
        <!-- 银行流水 -->
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
                <el-option label="支出" value="DEBIT" />
                <el-option label="收入" value="CREDIT" />
              </el-select>
            </el-form-item>
            <el-form-item label="供应商">
              <el-select v-model="bankSearchForm.supplier" placeholder="请选择" clearable filterable style="width: 180px;">
                <el-option v-for="s in suppliers" :key="s.id" :label="s.name" :value="s.id" />
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
            <el-table-column prop="summary" label="摘要" width="100" show-overflow-tooltip />
            <el-table-column label="匹配供应商" width="120" show-overflow-tooltip>
              <template #default="{ row }">
                <span v-if="row.supplier_name" class="text-success">{{ row.supplier_name }}</span>
                <span v-else class="text-muted">未匹配</span>
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
                <el-tag :type="getBankStatusType(row.status)" size="small">{{ row.status_display }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="150" fixed="right">
              <template #default="{ row }">
                <el-button size="small" link @click="handleMatchBank(row)" v-if="row.status === 'PENDING'">匹配</el-button>
                <el-button size="small" link type="warning" @click="handleIgnoreBank(row)" v-if="row.status === 'PENDING'">忽略</el-button>
                <el-button size="small" link @click="handleViewBank(row)">详情</el-button>
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

        <!-- 应付账款列表 -->
        <el-tab-pane label="应付账款" name="payables">
          <el-form :inline="true" :model="searchForm" class="search-form">
            <el-form-item label="供应商">
              <el-select v-model="searchForm.supplier" placeholder="请选择供应商" clearable filterable style="width: 200px;">
                <el-option v-for="s in suppliers" :key="s.id" :label="s.name" :value="s.id" />
              </el-select>
            </el-form-item>
            <el-form-item label="状态">
              <el-select v-model="searchForm.status" placeholder="请选择状态" clearable style="width: 120px;">
                <el-option label="未付款" value="UNPAID" />
                <el-option label="部分付款" value="PARTIAL" />
                <el-option label="已付款" value="PAID" />
                <el-option label="已逾期" value="OVERDUE" />
              </el-select>
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="loadAPList">查询</el-button>
              <el-button @click="resetSearch">重置</el-button>
            </el-form-item>
          </el-form>

          <el-table :data="apList" v-loading="loading" border stripe style="width: 100%;">
            <el-table-column prop="ap_no" label="应付单号" width="140" show-overflow-tooltip />
            <el-table-column prop="supplier_name" label="供应商" min-width="100" show-overflow-tooltip />
            <el-table-column prop="purchase_order_no" label="采购订单" width="120" show-overflow-tooltip />
            <el-table-column prop="due_date" label="到期日" width="95" />
            <el-table-column label="应付/已付" width="120" align="right">
              <template #default="{ row }">
                <div>¥{{ formatNumber(row.amount_due) }}</div>
                <div style="color: #67c23a; font-size: 12px;">已付: ¥{{ formatNumber(row.amount_paid) }}</div>
              </template>
            </el-table-column>
            <el-table-column label="付款进度" width="100" align="center">
              <template #default="{ row }">
                <el-progress 
                  :percentage="getPaymentProgress(row)" 
                  :stroke-width="8"
                  :color="getProgressColor(getPaymentProgress(row))"
                  :format="() => getPaymentProgress(row) + '%'"
                />
              </template>
            </el-table-column>
            <el-table-column label="收货状态" width="80" align="center">
              <template #default="{ row }">
                <el-tag :type="getReceiptStatusType(row.receipt_status)" size="small">
                  {{ getReceiptStatusLabel(row.receipt_status) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="status" label="状态" width="80">
              <template #default="{ row }">
                <el-tag :type="getAPStatusType(row.status)" size="small">{{ getAPStatusLabel(row.status) }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="150" fixed="right">
              <template #default="{ row }">
                <el-button size="small" link @click="handleView(row)">查看</el-button>
                <el-button size="small" link type="primary" @click="handlePayment(row)" v-if="row.status !== 'PAID'">付款</el-button>
                <el-button size="small" link type="danger" @click="handleDelete(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>

          <el-pagination
            v-model:current-page="pagination.page"
            v-model:page-size="pagination.pageSize"
            :total="pagination.total"
            layout="total, sizes, prev, pager, next"
            @size-change="loadAPList"
            @current-change="loadAPList"
            style="margin-top: 20px; justify-content: flex-end;"
          />
        </el-tab-pane>

        <!-- 采购对账 -->
        <el-tab-pane label="采购对账" name="reconciliation">
          <div class="tab-header">
            <el-button type="primary" @click="handleAddReconciliation">
              <el-icon><Plus /></el-icon> 新建对账单
            </el-button>
            <el-button @click="loadSupplierSummary">
              <el-icon><DataAnalysis /></el-icon> 供应商汇总
            </el-button>
          </div>
          
          <el-table :data="reconciliationList" v-loading="reconciliationLoading" stripe border style="margin-top: 15px;">
            <el-table-column prop="reconciliation_no" label="对账单号" width="140" />
            <el-table-column prop="supplier_name" label="供应商" min-width="120" />
            <el-table-column prop="period_start" label="开始" width="100" />
            <el-table-column prop="period_end" label="结束" width="100" />
            <el-table-column prop="total_order_amount" label="订单金额" width="110" align="right">
              <template #default="{ row }">¥{{ formatNumber(row.total_order_amount) }}</template>
            </el-table-column>
            <el-table-column prop="total_received_amount" label="收货金额" width="110" align="right">
              <template #default="{ row }">¥{{ formatNumber(row.total_received_amount) }}</template>
            </el-table-column>
            <el-table-column prop="total_invoice_amount" label="发票金额" width="110" align="right">
              <template #default="{ row }">¥{{ formatNumber(row.total_invoice_amount) }}</template>
            </el-table-column>
            <el-table-column prop="total_paid_amount" label="已付款" width="100" align="right">
              <template #default="{ row }">¥{{ formatNumber(row.total_paid_amount) }}</template>
            </el-table-column>
            <el-table-column prop="balance_amount" label="欠款" width="100" align="right">
              <template #default="{ row }">
                <span :class="row.balance_amount > 0 ? 'text-danger' : ''">¥{{ formatNumber(row.balance_amount) }}</span>
              </template>
            </el-table-column>
            <el-table-column prop="status_display" label="状态" width="100" align="center">
              <template #default="{ row }">
                <el-tag :type="getReconciliationStatusType(row.status)">{{ row.status_display }}</el-tag>
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

    <!-- 应付账款详情对话框 -->
    <el-dialog v-model="viewDialogVisible" title="应付账款详情" width="700px">
      <el-descriptions :column="2" border v-if="currentAP">
        <el-descriptions-item label="应付单号">{{ currentAP.ap_no }}</el-descriptions-item>
        <el-descriptions-item label="状态">
          <el-tag :type="getAPStatusType(currentAP.status)">{{ getAPStatusLabel(currentAP.status) }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="供应商">{{ currentAP.supplier_name }}</el-descriptions-item>
        <el-descriptions-item label="采购订单">{{ currentAP.purchase_order_no || '-' }}</el-descriptions-item>
        <el-descriptions-item label="发票号">{{ currentAP.invoice_no || '-' }}</el-descriptions-item>
        <el-descriptions-item label="发票日期">{{ currentAP.invoice_date || '-' }}</el-descriptions-item>
        <el-descriptions-item label="到期日期">{{ currentAP.due_date || '-' }}</el-descriptions-item>
        <el-descriptions-item label="关联项目">{{ currentAP.project_name || '-' }}</el-descriptions-item>
        <el-descriptions-item label="应付金额">
          <span class="amount-primary">¥{{ formatNumber(currentAP.amount_due) }}</span>
        </el-descriptions-item>
        <el-descriptions-item label="已付金额">
          <span class="amount-success">¥{{ formatNumber(currentAP.amount_paid) }}</span>
        </el-descriptions-item>
        <el-descriptions-item label="未付金额" :span="2">
          <span class="amount-danger">¥{{ formatNumber((currentAP.amount_due || 0) - (currentAP.amount_paid || 0)) }}</span>
        </el-descriptions-item>
        <el-descriptions-item label="创建时间" :span="2">{{ currentAP.created_at }}</el-descriptions-item>
        <el-descriptions-item label="备注" :span="2">{{ currentAP.notes || '-' }}</el-descriptions-item>
      </el-descriptions>
    </el-dialog>

    <!-- 付款登记对话框 -->
    <el-dialog v-model="paymentVisible" title="登记付款" width="500px">
      <el-form :model="paymentForm" label-width="100px">
        <el-form-item label="应付金额">
          <span class="amount-lg">¥{{ formatNumber(currentAP.amount_due) }}</span>
        </el-form-item>
        <el-form-item label="已付金额">
          <span>¥{{ formatNumber(currentAP.amount_paid) }}</span>
        </el-form-item>
        <el-form-item label="未付金额">
          <span class="text-danger">¥{{ formatNumber((currentAP.amount_due || 0) - (currentAP.amount_paid || 0)) }}</span>
        </el-form-item>
        <el-form-item label="本次付款" required>
          <el-input-number v-model="paymentForm.amount" :min="0" :max="(currentAP.amount_due || 0) - (currentAP.amount_paid || 0)" :precision="2" style="width: 100%" />
        </el-form-item>
        <el-form-item label="付款日期" required>
          <el-date-picker v-model="paymentForm.payment_date" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
        </el-form-item>
        <el-form-item label="付款方式">
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
    <el-dialog v-model="reconciliationDialogVisible" title="新建采购对账单" width="500px">
      <el-form :model="reconciliationForm" label-width="100px" :rules="reconciliationRules" ref="reconciliationFormRef">
        <el-form-item label="供应商" prop="supplier">
          <el-select v-model="reconciliationForm.supplier" placeholder="选择供应商" filterable style="width: 100%;">
            <el-option v-for="s in suppliers" :key="s.id" :label="s.name" :value="s.id" />
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
          <el-tag :type="getReconciliationStatusType(currentReconciliation.status)">{{ currentReconciliation.status_display }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="供应商">{{ currentReconciliation.supplier_name }}</el-descriptions-item>
        <el-descriptions-item label="期间">{{ currentReconciliation.period_start }} ~ {{ currentReconciliation.period_end }}</el-descriptions-item>
      </el-descriptions>
      
      <el-descriptions :column="5" border v-if="currentReconciliation" style="margin-top: 15px;">
        <el-descriptions-item label="订单金额">
          <span class="text-primary">¥{{ formatNumber(currentReconciliation.total_order_amount) }}</span>
        </el-descriptions-item>
        <el-descriptions-item label="收货金额">
          <span class="text-info">¥{{ formatNumber(currentReconciliation.total_received_amount) }}</span>
        </el-descriptions-item>
        <el-descriptions-item label="发票金额">
          <span class="text-warning">¥{{ formatNumber(currentReconciliation.total_invoice_amount) }}</span>
        </el-descriptions-item>
        <el-descriptions-item label="已付款">
          <span class="text-success">¥{{ formatNumber(currentReconciliation.total_paid_amount) }}</span>
        </el-descriptions-item>
        <el-descriptions-item label="欠款">
          <span :class="currentReconciliation.balance_amount > 0 ? 'text-danger' : 'text-success'">
            ¥{{ formatNumber(currentReconciliation.balance_amount) }}
          </span>
        </el-descriptions-item>
      </el-descriptions>
      
      <el-divider>对账明细</el-divider>
      
      <div v-if="currentReconciliation?.status === 'PENDING'" style="margin-bottom: 10px;">
        <el-button type="primary" size="small" @click="batchConfirmReceipt">批量确认收货</el-button>
      </div>
      
      <el-table :data="currentReconciliation?.lines || []" border size="small" max-height="400"
                @selection-change="handleLineSelectionChange">
        <el-table-column type="selection" width="45" v-if="currentReconciliation?.status === 'PENDING'" />
        <el-table-column prop="reference_date" label="日期" width="90" />
        <el-table-column prop="line_type_display" label="类型" width="80" />
        <el-table-column prop="reference_no" label="单据号" width="130" />
        <el-table-column label="收货进度" width="100" align="center">
          <template #default="{ row }">
            <span v-if="row.line_type === 'ORDER'">{{ row.received_qty }}/{{ row.order_qty }}</span>
          </template>
        </el-table-column>
        <el-table-column label="收货状态" width="90" align="center">
          <template #default="{ row }">
            <el-tag v-if="row.line_type === 'ORDER'" :type="getReceiptStatusType(row.receipt_status)" size="small">
              {{ row.receipt_status_display || getReceiptStatusText(row.receipt_status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="付款进度" width="140" align="center">
          <template #default="{ row }">
            <div v-if="row.line_type === 'ORDER'" style="display: flex; align-items: center; gap: 5px;">
              <el-progress 
                :percentage="Number(row.payment_progress || 0)" 
                :stroke-width="10"
                :show-text="false"
                :color="getProgressColor(row.payment_progress)"
                style="flex: 1;"
              />
              <span style="font-size: 12px; min-width: 40px;">{{ row.payment_progress || 0 }}%</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="已付/应付" width="120" align="right">
          <template #default="{ row }">
            <span v-if="row.line_type === 'ORDER'" style="font-size: 12px;">
              ¥{{ formatNumber(row.paid_amount) }}<br/>
              <span style="color: #909399;">/¥{{ formatNumber(row.payable_amount) }}</span>
            </span>
          </template>
        </el-table-column>
        <el-table-column label="确认" width="60" align="center">
          <template #default="{ row }">
            <el-icon v-if="row.receipt_confirmed" color="#67c23a"><CircleCheck /></el-icon>
            <el-button v-else-if="row.line_type === 'ORDER' && currentReconciliation?.status === 'PENDING'" 
                       size="small" type="primary" link @click="confirmReceiptLine(row)">确认</el-button>
          </template>
        </el-table-column>
        <el-table-column prop="notes" label="备注" min-width="100" />
      </el-table>
    </el-dialog>

    <!-- 汇总对话框 -->
    <el-dialog v-model="summaryDialogVisible" title="供应商对账汇总" width="800px">
      <el-table :data="summaryData" stripe border>
        <el-table-column prop="name" label="供应商名称" />
        <el-table-column prop="code" label="编码" width="120" />
        <el-table-column label="应付金额" width="130" align="right">
          <template #default="{ row }">¥{{ formatNumber(row.total_payable) }}</template>
        </el-table-column>
        <el-table-column label="已付款" width="130" align="right">
          <template #default="{ row }">¥{{ formatNumber(row.total_paid) }}</template>
        </el-table-column>
        <el-table-column label="余额" width="130" align="right">
          <template #default="{ row }">
            <span :class="row.balance > 0 ? 'text-danger' : ''">¥{{ formatNumber(row.balance) }}</span>
          </template>
        </el-table-column>
      </el-table>
    </el-dialog>

    <!-- 银行流水详情对话框 -->
    <el-dialog v-model="bankDetailVisible" title="银行流水详情" width="700px">
      <el-descriptions :column="2" border v-if="currentBankStatement">
        <el-descriptions-item label="交易时间" :span="2">{{ formatDateTime(currentBankStatement.transaction_time) }}</el-descriptions-item>
        <el-descriptions-item label="借贷标志">
          <el-tag :type="currentBankStatement.transaction_type === 'DEBIT' ? 'danger' : 'success'">
            {{ currentBankStatement.transaction_type_display }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="金额">
          <span :class="currentBankStatement.transaction_type === 'DEBIT' ? 'text-danger' : 'text-success'" style="font-size: 18px; font-weight: bold;">
            ¥{{ formatNumber(currentBankStatement.amount) }}
          </span>
        </el-descriptions-item>
        <el-descriptions-item label="对方单位" :span="2">{{ currentBankStatement.counterparty_name }}</el-descriptions-item>
        <el-descriptions-item label="对方账号">{{ currentBankStatement.counterparty_account }}</el-descriptions-item>
        <el-descriptions-item label="对方行号">{{ currentBankStatement.counterparty_bank || '-' }}</el-descriptions-item>
        <el-descriptions-item label="用途">{{ currentBankStatement.purpose || '-' }}</el-descriptions-item>
        <el-descriptions-item label="摘要">{{ currentBankStatement.summary || '-' }}</el-descriptions-item>
        <el-descriptions-item label="附言" :span="2">{{ currentBankStatement.postscript || '-' }}</el-descriptions-item>
        <el-descriptions-item label="状态">
          <el-tag :type="getBankStatusType(currentBankStatement.status)">{{ currentBankStatement.status_display }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="匹配类型">{{ currentBankStatement.match_type_display || '-' }}</el-descriptions-item>
        <el-descriptions-item label="匹配供应商/客户">
          {{ currentBankStatement.supplier_name || currentBankStatement.customer_name || '-' }}
        </el-descriptions-item>
        <el-descriptions-item label="置信度">{{ currentBankStatement.match_confidence }}%</el-descriptions-item>
        <el-descriptions-item label="关联应付单">{{ currentBankStatement.related_ap_no || '-' }}</el-descriptions-item>
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
          <span :class="currentBankStatement.transaction_type === 'DEBIT' ? 'text-danger' : 'text-success'" style="font-size: 16px; font-weight: bold;">
            ¥{{ formatNumber(currentBankStatement.amount) }}
          </span>
        </el-form-item>
        <el-form-item label="匹配类型">
          <el-radio-group v-model="bankMatchForm.match_type">
            <el-radio label="AP">应付账款</el-radio>
            <el-radio label="AR">应收账款</el-radio>
            <el-radio label="EXPENSE">费用</el-radio>
            <el-radio label="OTHER">其他</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="供应商" v-if="bankMatchForm.match_type === 'AP'">
          <el-select v-model="bankMatchForm.supplier_id" placeholder="选择供应商" filterable clearable style="width: 100%;">
            <el-option v-for="s in suppliers" :key="s.id" :label="s.name" :value="s.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="应付账款" v-if="bankMatchForm.match_type === 'AP' && bankMatchForm.supplier_id">
          <el-select v-model="bankMatchForm.ap_id" placeholder="选择应付账款(可选)" filterable clearable style="width: 100%;">
            <el-option v-for="ap in supplierAPList" :key="ap.id" 
                      :label="`${ap.ap_no} - ¥${formatNumber(ap.amount_due)}`" 
                      :value="ap.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="客户" v-if="bankMatchForm.match_type === 'AR'">
          <el-select v-model="bankMatchForm.customer_id" placeholder="选择客户" filterable clearable style="width: 100%;">
            <el-option v-for="c in customers" :key="c.id" :label="c.name" :value="c.id" />
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

    <!-- 导入结果对话框 -->
    <el-dialog v-model="importResultVisible" title="导入结果" width="500px">
      <el-descriptions :column="2" border v-if="importResult">
        <el-descriptions-item label="批次号" :span="2">{{ importResult.batch_no }}</el-descriptions-item>
        <el-descriptions-item label="成功导入">
          <span class="text-success">{{ importResult.success_count }} 条</span>
        </el-descriptions-item>
        <el-descriptions-item label="跳过记录">
          <span class="text-muted">{{ importResult.skipped_count || 0 }} 条</span>
          <el-tooltip content="未匹配供应商或非业务流水（工资/税费等）" placement="top">
            <el-icon style="margin-left: 4px; cursor: help;"><QuestionFilled /></el-icon>
          </el-tooltip>
        </el-descriptions-item>
        <el-descriptions-item label="错误数">
          <span :class="importResult.error_count > 0 ? 'text-danger' : ''">{{ importResult.error_count }} 条</span>
        </el-descriptions-item>
        <el-descriptions-item label="自动匹配供应商">
          <span class="text-primary">{{ importResult.matched_count }} 条</span>
        </el-descriptions-item>
        <el-descriptions-item label="支出总额" :span="2">
          <span class="text-danger" style="font-size: 16px; font-weight: bold;">¥{{ formatNumber(importResult.debit_total) }}</span>
        </el-descriptions-item>
      </el-descriptions>
      <div v-if="importResult?.errors?.length > 0" style="margin-top: 15px;">
        <el-divider>错误详情 (前10条)</el-divider>
        <div v-for="(err, idx) in importResult.errors" :key="idx" class="error-item">
          行 {{ err.row }}: {{ err.error }}
        </div>
      </div>
      <template #footer>
        <el-button type="primary" @click="importResultVisible = false; loadBankStatements()">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, computed, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, DataAnalysis, CircleCheck, Upload, Download, Connection, QuestionFilled } from '@element-plus/icons-vue'
import request from '@/utils/request'

const loading = ref(false)
const reconciliationLoading = ref(false)
const bankLoading = ref(false)
const saving = ref(false)
const matching = ref(false)
const autoMatching = ref(false)
const activeTab = ref('bankStatements')

const apList = ref([])
const reconciliationList = ref([])
const bankStatements = ref([])
const selectedBankStatements = ref([])
const suppliers = ref([])
const customers = ref([])
const summaryData = ref([])
const selectedLines = ref([])
const supplierAPList = ref([])

const uploadRef = ref(null)
const uploadUrl = computed(() => {
  const baseUrl = import.meta.env.VITE_API_BASE_URL || '/api'
  return `${baseUrl}/finance/bank-statements/import_excel/`
})
const uploadHeaders = computed(() => {
  const token = localStorage.getItem('access_token')
  return token ? { Authorization: `Bearer ${token}` } : {}
})

const paymentVisible = ref(false)
const viewDialogVisible = ref(false)
const reconciliationDialogVisible = ref(false)
const detailDialogVisible = ref(false)
const summaryDialogVisible = ref(false)
const bankDetailVisible = ref(false)
const bankMatchVisible = ref(false)
const importResultVisible = ref(false)

const currentAP = ref({})
const currentReconciliation = ref(null)
const currentBankStatement = ref(null)
const detailTitle = ref('')
const importResult = ref(null)

const reconciliationFormRef = ref(null)

const searchForm = reactive({ supplier: null, status: null })
const bankSearchForm = reactive({ status: null, transaction_type: 'DEBIT', supplier: null })
const pagination = reactive({ page: 1, pageSize: 20, total: 0 })
const bankPagination = reactive({ page: 1, pageSize: 20, total: 0 })
const paymentForm = reactive({ amount: 0, payment_date: new Date().toISOString().split('T')[0], payment_method: 'BANK', notes: '' })
const bankMatchForm = reactive({ match_type: 'AP', supplier_id: null, customer_id: null, ap_id: null, ar_id: null, notes: '' })

const reconciliationForm = reactive({
  supplier: null,
  period_start: '',
  period_end: '',
  opening_balance: 0,
  notes: ''
})

const reconciliationRules = {
  supplier: [{ required: true, message: '请选择供应商' }],
  period_start: [{ required: true, message: '请选择开始日期' }],
  period_end: [{ required: true, message: '请选择结束日期' }]
}

const formatNumber = (num) => parseFloat(num || 0).toFixed(2)
const formatDateTime = (dt) => {
  if (!dt) return '-'
  return dt.replace('T', ' ').slice(0, 19)
}

const getAPStatusType = (s) => ({ 'UNPAID': 'warning', 'PARTIAL': 'primary', 'PAID': 'success', 'OVERDUE': 'danger' }[s] || 'info')
const getAPStatusLabel = (s) => ({ 'UNPAID': '未付款', 'PARTIAL': '部分付款', 'PAID': '已付款', 'OVERDUE': '已逾期' }[s] || s)
const getBankStatusType = (s) => ({ 'PENDING': 'warning', 'MATCHED': 'success', 'IGNORED': 'info', 'ERROR': 'danger' }[s] || 'info')

const getPaymentProgress = (row) => {
  const due = parseFloat(row.amount_due || 0)
  const paid = parseFloat(row.amount_paid || 0)
  if (due <= 0) return 0
  return Math.min(100, Math.round((paid / due) * 100))
}

const getReceiptStatusType = (status) => {
  const types = { 'NOT_RECEIVED': 'danger', 'PARTIAL': 'warning', 'RECEIVED': 'success', 'VERIFIED': 'success' }
  return types[status] || 'info'
}

const getReceiptStatusLabel = (status) => {
  const labels = { 'NOT_RECEIVED': '未收货', 'PARTIAL': '部分', 'RECEIVED': '已收货', 'VERIFIED': '已验收' }
  return labels[status] || status || '未知'
}

const getReceiptStatusText = getReceiptStatusLabel

const getReconciliationStatusType = (status) => {
  const types = { DRAFT: 'info', PENDING: 'warning', CONFIRMED: 'success', DISPUTED: 'danger', CLOSED: '' }
  return types[status] || 'info'
}

const getProgressColor = (progress) => {
  const p = Number(progress || 0)
  if (p >= 100) return '#67c23a'
  if (p >= 50) return '#409eff'
  if (p > 0) return '#e6a23c'
  return '#909399'
}

const handleTabChange = (tab) => {
  if (tab === 'payables') loadAPList()
  else if (tab === 'reconciliation') loadReconciliationList()
  else if (tab === 'bankStatements') loadBankStatements()
}

// 银行流水相关
const loadBankStatements = async () => {
  bankLoading.value = true
  try {
    const params = { page: bankPagination.page, page_size: bankPagination.pageSize, ...bankSearchForm }
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
  bankSearchForm.transaction_type = 'DEBIT'
  bankSearchForm.supplier = null
  bankPagination.page = 1
  loadBankStatements()
}

const handleBankSizeChange = (size) => {
  bankPagination.pageSize = size
  bankPagination.page = 1
  loadBankStatements()
}

const beforeUpload = (file) => {
  const isExcel = file.name.endsWith('.xlsx') || file.name.endsWith('.xls')
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

const exportBankStatements = async () => {
  try {
    const params = { ...bankSearchForm }
    Object.keys(params).forEach(k => { if (params[k] === null || params[k] === '') delete params[k] })
    
    const response = await request.get('/finance/bank-statements/export_excel/', {
      params,
      responseType: 'blob'
    })
    
    const url = window.URL.createObjectURL(new Blob([response]))
    const link = document.createElement('a')
    link.href = url
    link.setAttribute('download', `银行流水_${new Date().toISOString().slice(0, 10)}.xlsx`)
    document.body.appendChild(link)
    link.click()
    link.remove()
    window.URL.revokeObjectURL(url)
    
    ElMessage.success('导出成功')
  } catch (error) {
    ElMessage.error('导出失败')
  }
}

const autoMatchAll = async () => {
  try {
    autoMatching.value = true
    const response = await request.post('/finance/bank-statements/auto_match_all/')
    ElMessage.success(response.message || `成功匹配 ${response.matched_count} 条记录`)
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
  // Reset form
  bankMatchForm.match_type = row.transaction_type === 'DEBIT' ? 'AP' : 'AR'
  bankMatchForm.supplier_id = row.supplier || null
  bankMatchForm.customer_id = row.customer || null
  bankMatchForm.ap_id = null
  bankMatchForm.ar_id = null
  bankMatchForm.notes = ''
  
  if (row.supplier) {
    loadSupplierAPs(row.supplier)
  }
  
  bankMatchVisible.value = true
}

const handleIgnoreBank = async (row) => {
  try {
    await ElMessageBox.confirm('确定要忽略此银行流水吗？', '确认')
    await request.post(`/finance/bank-statements/${row.id}/ignore/`)
    ElMessage.success('已忽略')
    loadBankStatements()
  } catch (error) {
    if (error !== 'cancel') ElMessage.error('操作失败')
  }
}

const loadSupplierAPs = async (supplierId) => {
  if (!supplierId) {
    supplierAPList.value = []
    return
  }
  try {
    const response = await request.get('/finance/payables/', { 
      params: { supplier: supplierId, status: 'PENDING', page_size: 50 } 
    })
    supplierAPList.value = response.results || []
  } catch (error) {
    console.error('加载供应商应付账款失败:', error)
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

const submitBankMatch = async () => {
  if (!bankMatchForm.match_type) {
    return ElMessage.warning('请选择匹配类型')
  }
  if (bankMatchForm.match_type === 'AP' && !bankMatchForm.supplier_id) {
    return ElMessage.warning('请选择供应商')
  }
  if (bankMatchForm.match_type === 'AR' && !bankMatchForm.customer_id) {
    return ElMessage.warning('请选择客户')
  }
  
  try {
    matching.value = true
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

// Watch for supplier change in match form
watch(() => bankMatchForm.supplier_id, (newVal) => {
  if (newVal) {
    loadSupplierAPs(newVal)
  } else {
    supplierAPList.value = []
  }
  bankMatchForm.ap_id = null
})

const loadAPList = async () => {
  loading.value = true
  try {
    const params = { page: pagination.page, page_size: pagination.pageSize, ...searchForm }
    Object.keys(params).forEach(k => { if (params[k] === null) delete params[k] })
    const response = await request.get('/finance/payables/', { params })
    apList.value = response.results || []
    pagination.total = response.count || 0
  } catch (error) {
    ElMessage.error('加载应付账款失败')
  } finally {
    loading.value = false
  }
}

const loadSuppliers = async () => {
  try {
    const response = await request.get('/masterdata/suppliers/', { params: { page_size: 100 } })
    suppliers.value = response.results || response || []
  } catch (error) {
    console.error('加载供应商失败:', error)
  }
}

const loadReconciliationList = async () => {
  reconciliationLoading.value = true
  try {
    const res = await request.get('/finance/purchase-reconciliations/')
    reconciliationList.value = res.results || res || []
  } catch (error) {
    ElMessage.error('加载采购对账单失败')
  } finally {
    reconciliationLoading.value = false
  }
}

const resetSearch = () => {
  searchForm.supplier = null
  searchForm.status = null
  pagination.page = 1
  loadAPList()
}

const handleView = (row) => {
  currentAP.value = row
  viewDialogVisible.value = true
}

const handlePayment = (row) => {
  currentAP.value = row
  paymentForm.amount = (row.amount_due || 0) - (row.amount_paid || 0)
  paymentVisible.value = true
}

const submitPayment = async () => {
  if (!paymentForm.amount || paymentForm.amount <= 0) return ElMessage.warning('请输入付款金额')
  try {
    await request.post(`/finance/payables/${currentAP.value.id}/record_payment/`, paymentForm)
    ElMessage.success('付款登记成功')
    paymentVisible.value = false
    loadAPList()
  } catch (error) {
    ElMessage.error('付款登记失败')
  }
}

const handleDelete = async (row) => {
  try {
    await ElMessageBox.confirm('确定要删除此应付账款记录吗？此操作不可恢复！', '删除应付账款', { type: 'warning' })
    await request.delete(`/finance/payables/${row.id}/`)
    ElMessage.success('应付账款已删除')
    loadAPList()
  } catch (error) {
    if (error !== 'cancel') ElMessage.error('删除应付账款失败')
  }
}

// 对账功能
const handleAddReconciliation = () => {
  Object.assign(reconciliationForm, { supplier: null, period_start: '', period_end: '', opening_balance: 0, notes: '' })
  reconciliationDialogVisible.value = true
}

const saveReconciliation = async () => {
  try {
    await reconciliationFormRef.value.validate()
    saving.value = true
    await request.post('/finance/purchase-reconciliations/', reconciliationForm)
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
    const res = await request.get(`/finance/purchase-reconciliations/${row.id}/`)
    currentReconciliation.value = res
    detailTitle.value = `采购对账单 - ${row.reconciliation_no}`
    detailDialogVisible.value = true
  } catch (error) {
    ElMessage.error('加载详情失败')
  }
}

const handleGenerateReconciliation = async (row) => {
  try {
    await ElMessageBox.confirm('确定要生成对账明细吗？', '确认')
    await request.post(`/finance/purchase-reconciliations/${row.id}/generate_lines/`)
    ElMessage.success('生成成功')
    loadReconciliationList()
  } catch (error) {
    if (error !== 'cancel') ElMessage.error('生成失败: ' + (error.response?.data?.error || error.message))
  }
}

const handleConfirmReconciliation = async (row) => {
  try {
    await ElMessageBox.confirm('确定要确认该对账单吗？', '确认')
    await request.post(`/finance/purchase-reconciliations/${row.id}/confirm/`)
    ElMessage.success('确认成功')
    loadReconciliationList()
  } catch (error) {
    if (error !== 'cancel') ElMessage.error('确认失败')
  }
}

const loadSupplierSummary = async () => {
  try {
    const res = await request.get('/finance/purchase-reconciliations/supplier_summary/')
    summaryData.value = res
    summaryDialogVisible.value = true
  } catch (error) {
    ElMessage.error('加载汇总失败')
  }
}

const handleLineSelectionChange = (selection) => {
  selectedLines.value = selection
}

const confirmReceiptLine = async (row) => {
  try {
    await request.post(`/finance/purchase-reconciliations/${currentReconciliation.value.id}/confirm_receipt/${row.id}/`, { receipt_status: 'RECEIVED' })
    ElMessage.success('收货确认成功')
    handleViewReconciliation(currentReconciliation.value)
  } catch (error) {
    ElMessage.error('确认失败: ' + (error.response?.data?.error || error.message))
  }
}

const batchConfirmReceipt = async () => {
  if (selectedLines.value.length === 0) return ElMessage.warning('请选择要确认的明细')
  try {
    const lineIds = selectedLines.value.filter(l => l.line_type === 'ORDER').map(l => l.id)
    if (lineIds.length === 0) return ElMessage.warning('请选择订单类型的明细')
    await request.post(`/finance/purchase-reconciliations/${currentReconciliation.value.id}/batch_confirm_receipt/`, { line_ids: lineIds })
    ElMessage.success('批量确认成功')
    handleViewReconciliation(currentReconciliation.value)
  } catch (error) {
    ElMessage.error('确认失败: ' + (error.response?.data?.error || error.message))
  }
}

onMounted(() => {
  loadBankStatements()
  loadSuppliers()
  loadCustomers()
})
</script>

<style scoped>
.ap-list { padding: 20px; }
.card-header { display: flex; justify-content: space-between; align-items: center; }
.search-form { margin-bottom: 20px; }
.tab-header { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.text-danger { color: #f56c6c; font-weight: bold; }
.text-warning { color: #e6a23c; font-weight: bold; }
.text-success { color: #67c23a; font-weight: bold; }
.text-primary { color: #409eff; font-weight: bold; }
.text-info { color: #909399; font-weight: bold; }
.text-muted { color: #c0c4cc; }
.amount-primary { font-size: 16px; font-weight: 600; color: #409EFF; }
.amount-success { font-size: 16px; font-weight: 600; color: #67C23A; }
.amount-danger { font-size: 18px; font-weight: 600; color: #F56C6C; }
.amount-lg { font-size: 16px; font-weight: 600; }
.error-item { padding: 5px 10px; margin: 5px 0; background: #fef0f0; color: #f56c6c; border-radius: 4px; font-size: 13px; }
</style>
