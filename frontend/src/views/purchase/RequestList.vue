<template>
  <div class="purchase-request-list">
    <!-- 物料需求清单区域 -->
    <el-card style="margin-bottom: 20px;">
      <template #header>
        <div class="card-header">
          <span>
            <el-icon><List /></el-icon>
            物料需求清单（导出询价用）
          </span>
          <el-select 
            v-model="bomProject" 
            placeholder="选择项目查看BOM" 
            clearable 
            filterable
            style="width: 280px;"
            @change="loadBomItems"
          >
            <el-option v-for="p in projects" :key="p.id" :label="`${p.code} - ${p.name}`" :value="p.id" />
          </el-select>
        </div>
      </template>
      
      <div v-if="!bomProject" class="tip-box">
        <el-alert title="请选择项目以查看需要采购的物料" type="info" :closable="false" />
      </div>
      
      <template v-else>
        <!-- 筛选条件 -->
        <el-row :gutter="15" style="margin-bottom: 15px;">
          <el-col :span="4">
            <el-select v-model="bomFilter.hasDrawing" placeholder="有图/无图" clearable style="width: 100%;">
              <el-option label="全部" value="" />
              <el-option label="有图" value="HAS_DRAWING" />
              <el-option label="无图" value="NO_DRAWING" />
            </el-select>
          </el-col>
          <el-col :span="5">
            <el-select v-model="bomFilter.itemType" placeholder="物料类型" clearable style="width: 100%;">
              <el-option label="全部" value="" />
              <el-option label="机加" value="机加" />
              <el-option label="钣金" value="钣金" />
              <el-option label="特殊工艺" value="特殊工艺" />
              <el-option label="其他" value="其他" />
              <el-option label="机械类" value="机械类" />
              <el-option label="电气类" value="电气类" />
              <el-option label="耗材辅料" value="耗材辅料" />
              <el-option label="办公用品" value="办公用品" />
            </el-select>
          </el-col>
          <el-col :span="5">
            <el-input v-model="bomFilter.brand" placeholder="版本/品牌筛选" clearable />
          </el-col>
          <el-col :span="5">
            <el-input v-model="bomFilter.keyword" placeholder="搜索编码/名称/规格" clearable />
          </el-col>
          <el-col :span="5">
            <el-button @click="resetBomFilters">
              <el-icon><Refresh /></el-icon>
              重置
            </el-button>
            <el-button type="success" @click="handleExportBomForQuote" :disabled="filteredBomItems.length === 0">
              <el-icon><Download /></el-icon>
              导出询价清单
            </el-button>
          </el-col>
        </el-row>
        
        <!-- 筛选结果统计 -->
        <div style="margin-bottom: 10px; color: #666;">
          筛选结果: <el-tag type="info">{{ filteredBomItems.length }}</el-tag> / {{ bomItems.length }} 项
          <span v-if="selectedBomRows.length > 0" style="margin-left: 20px;">
            已选择: <el-tag type="primary">{{ selectedBomRows.length }}</el-tag> 项
            <el-button type="success" size="small" @click="handleExportSelectedBom" style="margin-left: 10px;">
              导出选中
            </el-button>
          </span>
        </div>
        
        <!-- BOM物料列表 -->
        <el-table 
          :data="filteredBomItems" 
          v-loading="bomLoading" 
          stripe 
          border 
          size="small"
          max-height="350"
          ref="bomTableRef"
          @selection-change="handleBomSelectionChange"
        >
          <el-table-column type="selection" width="40" />
          <el-table-column prop="item_code" label="物料编码" width="120" />
          <el-table-column prop="has_drawing_display" label="有图/无图" width="80" />
          <el-table-column prop="item_type_display" label="物料类型" width="80" />
          <el-table-column prop="item_name" label="物料名称" min-width="150" show-overflow-tooltip />
          <el-table-column prop="specification" label="规格型号" width="120" show-overflow-tooltip />
          <el-table-column prop="version_brand" label="版本/品牌" width="100" show-overflow-tooltip />
          <el-table-column prop="unit" label="单位" width="50" align="center" />
          <el-table-column prop="planned_qty" label="需求数量" width="80" align="right" />
          <el-table-column prop="required_date" label="需求日期" width="100" />
        </el-table>
      </template>
    </el-card>

    <!-- 采购申请列表 -->
    <el-card>
      <template #header>
        <div class="card-header">
          <span>采购申请列表</span>
          <div class="header-actions">
          <el-button type="primary" v-permission="'purchase:request:create'" @click="handleAdd">
            <el-icon><Plus /></el-icon>
            创建申请
          </el-button>
            <el-dropdown style="margin-left: 10px;">
              <el-button type="success">
                导入 <el-icon class="el-icon--right"><ArrowDown /></el-icon>
              </el-button>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item @click="handleImport">
                    <el-icon><Upload /></el-icon> 导入采购申请
                  </el-dropdown-item>
                  <el-dropdown-item divided @click="handleDownloadTemplate">
                    <el-icon><Document /></el-icon> 下载导入模板
                  </el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
          </div>
        </div>
      </template>

      <!-- 搜索栏 -->
      <el-form :inline="true" class="search-form">
        <el-form-item label="项目">
          <el-select 
            v-model="searchForm.project" 
            placeholder="选择项目" 
            clearable 
            filterable
            style="width: 250px;"
            @change="loadRequests"
          >
            <el-option v-for="p in projects" :key="p.id" :label="p.name" :value="p.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="状态">
          <el-select 
            v-model="searchForm.status" 
            placeholder="选择状态" 
            clearable 
            style="width: 120px;"
            @change="loadRequests"
          >
            <el-option label="全部" :value="null" />
            <el-option label="草稿" value="DRAFT" />
            <el-option label="已提交" value="SUBMITTED" />
            <el-option label="已批准" value="APPROVED" />
            <el-option label="已拒绝" value="REJECTED" />
            <el-option label="已转订单" value="CONVERTED" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="loadRequests">
            <el-icon><Search /></el-icon>
            搜索
          </el-button>
          <el-button @click="resetSearch">
            <el-icon><RefreshLeft /></el-icon>
            重置
          </el-button>
        </el-form-item>
      </el-form>
      
      <!-- 过滤提示 -->
      <el-alert
        v-if="searchForm.project || searchForm.status"
        :title="getFilterTip()"
        type="info"
        :closable="false"
        style="margin-bottom: 15px;"
      />

      <!-- 批量操作工具栏 -->
      <div class="table-toolbar" v-permission="'purchase:request:delete'" v-if="canDelete && selectedRows.length > 0">
        <span>已选择 {{ selectedRows.length }} 项</span>
        <el-button 
          type="danger" 
          size="small" 
          @click="batchDelete"
          :loading="deleteLoading"
        >
          批量删除
        </el-button>
      </div>

      <el-table :data="requests" v-loading="loading" stripe border @selection-change="handleSelectionChange">
        <el-table-column v-permission="'purchase:request:delete'" v-if="canDelete" type="selection" width="55" fixed />
        <el-table-column prop="request_no" label="采购申请号" width="140" fixed />
        <el-table-column prop="project_name" label="项目" width="160" show-overflow-tooltip />
        <el-table-column label="物料名称" width="150" show-overflow-tooltip>
          <template #default="{ row }">
            <span v-if="row.item_summary">{{ row.item_summary.item_name }}</span>
            <span v-else class="text-muted">-</span>
            <el-tag v-if="row.lines_count > 1" size="small" type="info" style="margin-left: 4px;">+{{ row.lines_count - 1 }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="规格/图纸号" width="120" show-overflow-tooltip>
          <template #default="{ row }">
            {{ row.item_summary?.specification || '-' }}
          </template>
        </el-table-column>
        <el-table-column label="单价" width="90" align="right">
          <template #default="{ row }">
            <span v-if="row.item_summary">¥{{ formatMoney(row.item_summary.unit_price) }}</span>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column label="单位" width="60" align="center">
          <template #default="{ row }">
            {{ row.item_summary?.unit || '-' }}
          </template>
        </el-table-column>
        <el-table-column label="数量" width="80" align="right">
          <template #default="{ row }">
            {{ row.total_qty || 0 }}
          </template>
        </el-table-column>
        <el-table-column prop="supplier_name" label="供应商" width="140" show-overflow-tooltip />
        <el-table-column prop="requestor_name" label="申请人" width="80" />
        <el-table-column prop="required_date" label="需求日期" width="100" />
        <el-table-column prop="status" label="状态" width="90">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)" size="small">{{ getStatusLabel(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="total_with_tax" label="含税总额" width="100" align="right">
          <template #default="{ row }">
            ¥{{ formatMoney(row.total_with_tax || row.total_amount) }}
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="140" />
        <el-table-column label="操作" width="420" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="handleView(row)">查看</el-button>
            <el-button size="small" v-permission="'purchase:request:edit'" @click="handleEdit(row)" v-if="row.status === 'DRAFT'">编辑</el-button>
            <el-button size="small" type="warning" @click="handleSubmit(row)" v-if="row.status === 'DRAFT'">提交</el-button>
            <el-button size="small" type="info" @click="showWorkflowProgress(row)" v-if="row.status === 'SUBMITTED'">审批进度</el-button>
            <el-button size="small" type="success" @click="handleApprove(row)" v-if="row.status === 'SUBMITTED'">批准</el-button>
            <el-button size="small" type="danger" @click="handleReject(row)" v-if="row.status === 'SUBMITTED'">拒绝</el-button>
            <el-button size="small" type="info" @click="handleWithdraw(row)" v-if="row.status === 'SUBMITTED' || row.status === 'APPROVED'">撤回</el-button>
            <el-button size="small" type="primary" @click="convertToPO(row)" v-if="row.status === 'APPROVED'">转采购订单</el-button>
            <el-button 
              v-if="canDelete"
              size="small" 
              type="danger" 
              @click="deleteRow(row)"
              :loading="deleteLoading"
            >
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>
      
      <!-- 分页 -->
      <el-pagination
        v-model:current-page="pagination.page"
        v-model:page-size="pagination.pageSize"
        :page-sizes="[10, 20, 50, 100]"
        :total="pagination.total"
        layout="total, sizes, prev, pager, next"
        @size-change="loadRequests"
        @current-change="loadRequests"
        style="margin-top: 20px; justify-content: flex-end;"
      />
    </el-card>

    <!-- 创建/编辑对话框 -->
    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="1100px" destroy-on-close>
      <el-form :model="form" :rules="rules" ref="formRef" label-width="100px">
        <el-row :gutter="20">
          <el-col :span="6">
            <el-form-item label="关联项目" prop="project">
              <el-select v-model="form.project" placeholder="选择项目" filterable clearable style="width: 100%;" @change="onProjectChange">
                <el-option v-for="p in projects" :key="p.id" :label="p.name" :value="p.id" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="6">
            <el-form-item label="供应商">
              <el-select v-model="form.supplier" placeholder="选择供应商" filterable clearable style="width: 100%;">
                <el-option v-for="s in suppliers" :key="s.id" :label="s.name" :value="s.id" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="6">
            <el-form-item label="需求日期" prop="required_date">
              <el-date-picker v-model="form.required_date" type="date" value-format="YYYY-MM-DD" placeholder="选择日期" style="width: 100%;" />
            </el-form-item>
          </el-col>
          <el-col :span="6">
            <el-form-item label="增值税率">
              <el-select v-model="form.tax_rate" placeholder="选择税率" style="width: 100%;">
                <el-option :value="0" label="0% (免税)" />
                <el-option :value="1" label="1%" />
                <el-option :value="3" label="3%" />
                <el-option :value="6" label="6%" />
                <el-option :value="9" label="9%" />
                <el-option :value="13" label="13%" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="备注">
          <el-input v-model="form.notes" type="textarea" :rows="2" placeholder="请输入备注" />
        </el-form-item>
        
        <!-- 申请明细 -->
        <el-divider content-position="left">申请明细</el-divider>
        <el-button type="primary" size="small" @click="addLine" style="margin-bottom: 10px;">
          <el-icon><Plus /></el-icon>
          添加物料
        </el-button>
        
        <el-table :data="form.lines" border size="small">
          <el-table-column label="物料" min-width="200">
            <template #default="{ row, $index }">
              <el-select v-model="row.item" placeholder="选择物料" filterable style="width: 100%;" @change="onItemChange($index)">
                <el-option v-for="item in availableItems" :key="item.id" :label="`${item.sku} - ${item.name}`" :value="item.id" />
              </el-select>
              <div v-if="form.project && projectItems.length === 0" style="color: #E6A23C; font-size: 12px;">
                该项目无未申请物料
              </div>
            </template>
          </el-table-column>
          <el-table-column label="物料名称" min-width="120" show-overflow-tooltip>
            <template #default="{ row }">
              {{ getItemName(row.item) }}
            </template>
          </el-table-column>
          <el-table-column label="型号/图号" width="120" show-overflow-tooltip>
            <template #default="{ row }">
              {{ getItemModel(row.item) }}
            </template>
          </el-table-column>
          <el-table-column label="类型" width="80" show-overflow-tooltip>
            <template #default="{ row }">
              {{ getItemType(row.item) }}
            </template>
          </el-table-column>
          <el-table-column label="数量" width="90">
            <template #default="{ row }">
              <el-input-number v-model="row.qty" :min="0.01" :precision="2" size="small" controls-position="right" style="width: 100%;" />
            </template>
          </el-table-column>
          <el-table-column label="单位" width="60" align="center">
            <template #default="{ row }">
              {{ getItemUnit(row.item) }}
            </template>
          </el-table-column>
          <el-table-column label="单价" width="100">
            <template #default="{ row }">
              <el-input-number v-model="row.estimated_price" :min="0" :precision="2" size="small" controls-position="right" style="width: 100%;" />
            </template>
          </el-table-column>
          <el-table-column label="金额" width="90" align="right">
            <template #default="{ row }">
              ¥{{ getLineAmount(row).toFixed(2) }}
            </template>
          </el-table-column>
          <el-table-column label="税额" width="80" align="right">
            <template #default="{ row }">
              ¥{{ getLineTax(row).toFixed(2) }}
            </template>
          </el-table-column>
          <el-table-column label="含税价" width="90" align="right">
            <template #default="{ row }">
              ¥{{ getLineTotalWithTax(row).toFixed(2) }}
            </template>
          </el-table-column>
          <el-table-column label="交期" width="130">
            <template #default="{ row }">
              <el-date-picker v-model="row.required_date" type="date" value-format="YYYY-MM-DD" placeholder="交期" size="small" style="width: 100%;" />
            </template>
          </el-table-column>
          <el-table-column label="备注" min-width="120">
            <template #default="{ row }">
              <el-input v-model="row.notes" placeholder="备注" size="small" />
            </template>
          </el-table-column>
          <el-table-column label="操作" width="50" align="center" fixed="right">
            <template #default="{ $index }">
              <el-button type="danger" size="small" link @click="removeLine($index)">
                <el-icon><Delete /></el-icon>
              </el-button>
            </template>
          </el-table-column>
        </el-table>
        
        <div class="total-section">
          <div class="total-row">
            <span class="label">不含税金额：</span>
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
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSave" :loading="saving">保存</el-button>
      </template>
    </el-dialog>
    
    <!-- 查看详情对话框 -->
    <el-dialog v-model="viewDialogVisible" title="采购申请详情" width="900px">
      <el-descriptions :column="3" border v-if="currentRequest">
        <el-descriptions-item label="申请单号">{{ currentRequest.request_no }}</el-descriptions-item>
        <el-descriptions-item label="状态">
          <el-tag :type="getStatusType(currentRequest.status)">{{ getStatusLabel(currentRequest.status) }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="申请人">{{ currentRequest.requestor_name }}</el-descriptions-item>
        <el-descriptions-item label="关联项目">{{ currentRequest.project_name || '-' }}</el-descriptions-item>
        <el-descriptions-item label="供应商">{{ currentRequest.supplier_name || '-' }}</el-descriptions-item>
        <el-descriptions-item label="需求日期">{{ currentRequest.required_date || '-' }}</el-descriptions-item>
        <el-descriptions-item label="不含税金额">¥{{ parseFloat(currentRequest.total_amount || 0).toFixed(2) }}</el-descriptions-item>
        <el-descriptions-item label="税额">¥{{ parseFloat(currentRequest.tax_amount || 0).toFixed(2) }}</el-descriptions-item>
        <el-descriptions-item label="含税总额">¥{{ parseFloat(currentRequest.total_with_tax || 0).toFixed(2) }}</el-descriptions-item>
        <el-descriptions-item label="创建时间" :span="3">{{ currentRequest.created_at }}</el-descriptions-item>
        <el-descriptions-item label="备注" :span="3">{{ currentRequest.notes || '-' }}</el-descriptions-item>
      </el-descriptions>
      
      <el-divider content-position="left">申请明细</el-divider>
      <el-table :data="currentRequest?.lines || []" border size="small">
        <el-table-column prop="item_name" label="物料" min-width="150" />
        <el-table-column prop="qty" label="数量" width="70" align="right" />
        <el-table-column prop="item_unit" label="单位" width="60" align="center" />
        <el-table-column label="单价" width="90" align="right">
          <template #default="{ row }">
            ¥{{ parseFloat(row.estimated_price || 0).toFixed(2) }}
          </template>
        </el-table-column>
        <el-table-column label="金额" width="90" align="right">
          <template #default="{ row }">
            ¥{{ ((row.qty || 0) * (row.estimated_price || 0)).toFixed(2) }}
          </template>
        </el-table-column>
        <el-table-column label="税额" width="80" align="right">
          <template #default="{ row }">
            ¥{{ (((row.qty || 0) * (row.estimated_price || 0)) * (currentRequest?.tax_rate || 0) / 100).toFixed(2) }}
          </template>
        </el-table-column>
        <el-table-column label="含税价" width="90" align="right">
          <template #default="{ row }">
            ¥{{ (((row.qty || 0) * (row.estimated_price || 0)) * (1 + (currentRequest?.tax_rate || 0) / 100)).toFixed(2) }}
          </template>
        </el-table-column>
        <el-table-column prop="required_date" label="交期" width="100" />
        <el-table-column prop="notes" label="备注" min-width="100" />
      </el-table>
    </el-dialog>
    
    <!-- 转采购订单对话框 -->
    <el-dialog v-model="convertDialogVisible" title="转换为采购订单" width="500px">
      <el-form :model="convertForm" label-width="100px">
        <el-form-item label="选择供应商" required>
          <el-select v-model="convertForm.supplier" placeholder="请选择供应商" filterable style="width: 100%;">
            <el-option v-for="s in suppliers" :key="s.id" :label="s.name" :value="s.id" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="convertDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="doConvertToPO" :loading="converting">确定转换</el-button>
      </template>
    </el-dialog>

    <!-- 导入采购申请对话框 -->
    <el-dialog v-model="importDialogVisible" title="导入采购申请" width="700px">
      <div class="import-content">
        <el-alert 
          title="导入说明" 
          type="info" 
          :closable="false" 
          style="margin-bottom: 20px;"
        >
          <template #default>
            <div style="line-height: 1.8;">
              <p>1. 请使用从上方"物料需求清单"导出的Excel文件</p>
              <p>2. 系统会校验Excel中的项目号是否与选择的项目一致</p>
              <p>3. 系统会按供应商自动拆分成多个采购申请</p>
            </div>
          </template>
        </el-alert>
        
        <!-- 项目选择 -->
        <el-form-item label="关联项目" label-width="80px" style="margin-bottom: 20px;">
          <el-select 
            v-model="importProject" 
            placeholder="选择项目（用于校验Excel中的项目号）" 
            clearable 
            filterable
            style="width: 100%;"
          >
            <el-option 
              v-for="p in projects" 
              :key="p.id" 
              :label="`${p.code} - ${p.name}`" 
              :value="p.id" 
            />
          </el-select>
          <div class="el-form-item__tip" style="color: #909399; font-size: 12px; margin-top: 5px;">
            选择项目后，系统会校验Excel中的项目号是否匹配
          </div>
        </el-form-item>
        
        <el-upload
          ref="importUploadRef"
          drag
          :auto-upload="false"
          accept=".xlsx,.xls"
          :limit="1"
          :on-change="handleImportFileChange"
          :on-exceed="handleImportExceed"
          :file-list="importFileList"
        >
          <el-icon class="el-icon--upload"><UploadFilled /></el-icon>
          <div class="el-upload__text">
            将文件拖到此处，或<em>点击上传</em>
          </div>
          <template #tip>
            <div class="el-upload__tip">只能上传Excel文件(.xlsx/.xls)</div>
          </template>
        </el-upload>
        
        <!-- 项目号不匹配错误 -->
        <div v-if="importError && importError.type === 'project_mismatch'" class="import-error" style="margin-top: 20px;">
          <el-alert type="error" :closable="false">
            <template #title>
              <strong>{{ importError.title }}</strong>
            </template>
            <template #default>
              <div style="margin-top: 10px;">
                <p><strong>您选择的项目：</strong>{{ importError.selectedProject }}</p>
                <p><strong>Excel中的项目号：</strong>{{ importError.excelProjects }}</p>
                <p style="margin-top: 10px;"><strong>不匹配的记录示例：</strong></p>
                <ul style="margin-left: 20px;">
                  <li v-for="(detail, idx) in importError.details" :key="idx">{{ detail }}</li>
                </ul>
                <p style="margin-top: 10px; color: #E6A23C;">
                  <strong>建议：</strong>{{ importError.suggestion }}
                </p>
              </div>
            </template>
          </el-alert>
        </div>
        
        <!-- 导入结果 -->
        <div v-if="importResult" class="import-result" style="margin-top: 20px;">
          <el-alert 
            :title="importResult.message" 
            :type="importResult.success ? 'success' : 'warning'" 
            :closable="false"
          />
          <div v-if="importResult.purchase_requests && importResult.purchase_requests.length > 0" style="margin-top: 10px;">
            <p><strong>已创建的采购申请：</strong></p>
            <el-table :data="importResult.purchase_requests" border size="small">
              <el-table-column prop="request_no" label="申请单号" width="140" />
              <el-table-column prop="project_name" label="项目" width="120" />
              <el-table-column prop="supplier_name" label="供应商" />
              <el-table-column prop="lines_count" label="物料数" width="70" align="center" />
              <el-table-column prop="total_amount" label="金额" width="100" align="right">
                <template #default="{ row }">¥{{ formatMoney(row.total_amount) }}</template>
              </el-table-column>
            </el-table>
          </div>
          <div v-if="importResult.errors && importResult.errors.length > 0" style="margin-top: 10px;">
            <p class="text-danger"><strong>导入错误（{{ importResult.errors.length }}条）：</strong></p>
            <ul style="max-height: 150px; overflow-y: auto;">
              <li v-for="err in importResult.errors.slice(0, 10)" :key="err.row" class="text-danger">
                行{{ err.row }}: {{ err.sku }} - {{ err.error }}
              </li>
            </ul>
          </div>
        </div>
      </div>
      <template #footer>
        <el-button @click="importDialogVisible = false">关闭</el-button>
        <el-button type="primary" @click="handleConfirmImport" :loading="importing" :disabled="!importFile">
          开始导入
        </el-button>
      </template>
    </el-dialog>
  </div>

    <!-- 审批进度弹窗 -->
    <WorkflowProgress
      v-model="workflowDialogVisible"
      :business-type="workflowBusinessType"
      :business-id="workflowBusinessId"
    />
  </template>

<script setup>
import WorkflowProgress from '@/components/WorkflowProgress.vue'

import { ref, reactive, onMounted, computed } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Delete, Search, RefreshLeft, ArrowDown, Upload, Download, Document, UploadFilled, List, Refresh } from '@element-plus/icons-vue'
import {
  getPurchaseRequests, getPurchaseRequest, createPurchaseRequest, updatePurchaseRequest,
  submitPurchaseRequest, approvePurchaseRequest, rejectPurchaseRequest, withdrawPurchaseRequest,
  convertRequestToPO, importPurchaseRequests, exportPurchaseRequestTemplate
} from '@/api/purchase'
import { getWorkflowByBusiness, approveTask, rejectTask } from '@/api/workflow'
import { useBatchDelete } from '@/composables/useBatchDelete'
import { usePermission } from '@/composables/usePermission'
import { getItemList, getSupplierList } from '@/api/masterdata'
import { exportBOMForQuote, getBOMList } from '@/api/projects/bom'
import { getProjectList } from '@/api/projects/project'

