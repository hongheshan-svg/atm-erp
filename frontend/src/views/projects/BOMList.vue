<template>
  <div class="bom-list">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>项目BOM清单</span>
          <div class="header-actions">
            <el-select v-model="selectedProject" placeholder="选择项目" clearable filterable style="width: 250px; margin-right: 10px;">
              <el-option
                v-for="project in projects"
                :key="project.id"
                :label="project.name"
                :value="project.id"
              />
            </el-select>
            <el-button type="primary" v-permission="'projects:project:create'" @click="handleAdd" :disabled="!selectedProject">
              <el-icon><Plus /></el-icon>
              添加物料
            </el-button>
            <el-dropdown style="margin-left: 10px;" :disabled="!selectedProject">
              <el-button type="success">
                导入/导出 <el-icon class="el-icon--right"><ArrowDown /></el-icon>
              </el-button>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item @click="handleExportExcel" :disabled="!bomItems.length">
                    <el-icon><Download /></el-icon> 导出Excel
                  </el-dropdown-item>
                  <el-dropdown-item @click="handleImport">
                    <el-icon><Upload /></el-icon> 导入Excel
                  </el-dropdown-item>
                  <el-dropdown-item divided @click="handleDownloadTemplate">
                    <el-icon><Document /></el-icon> 下载导入模板
                  </el-dropdown-item>
                  <el-dropdown-item divided @click="handleCopyFromProject">
                    <el-icon><CopyDocument /></el-icon> 从其他项目复制
                  </el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
            <el-button type="warning" @click="handleGeneratePR" :disabled="!selectedProject || !bomItems.length" style="margin-left: 10px;">
              <el-icon><Document /></el-icon>
              生成采购申请
            </el-button>
            <el-button type="info" @click="handleMaterialCheck" :disabled="!selectedProject || !bomItems.length" style="margin-left: 10px;">
              <el-icon><Checked /></el-icon>
              齐套检查
            </el-button>
          </div>
        </div>
      </template>
      
      <!-- BOM统计 -->
      <el-row :gutter="20" class="stats-row" v-if="bomItems.length > 0">
        <el-col :span="4">
          <el-statistic title="物料种类" :value="bomItems.length" suffix="种" />
        </el-col>
        <el-col :span="4">
          <el-statistic title="计划总量" :value="totalPlannedQty" />
        </el-col>
        <el-col :span="4">
          <el-statistic title="已领用" :value="totalActualQty" />
        </el-col>
        <el-col :span="4">
          <el-statistic title="预估成本" :value="totalEstimatedCost" :precision="2" prefix="¥" />
        </el-col>
        <el-col :span="4">
          <el-statistic title="待询价" :value="pendingQuoteCount" suffix="项" />
        </el-col>
        <el-col :span="4">
          <el-statistic title="已询价" :value="bomItems.length - pendingQuoteCount" suffix="项" />
        </el-col>
      </el-row>
      
      <!-- 筛选和搜索栏 -->
      <div class="filter-bar" v-if="pagination.total > 0 || selectedProject">
        <el-row :gutter="15" style="margin-bottom: 15px;">
          <el-col :span="4">
            <el-select v-model="filterHasDrawing" placeholder="有图/无图" clearable style="width: 100%;" @change="applyFilters">
              <el-option label="全部" value="" />
              <el-option label="有图" value="HAS_DRAWING" />
              <el-option label="无图" value="NO_DRAWING" />
              <el-option label="待定" value="PENDING" />
            </el-select>
          </el-col>
          <el-col :span="5">
            <el-select v-model="filterItemType" placeholder="物料类型" clearable style="width: 100%;" @change="applyFilters">
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
            <el-input 
              v-model="filterBrand" 
              placeholder="版本/品牌筛选" 
              clearable
              @clear="applyFilters"
              @keyup.enter="applyFilters"
            />
          </el-col>
          <el-col :span="6">
        <el-input 
          v-model="searchKeyword" 
          placeholder="搜索物料编码/名称/规格" 
          clearable 
          @clear="applyFilters"
          @keyup.enter="applyFilters"
        >
          <template #prefix>
            <el-icon><Search /></el-icon>
          </template>
        </el-input>
          </el-col>
          <el-col :span="4">
            <el-button type="primary" @click="applyFilters" style="margin-right: 5px;">
              <el-icon><Search /></el-icon>
              查询
            </el-button>
            <el-button @click="resetFilters">
              <el-icon><Refresh /></el-icon>
              重置
            </el-button>
          </el-col>
        </el-row>
        
        <!-- 筛选结果提示和操作 -->
        <div class="filter-actions">
          <span class="filter-result">
            共 <el-tag type="info">{{ pagination.total }}</el-tag> 项
          </span>
          <el-button 
            type="success" 
            size="small" 
            @click="handleExportFiltered" 
            :disabled="bomItems.length === 0"
            style="margin-left: 15px;"
          >
            <el-icon><Download /></el-icon>
            导出筛选结果(询价用)
          </el-button>
          <span v-if="selectedRows.length > 0" class="selection-info" style="margin-left: 15px;">
          已选择 <el-tag type="primary" size="small">{{ selectedRows.length }}</el-tag> 项
            <el-button type="success" size="small" @click="handleExportSelected" style="margin-left: 10px;">
              <el-icon><Download /></el-icon>
              导出选中(询价用)
            </el-button>
            <el-button type="warning" size="small" @click="handleGeneratePRFromSelected" style="margin-left: 5px;">
            <el-icon><Document /></el-icon>
              生成采购申请
          </el-button>
          <el-button type="danger" size="small" v-permission="'projects:project:delete'" @click="handleBatchDelete" style="margin-left: 5px;">
            <el-icon><Delete /></el-icon>
            批量删除
          </el-button>
          <el-button size="small" @click="clearSelection" style="margin-left: 5px;">
            取消选择
          </el-button>
        </span>
        </div>
      </div>
      
      <!-- BOM列表 -->
      <el-table 
        :data="bomItems" 
        border 
        stripe 
        v-loading="loading"
        ref="tableRef"
        @selection-change="handleSelectionChange"
      >
        <el-table-column type="selection" width="50" />
        <el-table-column type="index" label="序号" width="60" :index="(index) => (pagination.page - 1) * pagination.pageSize + index + 1" />
        <el-table-column prop="project_name" label="所属项目" width="150" show-overflow-tooltip v-if="!selectedProject" />
        <el-table-column prop="item_sku" label="物料编码" width="120" />
        <el-table-column prop="item_name" label="物料名称" width="150" />
        <el-table-column prop="specification" label="规格型号" width="120" show-overflow-tooltip />
        <el-table-column prop="version_brand_display" label="版本/品牌" width="100" show-overflow-tooltip />
        <el-table-column prop="unit" label="单位" width="60" />
        <el-table-column prop="item_type" label="物料类型" width="80" />
        <el-table-column prop="planned_qty" label="计划数量" width="90" align="right" />
        <el-table-column prop="order_status_display" label="采购状态" width="100" align="center">
          <template #default="{ row }">
            <el-tag 
              :type="getOrderStatusType(row.order_status)" 
              size="small"
            >
              {{ row.order_status_display || '未下单' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="ordered_qty" label="已下单" width="80" align="right">
          <template #default="{ row }">
            {{ row.ordered_qty || 0 }}
          </template>
        </el-table-column>
        <el-table-column prop="supplier_name" label="供应商" width="120" show-overflow-tooltip />
        <el-table-column prop="delivery_date" label="交期" width="100" />
        <el-table-column prop="received_qty" label="已入库" width="80" align="right">
          <template #default="{ row }">
            <span :class="row.received_qty >= row.ordered_qty && row.ordered_qty > 0 ? 'text-success' : ''">
              {{ row.received_qty || 0 }}
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="issued_qty" label="已出库" width="80" align="right">
          <template #default="{ row }">
            {{ row.issued_qty || 0 }}
          </template>
        </el-table-column>
        <el-table-column label="剩余需求" width="80" align="right">
          <template #default="{ row }">
            {{ Math.max(0, (row.planned_qty || 0) - (row.issued_qty || 0)) }}
          </template>
        </el-table-column>
        <el-table-column prop="estimated_cost" label="预估单价" width="90" align="right">
          <template #default="{ row }">
            ¥{{ row.estimated_cost || 0 }}
          </template>
        </el-table-column>
        <el-table-column label="预估成本" width="100" align="right">
          <template #default="{ row }">
            ¥{{ ((row.planned_qty || 0) * (row.estimated_cost || 0)).toFixed(2) }}
          </template>
        </el-table-column>
        <el-table-column prop="has_drawing_display" label="有图/无图" width="80" />
        <el-table-column prop="required_date" label="需求日期" width="100" />
        <el-table-column prop="requester_name" label="申请人" width="80" />
        <el-table-column label="操作" width="120" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link size="small" v-permission="'projects:project:edit'" @click="handleEdit(row)">编辑</el-button>
            <el-button type="danger" link size="small" v-permission="'projects:project:delete'" @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      
      <!-- 分页 -->
      <el-pagination
        v-model:current-page="pagination.page"
        v-model:page-size="pagination.pageSize"
        :total="pagination.total"
        :page-sizes="[20, 50, 100, 200, 500]"
        layout="total, sizes, prev, pager, next, jumper"
        @size-change="handleSizeChange"
        @current-change="handlePageChange"
        style="margin-top: 20px; justify-content: flex-end;"
      />
    </el-card>
    
    <!-- 添加/编辑物料对话框 -->
    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="800px">
      <el-form :model="form" :rules="rules" ref="formRef" label-width="100px">
        <el-form-item label="所属项目">
          <el-input :value="currentProjectName" disabled>
            <template #prefix>
              <el-icon><Folder /></el-icon>
            </template>
          </el-input>
        </el-form-item>
        <el-form-item label="选择物料" prop="item" v-if="!form.id">
          <el-select v-model="form.item" placeholder="选择物料" filterable style="width: 100%;" @change="handleItemChange">
            <el-option
              v-for="item in items"
              :key="item.id"
              :label="`${item.sku} - ${item.name}`"
              :value="item.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="物料" v-else>
          <el-input :value="`${form.item_code} - ${form.item_name}`" disabled />
        </el-form-item>
        <el-row :gutter="20">
          <el-col :span="8">
            <el-form-item label="规格型号">
              <el-input v-model="form.specification" disabled />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="单位">
              <el-input v-model="form.unit" disabled />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="物料类型">
              <el-input v-model="form.item_type" disabled />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="8">
            <el-form-item label="计划数量" prop="planned_qty">
              <el-input-number v-model="form.planned_qty" :min="1" :max="999999" style="width: 100%;" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="预估单价">
              <el-input-number v-model="form.estimated_cost" :min="0" :precision="2" style="width: 100%;" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="版本/品牌">
              <el-input v-model="form.version_brand" placeholder="版本号或品牌" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="8">
            <el-form-item label="有图/无图">
              <el-select v-model="form.has_drawing" style="width: 100%;">
                <el-option label="有图" value="YES" />
                <el-option label="无图" value="NO" />
                <el-option label="待定" value="PENDING" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="需求日期">
              <el-date-picker 
                v-model="form.required_date" 
                type="date" 
                placeholder="选择日期"
                format="YYYY-MM-DD"
                value-format="YYYY-MM-DD"
                style="width: 100%;"
              />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="申请人">
              <el-select v-model="form.requester" placeholder="选择申请人" filterable clearable style="width: 100%;">
                <el-option
                  v-for="user in users"
                  :key="user.id"
                  :label="user.name"
                  :value="user.id"
                />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        
        <!-- 采购与库存信息 -->
        <el-divider content-position="left">采购与库存信息</el-divider>
        <el-row :gutter="20">
          <el-col :span="8">
            <el-form-item label="供应商">
              <el-select v-model="form.supplier" placeholder="选择供应商" filterable clearable style="width: 100%;">
                <el-option
                  v-for="s in suppliers"
                  :key="s.id"
                  :label="s.name"
                  :value="s.id"
                />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="交期">
              <el-date-picker 
                v-model="form.delivery_date" 
                type="date" 
                placeholder="选择交期"
                format="YYYY-MM-DD"
                value-format="YYYY-MM-DD"
                style="width: 100%;"
              />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="采购状态">
              <el-select v-model="form.order_status" style="width: 100%;" disabled>
                <el-option label="未下单" value="NOT_ORDERED" />
                <el-option label="采购申请中" value="PR_PENDING" />
                <el-option label="申请已批准" value="PR_APPROVED" />
                <el-option label="部分下单" value="PARTIAL" />
                <el-option label="已下单" value="ORDERED" />
                <el-option label="在途" value="IN_TRANSIT" />
                <el-option label="部分收货" value="PARTIAL_RECEIVED" />
                <el-option label="已收货" value="RECEIVED" />
                <el-option label="已退货" value="RETURNED" />
                <el-option label="已取消" value="CANCELLED" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="6">
            <el-form-item label="已下单数量">
              <el-input-number v-model="form.ordered_qty" :min="0" :precision="2" style="width: 100%;" />
            </el-form-item>
          </el-col>
          <el-col :span="6">
            <el-form-item label="已入库数量">
              <el-input-number v-model="form.received_qty" :min="0" :precision="2" style="width: 100%;" />
            </el-form-item>
          </el-col>
          <el-col :span="6">
            <el-form-item label="已出库数量">
              <el-input-number v-model="form.issued_qty" :min="0" :precision="2" style="width: 100%;" />
            </el-form-item>
          </el-col>
        </el-row>
        
        <el-form-item label="备注">
          <el-input v-model="form.notes" type="textarea" :rows="2" placeholder="备注信息" />
        </el-form-item>
        <el-form-item label="说明">
          <el-input v-model="form.description" type="textarea" :rows="2" placeholder="详细说明" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSubmit">确定</el-button>
      </template>
    </el-dialog>
    
    <!-- 导入BOM对话框 -->
    <el-dialog v-model="importDialogVisible" title="导入BOM" width="550px">
      <el-alert
        title="导入说明"
        type="info"
        show-icon
        :closable="false"
        class="mb-15"
      >
        <template #default>
          <div>1. 请先下载导入模板，按模板格式填写数据</div>
          <div>2. 物料编码必须与系统中的物料编码一致</div>
          <div>3. 计划数量为必填项，单价可选</div>
        </template>
      </el-alert>
      
      <el-upload
        ref="uploadRef"
        class="upload-area"
        drag
        action="#"
        :auto-upload="false"
        :limit="1"
        :on-change="handleFileChange"
        :on-exceed="handleExceed"
        accept=".xlsx,.xls"
      >
        <el-icon class="el-icon--upload"><UploadFilled /></el-icon>
        <div class="el-upload__text">
          将Excel文件拖到此处，或 <em>点击上传</em>
        </div>
        <template #tip>
          <div class="el-upload__tip">只支持 .xlsx 或 .xls 格式文件</div>
        </template>
      </el-upload>
      
      <div style="margin-top: 15px;">
        <el-checkbox v-model="importOptions.updateExisting">
          更新已存在的BOM（不勾选则跳过已存在的）
        </el-checkbox>
      </div>
      <div style="margin-top: 10px;">
        <el-checkbox v-model="importOptions.autoCreateItems">
          自动创建不存在的物料（勾选后，若物料编码不存在则自动在物料主数据中创建）
        </el-checkbox>
      </div>
      
      <!-- 导入结果 -->
      <div v-if="importResult" class="import-result">
        <el-divider content-position="left">导入结果</el-divider>
        
        <!-- 成功结果 -->
        <el-descriptions v-if="importResult.created !== undefined || importResult.updated !== undefined" :column="2" border size="small">
          <el-descriptions-item label="新增BOM">
            <el-tag type="success">{{ importResult.created || 0 }} 条</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="更新BOM">
            <el-tag type="primary">{{ importResult.updated || 0 }} 条</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="自动创建物料" v-if="importResult.items_created">
            <el-tag type="warning">{{ importResult.items_created }} 个</el-tag>
          </el-descriptions-item>
        </el-descriptions>
        
        <!-- 错误信息 -->
        <div v-if="importResult.error" class="error-summary" style="margin: 10px 0;">
          <el-alert :title="importResult.error" type="error" show-icon :closable="false" />
        </div>
        
        <!-- 详细错误列表 -->
        <div v-if="importResult.errors && importResult.errors.length > 0" class="error-list" style="margin-top: 10px; max-height: 200px; overflow-y: auto;">
          <el-alert title="详细错误" type="warning" show-icon :closable="false">
            <template #default>
              <div v-for="error in importResult.errors" :key="error.row" class="error-item">
                第 {{ error.row }} 行: {{ error.error }}
              </div>
            </template>
          </el-alert>
        </div>
        
        <!-- 必需列提示 -->
        <div v-if="importResult.required_columns" style="margin-top: 10px;">
          <el-alert type="info" show-icon :closable="false">
            <template #title>必需列: {{ importResult.required_columns.join(', ') }}</template>
          </el-alert>
        </div>
      </div>
      
      <template #footer>
        <el-button @click="handleDownloadTemplate">下载模板</el-button>
        <el-button @click="importDialogVisible = false">关闭</el-button>
        <el-button type="primary" @click="handleConfirmImport" :loading="importing" :disabled="!importFile">
          开始导入
        </el-button>
      </template>
    </el-dialog>
    
    <!-- 导入已报价BOM对话框 -->
    <el-dialog v-model="quoteImportDialogVisible" title="导入已报价BOM" width="550px">
      <el-alert
        title="导入说明"
        type="warning"
        show-icon
        :closable="false"
        class="mb-15"
      >
        <template #default>
          <div>1. 请先导出询价BOM清单，将报价信息填写完整后再导入</div>
          <div>2. 物料编码必须与项目BOM清单中的物料编码一致</div>
          <div>3. 含税单价或未税单价至少填写一项</div>
          <div>4. 导入成功后，物料将标记为"已询价"状态</div>
        </template>
      </el-alert>
      
      <el-upload
        ref="quoteUploadRef"
        class="upload-area"
        drag
        action="#"
        :auto-upload="false"
        :limit="1"
        :on-change="handleQuoteFileChange"
        :on-exceed="handleExceed"
        accept=".xlsx,.xls"
      >
        <el-icon class="el-icon--upload"><UploadFilled /></el-icon>
        <div class="el-upload__text">
          将已报价的Excel文件拖到此处，或 <em>点击上传</em>
        </div>
        <template #tip>
          <div class="el-upload__tip">只支持 .xlsx 或 .xls 格式文件</div>
        </template>
      </el-upload>
      
      <template #footer>
        <el-button @click="handleExportQuoteBOM">导出询价BOM</el-button>
        <el-button @click="quoteImportDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleConfirmQuoteImport" :loading="quoteImporting" :disabled="!quoteImportFile">
          开始导入
        </el-button>
      </template>
    </el-dialog>
    
    <!-- 从其他项目复制对话框 -->
    <el-dialog v-model="copyDialogVisible" title="从其他项目复制BOM" width="450px">
      <el-form label-width="100px">
        <el-form-item label="源项目">
          <el-select v-model="copySourceProject" placeholder="选择源项目" filterable style="width: 100%;">
            <el-option
              v-for="project in projects.filter(p => p.id !== selectedProject)"
              :key="project.id"
              :label="`${project.code} - ${project.name}`"
              :value="project.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="目标项目">
          <el-input :value="currentProjectName" disabled />
        </el-form-item>
      </el-form>
      <el-alert
        title="提示：已存在的物料将被跳过，不会覆盖"
        type="info"
        show-icon
        :closable="false"
      />
      <template #footer>
        <el-button @click="copyDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleConfirmCopy" :loading="copying" :disabled="!copySourceProject">
          确定复制
        </el-button>
      </template>
    </el-dialog>

    <!-- 齐套检查对话框 -->
    <el-dialog v-model="materialCheckDialogVisible" title="物料齐套检查" width="1000px">
      <div v-loading="materialCheckLoading">
        <!-- 汇总信息 -->
        <el-row :gutter="20" class="stats-row" v-if="materialCheckData.summary">
          <el-col :span="4">
            <el-statistic title="物料总数" :value="materialCheckData.summary.total_items" suffix="种" />
          </el-col>
          <el-col :span="4">
            <el-statistic title="已齐套" :value="materialCheckData.summary.complete_items" suffix="种" />
          </el-col>
          <el-col :span="4">
            <el-statistic title="缺料项">
              <template #value>
                <span :class="materialCheckData.summary.shortage_items > 0 ? 'text-danger' : ''">
                  {{ materialCheckData.summary.shortage_items }}
                </span>
              </template>
            </el-statistic>
          </el-col>
          <el-col :span="4">
            <el-statistic title="齐套率">
              <template #value>
                <span :class="materialCheckData.summary.completion_rate < 100 ? 'text-warning' : 'text-success'">
                  {{ materialCheckData.summary.completion_rate }}%
                </span>
              </template>
            </el-statistic>
          </el-col>
          <el-col :span="4">
            <el-statistic title="需求总值" :value="materialCheckData.summary.total_value" :precision="2" prefix="¥" />
          </el-col>
          <el-col :span="4">
            <el-statistic title="缺料金额">
              <template #value>
                <span class="text-danger">¥{{ toFixedSafe(materialCheckData.summary.shortage_value) }}</span>
              </template>
            </el-statistic>
          </el-col>
        </el-row>

        <!-- 齐套率进度条 -->
        <div class="progress-section" v-if="materialCheckData.summary">
          <span>整体齐套进度：</span>
          <el-progress 
            :percentage="materialCheckData.summary.completion_rate || 0" 
            :status="materialCheckData.summary.completion_rate >= 100 ? 'success' : materialCheckData.summary.completion_rate >= 80 ? '' : 'warning'"
            :stroke-width="20"
            style="flex: 1; margin-left: 10px;"
          />
        </div>

        <!-- 明细表格 -->
        <el-table :data="materialCheckData.details" border stripe max-height="400" style="margin-top: 15px;">
          <el-table-column prop="item_sku" label="物料编码" width="120" />
          <el-table-column prop="item_name" label="物料名称" min-width="150" show-overflow-tooltip />
          <el-table-column prop="specification" label="规格" width="100" show-overflow-tooltip />
          <el-table-column prop="unit" label="单位" width="60" align="center" />
          <el-table-column prop="planned_qty" label="计划数量" width="90" align="right" />
          <el-table-column prop="issued_qty" label="已出库" width="80" align="right" />
          <el-table-column prop="net_demand" label="净需求" width="80" align="right" />
          <el-table-column prop="stock_qty" label="库存" width="80" align="right">
            <template #default="{ row }">
              <span :class="row.stock_qty < row.net_demand ? 'text-danger' : ''">{{ row.stock_qty }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="shortage" label="缺料" width="80" align="right">
            <template #default="{ row }">
              <span class="text-danger" v-if="row.shortage > 0">{{ row.shortage }}</span>
              <span v-else>-</span>
            </template>
          </el-table-column>
          <el-table-column prop="shortage_value" label="缺料金额" width="100" align="right">
            <template #default="{ row }">
              <span class="text-danger" v-if="row.shortage_value > 0">¥{{ toFixedSafe(row.shortage_value) }}</span>
              <span v-else>-</span>
            </template>
          </el-table-column>
          <el-table-column prop="status_display" label="状态" width="90" align="center">
            <template #default="{ row }">
              <el-tag :type="getMaterialCheckStatusType(row.status)" size="small">{{ row.status_display }}</el-tag>
            </template>
          </el-table-column>
        </el-table>
      </div>
      <template #footer>
        <el-button @click="materialCheckDialogVisible = false">关闭</el-button>
        <el-button type="primary" @click="handleGeneratePR" :disabled="!materialCheckData.summary?.shortage_items">
          生成缺料采购申请
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, watch, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Document, Download, Upload, ArrowDown, CopyDocument, UploadFilled, Search, Delete, Folder, Checked, Refresh } from '@element-plus/icons-vue'
import { getBOMList, createBOM, updateBOM, deleteBOM, bulkDeleteBOM, getBOMPendingQuoteCount, exportBOMExcel, exportBOMForQuote, exportBOMTemplate, exportQuoteBOM, importQuoteBOM, importBOMExcel, copyBOMFromProject, getBOMMaterialCheck } from '@/api/projects/bom'
import { getProjectList } from '@/api/projects/project'
import { getUsers } from '@/api/auth'
import { getItemList, getSupplierList } from '@/api/masterdata'
import { toFixedSafe } from '@/utils/number'

const router = useRouter()

const loading = ref(false)
const selectedProject = ref(null)
const projects = ref<any[]>([])
const bomItems = ref<any[]>([])
const items = ref<any[]>([])
const users = ref<any[]>([])
const suppliers = ref<any[]>([])
const dialogVisible = ref(false)
const formRef = ref(null)
const tableRef = ref(null)

// 搜索、筛选和多选
const searchKeyword = ref('')
const filterHasDrawing = ref('')  // 有图/无图筛选
const filterItemType = ref('')    // 物料类型筛选
const filterBrand = ref('')       // 版本/品牌筛选
const selectedRows = ref<any[]>([])

// 分页
const pagination = reactive({
  page: 1,
  pageSize: 50,
  total: 0
})

// Import/Export related
const importDialogVisible = ref(false)
const copyDialogVisible = ref(false)

// 齐套检查
const materialCheckDialogVisible = ref(false)
const materialCheckLoading = ref(false)
const materialCheckData = ref({
  summary: {},
  details: []
})
const uploadRef = ref(null)
const importFile = ref(null)
const importing = ref(false)
const copying = ref(false)
const copySourceProject = ref(null)
const importResult = ref(null)
const importOptions = reactive({
  updateExisting: false,
  autoCreateItems: false
})

const form = reactive({
  id: null,
  item: null,
  item_code: '',
  item_name: '',
  specification: '',
  unit: '',
  item_type: '',
  planned_qty: 1,
  estimated_cost: 0,
  version_brand: '',
  has_drawing: 'PENDING',
  required_date: null,
  requester: null,
  notes: '',
  description: '',
  // 采购与库存字段
  order_status: 'NOT_ORDERED',
  supplier: null,
  delivery_date: null,
  ordered_qty: 0,
  received_qty: 0,
  issued_qty: 0
})

const rules = {
  item: [{ required: true, message: '请选择物料', trigger: 'change' }],
  planned_qty: [{ required: true, message: '请输入计划数量', trigger: 'blur' }]
}

const dialogTitle = computed(() => form.id ? '编辑物料' : '添加物料')

const currentProjectName = computed(() => {
  const project = projects.value.find(p => p.id === selectedProject.value)
  return project ? `${project.code} - ${project.name}` : ''
})

const totalPlannedQty = computed(() => 
  bomItems.value.reduce((sum, item) => sum + parseFloat(item.planned_qty || 0), 0)
)

const totalActualQty = computed(() => 
  bomItems.value.reduce((sum, item) => sum + parseFloat(item.actual_qty || 0), 0)
)

const totalEstimatedCost = computed(() => 
  bomItems.value.reduce((sum, item) => sum + parseFloat(item.planned_qty || 0) * parseFloat(item.estimated_cost || 0), 0)
)

// 待询价物料数量
const pendingQuoteCount = ref(0)

// 获取待询价数量
const fetchPendingQuoteCount = async () => {
  if (!selectedProject.value) {
    pendingQuoteCount.value = 0
    return
  }
  try {
    const res = await getBOMPendingQuoteCount( {
      params: { project: selectedProject.value }
    })
    pendingQuoteCount.value = res.data?.count || res.count || 0
  } catch (error) {
    console.error('获取待询价数量失败:', error)
    pendingQuoteCount.value = 0
  }
}

// 重置筛选条件
const resetFilters = () => {
  filterHasDrawing.value = ''
  filterItemType.value = ''
  filterBrand.value = ''
  searchKeyword.value = ''
  selectedRows.value = []
  pagination.page = 1
  if (tableRef.value) {
    tableRef.value.clearSelection()
  }
  fetchBOM()
}

// 应用筛选（重置到第一页并重新加载）
const applyFilters = () => {
  pagination.page = 1
  fetchBOM()
}

const getProgressStatus = (row) => {
  const percentage = ((row.actual_qty || 0) / (row.planned_qty || 1)) * 100
  if (percentage >= 100) return 'success'
  if (percentage >= 50) return ''
  return 'warning'
}

const fetchProjects = async () => {
  try {
    const res = await getProjectList()
    projects.value = res.data?.results || res.results || res.data || []
  } catch (error) {
    console.error('获取项目列表失败:', error)
  }
}

const fetchBOM = async () => {
  loading.value = true
  try {
    // 构建查询参数
    const params = {
      page: pagination.page,
      page_size: pagination.pageSize
    }
    if (selectedProject.value) {
      params.project = selectedProject.value
    }
    // 筛选参数
    if (filterHasDrawing.value) {
      // 转换前端值到后端值: HAS_DRAWING->YES, NO_DRAWING->NO, PENDING->PENDING
      const hasDrawingMap = { 'HAS_DRAWING': 'YES', 'NO_DRAWING': 'NO', 'PENDING': 'PENDING' }
      params.has_drawing = hasDrawingMap[filterHasDrawing.value] || filterHasDrawing.value
    }
    if (filterItemType.value) {
      params.item_type = filterItemType.value
    }
    if (filterBrand.value.trim()) {
      params.version_brand = filterBrand.value.trim()
    }
    if (searchKeyword.value.trim()) {
      params.search = searchKeyword.value.trim()
    }
    
    const res = await getBOMList(params)
    bomItems.value = res.data?.results || res.results || res.data || res || []
    // 更新分页总数
    pagination.total = res.data?.count || res.count || bomItems.value.length
  } catch (error) {
    console.error('获取BOM列表失败:', error)
    bomItems.value = []
    pagination.total = 0
    ElMessage.error('获取BOM列表失败')
  } finally {
    loading.value = false
  }
}

// 分页变化处理
const handlePageChange = (page) => {
  pagination.page = page
  fetchBOM()
}

const handleSizeChange = (size) => {
  pagination.pageSize = size
  pagination.page = 1
  fetchBOM()
}

const fetchItems = async () => {
  try {
    const res = await getItemList()
    items.value = res.data?.results || res.results || res.data || []
  } catch (error) {
    console.error('获取物料列表失败:', error)
  }
}

const fetchUsers = async () => {
  try {
    const res = await getUsers()
    const userList = res.data?.results || res.results || res.data || []
    users.value = userList.map(u => ({
      id: u.id,
      name: `${u.last_name || ''}${u.first_name || ''}`.trim() || u.username || `用户${u.id}`
    }))
  } catch (error) {
    console.error('获取用户列表失败:', error)
  }
}

const fetchSuppliers = async () => {
  try {
    const res = await getSupplierList()
    suppliers.value = res.data?.results || res.results || res.data || res || []
  } catch (error) {
    console.error('获取供应商列表失败:', error)
  }
}

const resetForm = () => {
  form.id = null
  form.item = null
  form.item_code = ''
  form.item_name = ''
  form.specification = ''
  form.unit = ''
  form.item_type = ''
  form.planned_qty = 1
  form.estimated_cost = 0
  form.version_brand = ''
  form.has_drawing = 'PENDING'
  form.required_date = null
  form.requester = null
  form.notes = ''
  form.description = ''
  // 采购与库存字段
  form.order_status = 'NOT_ORDERED'
  form.supplier = null
  form.delivery_date = null
  form.ordered_qty = 0
  form.received_qty = 0
  form.issued_qty = 0
}

const handleItemChange = (itemId) => {
  const item = items.value.find(i => i.id === itemId)
  if (item) {
    form.item_code = item.sku
    form.item_name = item.name
    form.specification = item.specification || ''
    form.unit = item.unit_display || item.unit || ''
    form.item_type = item.item_type_display || item.item_type || ''
    form.estimated_cost = item.standard_cost || 0
    const brand = item.brand || ''
    const model = item.model || ''
    form.version_brand = brand && model ? `${brand}/${model}` : (brand || model || '')
  }
}

const handleAdd = () => {
  resetForm()
  dialogVisible.value = true
}

const handleEdit = (row) => {
  Object.assign(form, row)
  dialogVisible.value = true
}

const handleDelete = (row) => {
  ElMessageBox.confirm(`确定要删除物料 ${row.item_name} 吗？`, '提示', {
    type: 'warning'
  }).then(async () => {
    try {
      await deleteBOM(row.id)
      ElMessage.success('删除成功')
      fetchBOM()
    } catch (error) {
      ElMessage.error('删除失败')
    }
  }).catch(error => { console.error(error) })
}

const handleSubmit = async () => {
  try {
    await formRef.value.validate()
    
    const data = { ...form, project: form.project || selectedProject.value }
    
    if (form.id) {
      await updateBOM(form.id, data)
      ElMessage.success('更新成功')
    } else {
      await createBOM( data)
      ElMessage.success('添加成功')
    }
    
    dialogVisible.value = false
    fetchBOM()
  } catch (error) {
    if (error !== 'cancel') {
      const errData = error.response?.data
      if (errData?.non_field_errors) {
        ElMessage.error('该物料已在BOM中存在，请勿重复添加')
      } else if (errData?.item) {
        ElMessage.error(errData.item[0] || '物料错误')
      } else {
        ElMessage.error('操作失败')
      }
    }
  }
}

// 多选处理
const handleSelectionChange = (rows) => {
  selectedRows.value = rows
}

// 清除选择
const clearSelection = () => {
  selectedRows.value = []
  if (tableRef.value) {
    tableRef.value.clearSelection()
  }
}

// 批量删除
const handleBatchDelete = async () => {
  if (selectedRows.value.length === 0) {
    ElMessage.warning('请先选择要删除的物料')
    return
  }
  
  try {
    await ElMessageBox.confirm(
      `确定要删除选中的 ${selectedRows.value.length} 项物料吗？此操作不可恢复！`,
      '批量删除',
      { type: 'warning' }
    )
    
    // 使用批量删除接口
    const ids = selectedRows.value.map(row => row.id)
    await bulkDeleteBOM(ids)
    
    ElMessage.success(`成功删除 ${selectedRows.value.length} 项物料`)
    clearSelection()
    fetchBOM()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('删除失败')
    }
  }
}

// 根据选中项生成采购申请
const handleGeneratePRFromSelected = () => {
  if (selectedRows.value.length === 0) {
    ElMessage.warning('请先选择要生成采购申请的物料')
    return
  }
  
  // 使用选中的物料生成采购申请
  generatePurchaseRequest(selectedRows.value)
}

const handleGeneratePR = () => {
  // 筛选出需要采购的物料（剩余需求 > 0）
  const itemsToOrder = bomItems.value.filter(item => {
    const remaining = (item.planned_qty || 0) - (item.issued_qty || 0)
    return remaining > 0
  })
  
  if (itemsToOrder.length === 0) {
    ElMessage.warning('所有物料已满足需求，无需生成采购申请')
    return
  }
  
  generatePurchaseRequest(itemsToOrder)
}

// 通用的生成采购申请函数
const generatePurchaseRequest = (itemsToOrder) => {
  // 确定项目：优先使用选中的项目，否则从物料行中提取
  const projectId = selectedProject.value || itemsToOrder[0]?.project || null
  const projectName = selectedProject.value
    ? currentProjectName.value
    : (itemsToOrder[0]?.project_name || '')

  // 检查是否涉及多个项目
  const projectIds = [...new Set(itemsToOrder.map(i => i.project).filter(Boolean))]
  if (!selectedProject.value && projectIds.length > 1) {
    ElMessage.warning('选中的物料来自多个项目，请先选择项目后再生成采购申请')
    return
  }

  ElMessageBox.confirm(
    `将根据选中物料生成采购申请，包含 ${itemsToOrder.length} 种物料。确定继续？`, 
    '生成采购申请', 
    { type: 'info' }
  ).then(() => {
    const prData = {
      project: projectId,
      projectName: projectName,
      lines: itemsToOrder.map(item => ({
        item: item.item,
        item_sku: item.item_sku,
        item_name: item.item_name,
        qty: Math.max(1, (item.planned_qty || 0) - (item.issued_qty || 0)),
        estimated_price: item.estimated_cost || 0
      }))
    }
    sessionStorage.setItem('bom_to_pr', JSON.stringify(prData))
    router.push('/purchase/requests?from_bom=1')
  }).catch(error => { console.error(error) })
}

// ========== 状态显示辅助函数 ==========

// 获取采购状态标签类型
const getOrderStatusType = (status) => {
  const statusTypeMap = {
    'NOT_ORDERED': 'info',       // 未下单 - 灰色
    'PR_PENDING': 'warning',     // 采购申请中 - 橙色
    'PR_APPROVED': '',           // 申请已批准 - 蓝色（默认）
    'PARTIAL': 'warning',        // 部分下单 - 橙色
    'ORDERED': 'success',        // 已下单 - 绿色
    'IN_TRANSIT': '',            // 在途 - 蓝色
    'PARTIAL_RECEIVED': 'warning', // 部分收货 - 橙色
    'RECEIVED': 'success',       // 已收货 - 绿色
    'RETURNED': 'danger',        // 已退货 - 红色
    'CANCELLED': 'danger',       // 已取消 - 红色
  }
  return statusTypeMap[status] || 'info'
}

// ========== 导入导出功能 ==========

const handleExportExcel = async () => {
  if (!selectedProject.value || !bomItems.value.length) {
    ElMessage.warning('没有可导出的数据')
    return
  }
  
  try {
    const response = await exportBOMExcel({ project: selectedProject.value })
    
    // 获取实际的blob数据
    const blobData = response.data || response
    const blob = new Blob([blobData], { 
      type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' 
    })
    
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.setAttribute('download', `BOM_${currentProjectName.value.split(' - ')[0]}.xlsx`)
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(url)
    
    ElMessage.success('导出成功')
  } catch (error) {
    console.error('导出失败:', error)
    ElMessage.error('导出失败')
  }
}

// 导出筛选结果（用于询价）
const handleExportFiltered = async () => {
  if (!selectedProject.value || bomItems.value.length === 0) {
    ElMessage.warning('没有可导出的数据')
    return
  }
  
  // 获取当前页的物料ID列表
  const itemIds = bomItems.value.map(item => item.id)
  await exportForQuote(itemIds, '筛选结果')
}

// 导出选中项（用于询价）
const handleExportSelected = async () => {
  if (selectedRows.value.length === 0) {
    ElMessage.warning('请先选择要导出的物料')
    return
  }
  
  // 获取选中的物料ID列表
  const itemIds = selectedRows.value.map(item => item.id)
  await exportForQuote(itemIds, '选中项')
}

// 通用导出函数（带历史价格）
const exportForQuote = async (bomIds, exportName) => {
  try {
    const response = await exportBOMForQuote({
      project: selectedProject.value,
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
    const projectName = currentProjectName.value.split(' - ')[0] || '项目'
    link.setAttribute('download', `物料需求清单_${projectName}_${exportName}.xlsx`)
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(url)
    
    ElMessage.success(`导出${exportName}成功，共${bomIds.length}项`)
  } catch (error) {
    console.error('导出失败:', error)
    ElMessage.error('导出失败')
  }
}

const handleDownloadTemplate = async () => {
  try {
    const response = await exportBOMTemplate()
    
    // 获取实际的blob数据
    const blobData = response.data || response
    const blob = new Blob([blobData], { 
      type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' 
    })
    
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.setAttribute('download', 'BOM_import_template.xlsx')
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

// ========== 询价BOM导出/导入功能 ==========

const handleExportQuoteBOM = async () => {
  if (!selectedProject.value) {
    ElMessage.warning('请先选择项目')
    return
  }
  
  if (!pendingQuoteCount.value) {
    ElMessage.warning('没有待询价的物料')
    return
  }
  
  try {
    const response = await exportQuoteBOM({ project: selectedProject.value })
    
    const blobData = response.data || response
    const blob = new Blob([blobData], { 
      type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' 
    })
    
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.setAttribute('download', `询价BOM_${currentProjectName.value.split(' - ')[0]}.xlsx`)
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(url)
    
    ElMessage.success(`导出成功，共 ${pendingQuoteCount.value} 项待询价物料`)
  } catch (error) {
    console.error('导出询价BOM失败:', error)
    ElMessage.error('导出询价BOM失败')
  }
}

// 询价BOM导入对话框
const quoteImportDialogVisible = ref(false)
const quoteImportFile = ref(null)
const quoteImporting = ref(false)
const quoteUploadRef = ref(null)

const handleImportQuoteBOM = () => {
  if (!selectedProject.value) {
    ElMessage.warning('请先选择项目')
    return
  }
  quoteImportFile.value = null
  if (quoteUploadRef.value) {
    quoteUploadRef.value.clearFiles()
  }
  quoteImportDialogVisible.value = true
}

const handleQuoteFileChange = (file) => {
  quoteImportFile.value = file.raw
}

const handleConfirmQuoteImport = async () => {
  if (!quoteImportFile.value) {
    ElMessage.warning('请选择要导入的文件')
    return
  }
  
  quoteImporting.value = true
  try {
    const formData = new FormData()
    formData.append('file', quoteImportFile.value)
    formData.append('project', selectedProject.value)
    
    const response = await importQuoteBOM(formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })
    
    const data = response.data || response
    
    ElMessage.success(data.message || `询价导入成功，已更新 ${data.updated} 条物料`)
    quoteImportDialogVisible.value = false
    fetchBOM()
    fetchPendingQuoteCount()
  } catch (error) {
    console.error('询价导入失败:', error)
    const errData = error.response?.data
    if (errData?.errors?.length) {
      const preview = errData.errors.slice(0, 3).map(e => `行${e.row}: ${e.error}`).join('；')
      ElMessage.error(`导入失败: ${errData.error || preview}`)
    } else {
      ElMessage.error(errData?.error || '询价导入失败')
    }
  } finally {
    quoteImporting.value = false
  }
}

const handleImport = () => {
  importFile.value = null
  importResult.value = null
  importOptions.updateExisting = false
  importOptions.autoCreateItems = false
  if (uploadRef.value) {
    uploadRef.value.clearFiles()
  }
  importDialogVisible.value = true
}

const handleFileChange = (file) => {
  importFile.value = file.raw
  importResult.value = null
}

const handleExceed = () => {
  ElMessage.warning('只能上传一个文件，请先删除已选文件')
}

const handleConfirmImport = async () => {
  if (!importFile.value) {
    ElMessage.warning('请选择要导入的文件')
    return
  }
  
  importing.value = true
  try {
    const formData = new FormData()
    formData.append('file', importFile.value)
    formData.append('project', selectedProject.value)
    formData.append('update_existing', importOptions.updateExisting.toString())
    formData.append('auto_create_items', importOptions.autoCreateItems.toString())
    
    const response = await importBOMExcel(formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })
    
    const data = response.data || response
    importResult.value = data
    
    if (data.created > 0 || data.updated > 0) {
      ElMessage.success(data.message || `导入成功：新增${data.created}条，更新${data.updated}条`)
      fetchBOM()
    } else if (data.errors && data.errors.length > 0) {
      ElMessage.warning('导入完成，但存在错误，请查看详情')
    }
  } catch (error) {
    console.error('导入失败:', error)
    // request.js interceptor 已经解包过，error.response?.data 或直接 error 可能包含信息
    const errData = error.response?.data || error
    if (errData?.errors?.length) {
      // 有详细错误列表
      importResult.value = errData
      // 对话框已经打开，保持显示错误列表
      // 不额外弹窗，因为 request.js 已经弹过了
    } else if (errData?.error) {
      // 有错误消息但没有详细列表
      importResult.value = { error: errData.error }
    }
    // 注意：request.js 的 interceptor 已经弹出了错误提示
  } finally {
    importing.value = false
  }
}

const handleCopyFromProject = () => {
  copySourceProject.value = null
  copyDialogVisible.value = true
}

const handleConfirmCopy = async () => {
  if (!copySourceProject.value) {
    ElMessage.warning('请选择源项目')
    return
  }
  
  copying.value = true
  try {
    const response = await copyBOMFromProject({
        source_project: copySourceProject.value,
        target_project: selectedProject.value
    })
    
    const data = response.data || response
    ElMessage.success(data.message || '复制成功')
    copyDialogVisible.value = false
    fetchBOM()
  } catch (error) {
    console.error('复制失败:', error)
    ElMessage.error(error.response?.data?.error || '复制失败')
  } finally {
    copying.value = false
  }
}

// 齐套检查
const handleMaterialCheck = async () => {
  if (!selectedProject.value) {
    ElMessage.warning('请先选择项目')
    return
  }
  
  materialCheckLoading.value = true
  materialCheckDialogVisible.value = true
  
  try {
    const response = await getBOMMaterialCheck({
      params: { project: selectedProject.value }
    })
    materialCheckData.value = response.data || response
  } catch (error) {
    console.error('齐套检查失败:', error)
    ElMessage.error(error.response?.data?.error || '齐套检查失败')
  } finally {
    materialCheckLoading.value = false
  }
}

const getMaterialCheckStatusType = (status) => {
  const types = {
    'COMPLETE': 'success',
    'READY': 'success',
    'PARTIAL': 'warning',
    'SHORTAGE': 'danger'
  }
  return types[status] || 'info'
}

watch(selectedProject, () => {
  // 切换项目时重置分页和筛选
  pagination.page = 1
  filterHasDrawing.value = ''
  filterItemType.value = ''
  filterBrand.value = ''
  searchKeyword.value = ''
  fetchBOM()
  fetchPendingQuoteCount()  // 同时获取待询价数量
})

onMounted(() => {
  fetchProjects()
  fetchItems()
  fetchUsers()
  fetchSuppliers()
  fetchBOM()  // 默认加载所有BOM
  fetchPendingQuoteCount()  // 获取待询价数量
})
</script>

<style scoped>
.bom-list {
  padding: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 16px;
  font-weight: bold;
}

.header-actions {
  display: flex;
  align-items: center;
}

.stats-row {
  margin-bottom: 20px;
  padding: 15px;
  background-color: #f5f7fa;
  border-radius: 8px;
}

.text-danger {
  color: #f56c6c;
}

.search-bar {
  display: flex;
  align-items: center;
  margin-bottom: 15px;
  padding: 10px 0;
}

.selection-info {
  display: flex;
  align-items: center;
  font-size: 14px;
  color: #606266;
}

.mb-15 {
  margin-bottom: 15px;
}

.mt-15 {
  margin-top: 15px;
}

.upload-area {
  width: 100%;
}

.upload-area :deep(.el-upload-dragger) {
  width: 100%;
}

.import-result {
  margin-top: 20px;
}

.error-list {
  margin-top: 15px;
  max-height: 200px;
  overflow-y: auto;
}

.error-item {
  padding: 2px 0;
  font-size: 12px;
}

.text-warning {
  color: #e6a23c;
}

.text-success {
  color: #67c23a;
}

.progress-section {
  display: flex;
  align-items: center;
  margin-top: 15px;
  padding: 10px 15px;
  background: #f5f7fa;
  border-radius: 4px;
}
</style>