const route = useRoute()

// 权限检查
const { canDelete } = usePermission()

// 批量删除功能 - 使用箭头函数包装避免 TDZ 错误
const { selectedRows, loading: deleteLoading, handleSelectionChange, batchDelete, deleteRow } = useBatchDelete(
  '/purchase/requests/',
  {
    onSuccess: () => loadRequests(),
    confirmTitle: '删除采购申请',
    confirmMessage: '确定要删除该采购申请吗？删除后不可恢复！'
  }
)

const workflowDialogVisible = ref(false)
const workflowBusinessId = ref(null)
const workflowBusinessType = 'PURCHASE_REQUEST'

const showWorkflowProgress = (row) => {
  workflowBusinessId.value = row.id
  workflowDialogVisible.value = true
}

const loading = ref(false)
const saving = ref(false)
const converting = ref(false)
const requests = ref([])
const projects = ref([])
const items = ref([])
const projectItems = ref([])  // 项目中未申请的物料
const suppliers = ref([])
const dialogVisible = ref(false)
const viewDialogVisible = ref(false)
const convertDialogVisible = ref(false)
const dialogTitle = ref('创建采购申请')
const isEdit = ref(false)
const formRef = ref(null)
const currentRequest = ref(null)
const currentConvertId = ref(null)

const searchForm = reactive({
  project: null,
  status: null
})

const pagination = reactive({
  page: 1,
  pageSize: 20,
  total: 0
})

const form = reactive({
  id: null,
  project: null,
  supplier: null,
  required_date: '',
  tax_rate: 13,
  notes: '',
  lines: []
})

const convertForm = reactive({
  supplier: null
})

// 导入相关
const importDialogVisible = ref(false)
const importing = ref(false)
const importFile = ref(null)
const importFileList = ref([])
const importUploadRef = ref(null)
const importResult = ref(null)
const importProject = ref(null)  // 导入时选择的项目
const importError = ref(null)    // 项目号不匹配等错误

// BOM物料筛选相关
const bomProject = ref(null)
const bomItems = ref([])
const bomLoading = ref(false)
const bomTableRef = ref(null)
const selectedBomRows = ref([])
const bomFilter = reactive({
  hasDrawing: '',
  itemType: '',
  brand: '',
  keyword: ''
})

// 筛选后的BOM列表
const filteredBomItems = computed(() => {
  let result = bomItems.value
  
  // 有图/无图筛选
  if (bomFilter.hasDrawing) {
    result = result.filter(item => item.has_drawing === bomFilter.hasDrawing)
  }
  
  // 物料类型筛选
  if (bomFilter.itemType) {
    result = result.filter(item => {
      const itemType = item.item_type_display || item.item_type || ''
      return itemType.includes(bomFilter.itemType)
    })
  }
  
  // 版本/品牌筛选
  if (bomFilter.brand.trim()) {
    const brandKeyword = bomFilter.brand.toLowerCase().trim()
    result = result.filter(item => {
      const versionBrand = (item.version_brand || '').toLowerCase()
      return versionBrand.includes(brandKeyword)
    })
  }
  
  // 关键字搜索
  if (bomFilter.keyword.trim()) {
    const keyword = bomFilter.keyword.toLowerCase().trim()
    result = result.filter(item => {
      return (item.item_code && item.item_code.toLowerCase().includes(keyword)) ||
             (item.item_name && item.item_name.toLowerCase().includes(keyword)) ||
             (item.specification && item.specification.toLowerCase().includes(keyword))
    })
  }
  
  return result
})

const rules = {
  required_date: [{ required: true, message: '请选择需求日期', trigger: 'change' }]
}

const formatMoney = (value) => {
  const amount = Number.parseFloat(value ?? 0)
  return Number.isFinite(amount) ? amount.toFixed(2) : '0.00'
}

const getStatusType = (status) => {
  const types = { 
    DRAFT: 'info', 
    SUBMITTED: 'warning', 
    PENDING: 'warning',
    APPROVED: 'success', 
    REJECTED: 'danger', 
    CONVERTED: '' 
  }
  return types[status] || 'info'
}

const getStatusLabel = (status) => {
  const labels = { 
    DRAFT: '草稿', 
    SUBMITTED: '已提交', 
    PENDING: '审批中',
    APPROVED: '已批准', 
    REJECTED: '已拒绝', 
    CONVERTED: '已转订单' 
  }
  return labels[status] || status
}

const loadRequests = async () => {
  loading.value = true
  try {
    const params = {
      page: pagination.page,
      page_size: pagination.pageSize
    }
    if (searchForm.project) params.project = searchForm.project
    if (searchForm.status) params.status = searchForm.status
    
    const res = await getPurchaseRequests(params)
    requests.value = res.data?.results || res.results || res.data || []
    pagination.total = res.data?.count || res.count || 0
  } catch (error) {
    ElMessage.error('加载采购申请失败')
  } finally {
    loading.value = false
  }
}

const loadProjects = async () => {
  try {
    const res = await getProjectList({ page_size: 9999 })
    projects.value = res.data?.results || res.results || res.data || []
  } catch (error) {
    console.error('加载项目失败:', error)
  }
}

const loadItems = async () => {
  try {
    const res = await getItemList({ page_size: 9999 })
    items.value = res.data?.results || res.results || res.data || []
  } catch (error) {
    console.error('加载物料失败:', error)
  }
}

// 加载项目中未申请的物料
const loadProjectItems = async (projectId) => {
  if (!projectId) {
    projectItems.value = []
    return
  }
  
  try {
    const res = await getBOMList({ 
      project: projectId, 
      is_deleted: false,
      order_status: 'NOT_ORDERED',
      page_size: 9999
    })
    const bomItems = res.data?.results || res.results || res.data || res || []
    // 从BOM中提取物料信息
    projectItems.value = bomItems.map(bom => ({
      id: bom.item,
      sku: bom.item_sku || bom.item_code || '',
      name: bom.item_name || '',
      specification: bom.specification || bom.item_specification || '',
      item_model: bom.item_model || '',
      drawing_no: bom.drawing_no || '',
      item_type_display: bom.item_type || '',
      planned_qty: bom.planned_qty,
      bom_id: bom.id
    })).filter(item => item.id)  // 过滤掉没有item的
  } catch (error) {
    console.error('加载项目物料失败:', error)
    projectItems.value = []
  }
}

// 可选物料：如果选了项目则显示项目未申请物料，否则显示所有物料
const availableItems = computed(() => {
  if (form.project && projectItems.value.length > 0) {
    return projectItems.value
  }
  return items.value
})

// 记录上一次选中的项目，避免重复选择同项目时清空物料
let lastSelectedProject = null

// 项目变化时重新加载可选物料
const onProjectChange = async (projectId) => {
  // 如果项目没有真正变化，只刷新物料列表不清空已选
  if (projectId === lastSelectedProject) {
    await loadProjectItems(projectId)
    return
  }
  lastSelectedProject = projectId
  await loadProjectItems(projectId)
  // 清空已选的物料（因为可能不在新项目的BOM中）
  form.lines.forEach(line => {
    line.item = null
    line.estimated_price = 0
  })
}

const loadSuppliers = async () => {
  try {
    const res = await getSupplierList({ page_size: 9999 })
    suppliers.value = res.data?.results || res.results || res.data || []
  } catch (error) {
    console.error('加载供应商失败:', error)
  }
}

const resetSearch = () => {
  searchForm.project = null
  searchForm.status = null
  pagination.page = 1
  loadRequests()
}

// 获取过滤提示文本
const getFilterTip = () => {
  const tips = []
  if (searchForm.project) {
    const proj = projects.value.find(p => p.id === searchForm.project)
    if (proj) {
      tips.push(`项目: ${proj.name}`)
    }
  }
  if (searchForm.status) {
    const statusMap = {
      DRAFT: '草稿',
      SUBMITTED: '已提交',
      APPROVED: '已批准',
      REJECTED: '已拒绝',
      CONVERTED: '已转订单'
    }
    tips.push(`状态: ${statusMap[searchForm.status]}`)
  }
  return `当前过滤条件：${tips.join(' | ')} （共 ${pagination.total} 条记录）`
}

const handleAdd = () => {
  dialogTitle.value = '创建采购申请'
  isEdit.value = false
  lastSelectedProject = null
  projectItems.value = []
  Object.assign(form, {
    id: null,
    project: null,
    supplier: null,
    required_date: '',
    tax_rate: 13,
    notes: '',
    lines: [{ item: null, qty: 1, estimated_price: 0, required_date: '', notes: '' }]
  })
  dialogVisible.value = true
}

const handleEdit = async (row) => {
  dialogTitle.value = '编辑采购申请'
  isEdit.value = true
  lastSelectedProject = null
  projectItems.value = []
  
  try {
    // 获取详情包括明细
    const res = await getPurchaseRequest(row.id)
    const data = res.data || res
    
    Object.assign(form, {
      id: data.id,
      project: data.project,
      supplier: data.supplier,
      required_date: data.required_date || '',
      tax_rate: data.tax_rate ?? 13,
      notes: data.notes || '',
      lines: (data.lines || []).map(line => ({
        id: line.id,
        item: line.item,
        qty: line.qty,
        estimated_price: parseFloat(line.estimated_price || 0),
        required_date: line.required_date || '',
        notes: line.notes || ''
      }))
    })
    
    if (form.lines.length === 0) {
      form.lines = [{ item: null, qty: 1, estimated_price: 0, required_date: '', notes: '' }]
    }
    
    // 如果有项目，加载项目BOM物料
    if (data.project) {
      lastSelectedProject = data.project
      await loadProjectItems(data.project)
    }
    
    dialogVisible.value = true
  } catch (error) {
    ElMessage.error('获取采购申请详情失败')
  }
}

const handleView = async (row) => {
  try {
    const res = await getPurchaseRequest(row.id)
    currentRequest.value = res.data || res
    viewDialogVisible.value = true
  } catch (error) {
    ElMessage.error('获取采购申请详情失败')
  }
}

const addLine = () => {
  form.lines.push({ item: null, qty: 1, estimated_price: 0, required_date: '', notes: '' })
}

const removeLine = (index) => {
  if (form.lines.length > 1) {
    form.lines.splice(index, 1)
  } else {
    ElMessage.warning('至少保留一行明细')
  }
}

const onItemChange = (index) => {
  const line = form.lines[index]
  const item = items.value.find(i => i.id === line.item)
  if (item) {
    line.estimated_price = parseFloat(item.purchase_price || item.standard_cost || 0)
  }
}

// 获取物料单位
const getItemUnit = (itemId) => {
  if (!itemId) return '-'
  const item = items.value.find(i => i.id === itemId)
  return item?.unit_display || item?.unit || '-'
}

// 查找物料信息（优先从availableItems中获取，其次从items中获取）
const findItemInfo = (itemId) => {
  if (!itemId) return null
  return availableItems.value.find(i => i.id === itemId) || items.value.find(i => i.id === itemId)
}

// 获取物料名称
const getItemName = (itemId) => {
  const item = findItemInfo(itemId)
  return item?.name || '-'
}

// 获取物料型号/图号
const getItemModel = (itemId) => {
  const item = findItemInfo(itemId)
  return item?.item_model || item?.model || item?.drawing_no || '-'
}

// 获取物料类型
const getItemType = (itemId) => {
  const item = findItemInfo(itemId)
  return item?.item_type_display || item?.category_name || '-'
}

// 计算行金额（不含税）
const getLineAmount = (row) => {
  return (row.qty || 0) * (row.estimated_price || 0)
}

// 计算行税额
const getLineTax = (row) => {
  return getLineAmount(row) * (form.tax_rate || 0) / 100
}

// 计算行含税价
const getLineTotalWithTax = (row) => {
  return getLineAmount(row) + getLineTax(row)
}

const calculateTotal = () => {
  return form.lines.reduce((sum, line) => {
    return sum + getLineAmount(line)
  }, 0)
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
    
    // 验证明细
    const validLines = form.lines.filter(line => line.item && line.qty > 0)
    if (validLines.length === 0) {
      ElMessage.warning('请至少添加一行有效的物料明细')
      return
    }
    
    saving.value = true
    
    const payload = {
      project: form.project,
      supplier: form.supplier,
      required_date: form.required_date,
      tax_rate: form.tax_rate,
      notes: form.notes,
      lines: validLines.map(line => ({
        item: line.item,
        qty: line.qty,
        estimated_price: line.estimated_price,
        required_date: line.required_date || null,
        notes: line.notes || ''
      }))
    }
    
    if (isEdit.value) {
      await updatePurchaseRequest(form.id, payload)
      ElMessage.success('更新采购申请成功')
    } else {
      await createPurchaseRequest(payload)
      ElMessage.success('创建采购申请成功')
      // 刷新物料需求清单（已采购的物料会被过滤掉）
      loadBomItems()
    }
    
    dialogVisible.value = false
    loadRequests()
  } catch (error) {
    console.error('保存失败详情:', error.response?.data || error)
    const errData = error.response?.data
    let errMsg = '保存采购申请失败'
    if (errData) {
      if (errData.required_date) errMsg = '请选择需求日期'
      else if (errData.detail) errMsg = errData.detail
      else if (typeof errData === 'object') errMsg = JSON.stringify(errData)
    }
    ElMessage.error(errMsg)
  } finally {
    saving.value = false
  }
}

const handleSubmit = async (row) => {
  try {
    await ElMessageBox.confirm('确定要提交该采购申请吗？提交后将进入审批流程。', '提交确认', { type: 'warning' })
    await submitPurchaseRequest(row.id)
    ElMessage.success('提交成功')
    loadRequests()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('提交失败')
    }
  }
}

const handleApprove = async (row) => {
  try {
    await ElMessageBox.confirm('确定要批准该采购申请吗？', '批准确认', { type: 'warning' })
    
    // 统一通过后端 approve 接口处理（后端自动检测并处理工作流）
    await approvePurchaseRequest(row.id)
    ElMessage.success('批准成功')
    loadRequests()
  } catch (error) {
    if (error !== 'cancel') {
      const msg = error.response?.data?.error || error.response?.data?.detail || error.message || '批准失败'
      console.error('审批失败:', msg, error)
      ElMessage.error(msg)
    }
  }
}

const handleReject = async (row) => {
  try {
    const { value: comment } = await ElMessageBox.prompt('请输入拒绝原因', '拒绝确认', {
      type: 'warning',
      inputType: 'textarea',
      inputPlaceholder: '请输入拒绝原因（必填）',
      inputValidator: (val) => val && val.trim() ? true : '请填写拒绝原因',
      confirmButtonText: '确认拒绝',
      cancelButtonText: '取消'
    })
    
    // 统一通过后端 reject 接口处理（后端自动检测并处理工作流）
    await rejectPurchaseRequest(row.id, { comment })
    ElMessage.success('已拒绝')
    loadRequests()
  } catch (error) {
    if (error !== 'cancel') {
      const msg = error.response?.data?.error || error.response?.data?.detail || error.message || '操作失败'
      console.error('拒绝失败:', msg, error)
      ElMessage.error(msg)
    }
  }
}

const handleWithdraw = async (row) => {
  try {
    await ElMessageBox.confirm('确定要撤回该采购申请吗？撤回后将恢复为草稿状态。', '撤回确认', { type: 'warning' })
    await withdrawPurchaseRequest(row.id)
    ElMessage.success('已撤回')
    loadRequests()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error(error.response?.data?.error || '撤回失败')
    }
  }
}

const convertToPO = (row) => {
  currentConvertId.value = row.id
  // 预填充采购申请中的供应商
  convertForm.supplier = row.supplier || null
  convertDialogVisible.value = true
}

const doConvertToPO = async () => {
  if (!convertForm.supplier) {
    ElMessage.warning('请选择供应商')
    return
  }
  
  converting.value = true
  try {
    await convertRequestToPO(currentConvertId.value, {
      supplier: convertForm.supplier
    })
    ElMessage.success('成功转换为采购订单')
    convertDialogVisible.value = false
    loadRequests()
  } catch (error) {
    ElMessage.error('转换为采购订单失败')
  } finally {
    converting.value = false
  }
}

// 处理从BOM页面传递过来的数据
const handleBomData = async () => {
  if (route.query.from_bom === '1') {
    const bomData = sessionStorage.getItem('bom_to_pr')
    if (bomData) {
      try {
        const data = JSON.parse(bomData)
        sessionStorage.removeItem('bom_to_pr') // 清除已使用的数据
        
        // 预填充表单
        dialogTitle.value = '创建采购申请（来自BOM）'
        isEdit.value = false
        // 先加载项目BOM物料列表，确保物料下拉框有数据
        await loadProjectItems(data.project)
        lastSelectedProject = data.project
        
        // 确保BOM传递过来的物料在下拉列表中（即使状态已变更不再是NOT_ORDERED）
        const existingItemIds = new Set(projectItems.value.map(i => i.id))
        data.lines.forEach(line => {
          if (line.item && !existingItemIds.has(line.item)) {
            projectItems.value.push({
              id: line.item,
              sku: line.item_sku || '',
              name: line.item_name || '',
              specification: '',
              item_model: '',
              drawing_no: '',
              item_type_display: ''
            })
          }
        })
        
        Object.assign(form, {
          id: null,
          project: data.project,
          required_date: new Date(Date.now() + 7 * 24 * 60 * 60 * 1000).toISOString().split('T')[0], // 默认7天后
          tax_rate: 13,
          notes: `根据项目 ${data.projectName} 的BOM清单生成`,
          lines: data.lines.map(line => ({
            item: line.item,
            qty: line.qty,
            estimated_price: line.estimated_price || 0
          }))
        })
        dialogVisible.value = true
        
        ElMessage.success(`已导入 ${data.lines.length} 种物料，请确认后保存`)
      } catch (e) {
        console.error('解析BOM数据失败:', e)
      }
    }
  }
}

// handleDelete 已被 useBatchDelete 的 deleteRow 替代

// ========== BOM物料筛选和导出功能 ==========
const loadBomItems = async () => {
  if (!bomProject.value) {
    bomItems.value = []
    return
  }
  
  bomLoading.value = true
  try {
    const res = await getBOMList({
        project: bomProject.value, 
        is_deleted: false,
        order_status: 'NOT_ORDERED',  // 只加载未采购的物料
        page_size: 9999
    })
    const items = res.data?.results || res.results || res.data || res || []
    bomItems.value = items.map(item => ({
      ...item,
      item_code: item.item_code || item.item?.sku || item.item_sku || '',
      item_name: item.item_name || item.item?.name || '',
      specification: item.specification || item.item?.specification || item.item_specification || '',
      unit: item.unit || item.item?.unit_display || item.item_unit || '',
      has_drawing_display: item.has_drawing_display || (item.has_drawing === 'HAS_DRAWING' ? '有图' : item.has_drawing === 'NO_DRAWING' ? '无图' : '待定'),
      item_type_display: item.item_type_display || item.item?.item_type_display || item.item_type || '',
      version_brand: item.version_brand_display || item.version_brand || ''
    }))
  } catch (error) {
    console.error('加载BOM物料失败:', error)
    bomItems.value = []
    ElMessage.error('加载BOM物料失败')
  } finally {
    bomLoading.value = false
  }
}

const resetBomFilters = () => {
  bomFilter.hasDrawing = ''
  bomFilter.itemType = ''
  bomFilter.brand = ''
  bomFilter.keyword = ''
  selectedBomRows.value = []
  if (bomTableRef.value) {
    bomTableRef.value.clearSelection()
  }
}

const handleBomSelectionChange = (rows) => {
  selectedBomRows.value = rows
}

const handleExportBomForQuote = async () => {
  if (filteredBomItems.value.length === 0) {
    ElMessage.warning('没有可导出的数据')
    return
  }
  
  const bomIds = filteredBomItems.value.map(item => item.id)
  await exportBomForQuote(bomIds, '筛选结果')
}

const handleExportSelectedBom = async () => {
  if (selectedBomRows.value.length === 0) {
    ElMessage.warning('请先选择要导出的物料')
    return
  }
  
  const bomIds = selectedBomRows.value.map(item => item.id)
  await exportBomForQuote(bomIds, '选中项')
}

const exportBomForQuote = async (bomIds, exportName) => {
  try {
    const response = await exportBOMForQuote({
      project: bomProject.value,
      bom_ids: bomIds
    }, {
      responseType: 'blob'
    })
    
    const blobData = response.data || response
    const blob = new Blob([blobData], { 
      type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' 
    })
    
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    const project = projects.value.find(p => p.id === bomProject.value)
    const projectCode = project?.code || bomProject.value
    link.setAttribute('download', `物料需求清单_${projectCode}_${exportName}.xlsx`)
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(url)
    
    ElMessage.success(`导出${exportName}成功，共${bomIds.length}项物料`)
  } catch (error) {
    console.error('导出失败:', error)
    ElMessage.error('导出失败: ' + (error.response?.data?.error || '未知错误'))
  }
}

// ========== 导入功能 ==========
const handleImport = () => {
  importFile.value = null
  importFileList.value = []
  importResult.value = null
  importError.value = null
  // 如果已选择BOM项目，自动填充
  importProject.value = bomProject.value || null
  if (importUploadRef.value) {
    importUploadRef.value.clearFiles()
  }
  importDialogVisible.value = true
}

const handleImportFileChange = (file) => {
  importFile.value = file.raw
  importResult.value = null
  importError.value = null
}

const handleImportExceed = () => {
  ElMessage.warning('只能上传一个文件，请先删除已选文件')
}

const handleConfirmImport = async () => {
  if (!importFile.value) {
    ElMessage.warning('请选择要导入的文件')
    return
  }
  
  importing.value = true
  importError.value = null
  importResult.value = null
  
  try {
    const formData = new FormData()
    formData.append('file', importFile.value)
    // 传递选择的项目ID
    if (importProject.value) {
      formData.append('project', importProject.value)
    }
    
    const response = await importPurchaseRequests(formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })
    
    const data = response.data || response
    importResult.value = {
      success: data.created_count > 0,
      message: data.message,
      purchase_requests: data.purchase_requests || [],
      errors: data.errors || []
    }
    
    if (data.created_count > 0) {
      ElMessage.success(data.message)
      loadRequests()
      // 刷新物料需求清单（已采购的物料会被过滤掉）
      loadBomItems()
    }
  } catch (error) {
    console.error('导入失败:', error)
    const errData = error.response?.data
    
    // 检查是否是项目号不匹配错误
    if (errData?.excel_projects || errData?.details) {
      importError.value = {
        type: 'project_mismatch',
        title: errData.error || '项目号不匹配',
        selectedProject: errData.selected_project || '未选择',
        excelProjects: errData.excel_projects?.join(', ') || '无',
        details: errData.details || [],
        suggestion: errData.suggestion || '请选择正确的项目后重新导入'
      }
    } else {
      importResult.value = {
        success: false,
        message: errData?.error || '导入失败',
        errors: errData?.errors || []
      }
      ElMessage.error(errData?.error || '导入失败')
    }
  } finally {
    importing.value = false
  }
}

const handleDownloadTemplate = async () => {
  try {
    const response = await exportPurchaseRequestTemplate({
      responseType: 'blob'
    })
    
    const blobData = response.data || response
    const blob = new Blob([blobData], { 
      type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' 
    })
    
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.setAttribute('download', '采购申请导入模板.xlsx')
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(url)
    
    ElMessage.success('模板下载成功')
  } catch (error) {
    console.error('下载模板失败:', error)
    ElMessage.error('下载模板失败')
  }
}

onMounted(async () => {
  // 首先加载项目和其他数据
  await Promise.all([
    loadProjects(),
    loadItems(),
    loadSuppliers()
  ])
  
  // 检查URL参数中是否有项目过滤
  if (route.query.project) {
    const projectId = parseInt(route.query.project)
    if (!isNaN(projectId)) {
      searchForm.project = projectId
    }
  }
  
  // 加载采购申请列表
  loadRequests()
  
  // 处理BOM数据（其他数据已在上面的Promise.all中加载完成）
  await handleBomData()
})
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

.table-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 15px;
  background-color: #f5f7fa;
  border-radius: 4px;
  margin-bottom: 10px;
  border: 1px solid #e4e7ed;
}

.table-toolbar span {
  font-size: 14px;
  color: #606266;
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
</style>
