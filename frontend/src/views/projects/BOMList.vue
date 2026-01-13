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
            <el-button type="primary" @click="handleAdd" :disabled="!selectedProject">
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
      <div class="filter-bar" v-if="bomItems.length > 0 || selectedProject">
        <el-row :gutter="15" style="margin-bottom: 15px;">
          <el-col :span="4">
            <el-select v-model="filterHasDrawing" placeholder="有图/无图" clearable style="width: 100%;">
              <el-option label="全部" value="" />
              <el-option label="有图" value="HAS_DRAWING" />
              <el-option label="无图" value="NO_DRAWING" />
              <el-option label="待定" value="PENDING" />
            </el-select>
          </el-col>
          <el-col :span="5">
            <el-select v-model="filterItemType" placeholder="物料类型" clearable style="width: 100%;">
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
            />
          </el-col>
          <el-col :span="6">
            <el-input 
              v-model="searchKeyword" 
              placeholder="搜索物料编码/名称/规格" 
              clearable 
              @input="handleSearch"
            >
              <template #prefix>
                <el-icon><Search /></el-icon>
              </template>
            </el-input>
          </el-col>
          <el-col :span="4">
            <el-button @click="resetFilters">
              <el-icon><Refresh /></el-icon>
              重置筛选
            </el-button>
          </el-col>
        </el-row>
        
        <!-- 筛选结果提示和操作 -->
        <div class="filter-actions">
          <span class="filter-result">
            筛选结果: <el-tag type="info">{{ filteredBomItems.length }}</el-tag> / {{ bomItems.length }} 项
          </span>
          <el-button 
            type="success" 
            size="small" 
            @click="handleExportFiltered" 
            :disabled="filteredBomItems.length === 0"
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
            <el-button type="danger" size="small" @click="handleBatchDelete" style="margin-left: 5px;">
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
        :data="filteredBomItems" 
        border 
        stripe 
        v-loading="loading"
        ref="tableRef"
        @selection-change="handleSelectionChange"
      >
        <el-table-column type="selection" width="50" />
        <el-table-column type="index" label="序号" width="60" />
        <el-table-column prop="project_name" label="所属项目" width="150" show-overflow-tooltip v-if="!selectedProject" />
        <el-table-column prop="item_code" label="物料编码" width="100" />
        <el-table-column prop="item_name" label="物料名称" width="150" />
        <el-table-column prop="specification" label="规格型号" width="120" show-overflow-tooltip />
        <el-table-column prop="version_brand_display" label="版本/品牌" width="100" show-overflow-tooltip />
        <el-table-column prop="unit" label="单位" width="60" />
        <el-table-column prop="item_type" label="物料类型" width="80" />
        <el-table-column prop="planned_qty" label="计划数量" width="90" align="right" />
        <el-table-column prop="quote_status_display" label="询价状态" width="90" align="center">
          <template #default="{ row }">
            <el-tag 
              :type="row.quote_status === 'QUOTED' ? 'success' : row.quote_status === 'QUOTING' ? 'warning' : 'info'" 
              size="small"
            >
              {{ row.quote_status_display || '未询价' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="price_with_tax" label="含税单价" width="100" align="right">
          <template #default="{ row }">
            <span v-if="row.price_with_tax">¥{{ parseFloat(row.price_with_tax).toFixed(4) }}</span>
            <span v-else class="text-muted">-</span>
          </template>
        </el-table-column>
        <el-table-column prop="order_status_display" label="下单状态" width="90" align="center">
          <template #default="{ row }">
            <el-tag 
              :type="row.order_status === 'ORDERED' ? 'success' : row.order_status === 'PARTIAL' ? 'warning' : 'info'" 
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
            <el-button type="primary" link size="small" @click="handleEdit(row)">编辑</el-button>
            <el-button type="danger" link size="small" @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
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
            <el-form-item label="下单状态">
              <el-select v-model="form.order_status" style="width: 100%;">
                <el-option label="未下单" value="NOT_ORDERED" />
                <el-option label="部分下单" value="PARTIAL" />
                <el-option label="已下单" value="ORDERED" />
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
      
      <el-checkbox v-model="importOptions.updateExisting" class="mt-15">
        更新已存在的物料（不勾选则跳过已存在的物料）
      </el-checkbox>
      
      <!-- 导入结果 -->
      <div v-if="importResult" class="import-result">
        <el-divider content-position="left">导入结果</el-divider>
        <el-descriptions :column="2" border size="small">
          <el-descriptions-item label="新增">
            <el-tag type="success">{{ importResult.created }} 条</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="更新">
            <el-tag type="primary">{{ importResult.updated }} 条</el-tag>
          </el-descriptions-item>
        </el-descriptions>
        
        <div v-if="importResult.errors && importResult.errors.length > 0" class="error-list">
          <el-alert title="导入错误" type="error" show-icon :closable="false">
            <template #default>
              <div v-for="error in importResult.errors" :key="error.row" class="error-item">
                第 {{ error.row }} 行: {{ error.error }}
              </div>
            </template>
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
                <span class="text-danger">¥{{ (materialCheckData.summary.shortage_value || 0).toFixed(2) }}</span>
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
              <span class="text-danger" v-if="row.shortage_value > 0">¥{{ row.shortage_value.toFixed(2) }}</span>
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

<script setup>
import { ref, reactive, computed, watch, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Document, Download, Upload, ArrowDown, CopyDocument, UploadFilled, Search, Delete, Folder, Checked, Refresh } from '@element-plus/icons-vue'
import request from '@/utils/request'

const router = useRouter()

const loading = ref(false)
const selectedProject = ref(null)
const projects = ref([])
const bomItems = ref([])
const items = ref([])
const users = ref([])
const suppliers = ref([])
const dialogVisible = ref(false)
const formRef = ref(null)
const tableRef = ref(null)

// 搜索、筛选和多选
const searchKeyword = ref('')
const filterHasDrawing = ref('')  // 有图/无图筛选
const filterItemType = ref('')    // 物料类型筛选
const filterBrand = ref('')       // 版本/品牌筛选
const selectedRows = ref([])

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
  updateExisting: false
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
    const res = await request.get('/projects/bom/pending_quote_count/', {
      params: { project: selectedProject.value }
    })
    pendingQuoteCount.value = res.data?.count || res.count || 0
  } catch (error) {
    console.error('获取待询价数量失败:', error)
    pendingQuoteCount.value = 0
  }
}

// 搜索和筛选后的 BOM 列表
const filteredBomItems = computed(() => {
  let result = bomItems.value
  
  // 1. 有图/无图筛选
  if (filterHasDrawing.value) {
    result = result.filter(item => item.has_drawing === filterHasDrawing.value)
  }
  
  // 2. 物料类型筛选（根据物料编码解析或item_type字段）
  if (filterItemType.value) {
    result = result.filter(item => {
      // 尝试从item_type_display或物料编码解析
      const itemType = item.item_type_display || item.item_type || ''
      return itemType.includes(filterItemType.value)
    })
  }
  
  // 3. 版本/品牌筛选
  if (filterBrand.value.trim()) {
    const brandKeyword = filterBrand.value.toLowerCase().trim()
    result = result.filter(item => {
      const versionBrand = (item.version_brand_display || item.version_brand || '').toLowerCase()
      return versionBrand.includes(brandKeyword)
    })
  }
  
  // 4. 关键字搜索
  if (searchKeyword.value.trim()) {
    const keyword = searchKeyword.value.toLowerCase().trim()
    result = result.filter(item => {
      return (item.item_code && item.item_code.toLowerCase().includes(keyword)) ||
             (item.item_name && item.item_name.toLowerCase().includes(keyword)) ||
             (item.specification && item.specification.toLowerCase().includes(keyword))
    })
  }
  
  return result
})

// 重置筛选条件
const resetFilters = () => {
  filterHasDrawing.value = ''
  filterItemType.value = ''
  filterBrand.value = ''
  searchKeyword.value = ''
  selectedRows.value = []
  if (tableRef.value) {
    tableRef.value.clearSelection()
  }
}

const getProgressStatus = (row) => {
  const percentage = ((row.actual_qty || 0) / (row.planned_qty || 1)) * 100
  if (percentage >= 100) return 'success'
  if (percentage >= 50) return ''
  return 'warning'
}

const fetchProjects = async () => {
  try {
    const res = await request.get('/projects/projects/')
    projects.value = res.data?.results || res.results || res.data || []
  } catch (error) {
    console.error('获取项目列表失败:', error)
  }
}

const fetchBOM = async () => {
  loading.value = true
  try {
    // 构建查询参数，如果选择了项目则过滤
    const params = {}
    if (selectedProject.value) {
      params.project = selectedProject.value
    }
    const res = await request.get('/projects/bom/', { params })
    bomItems.value = res.data?.results || res.results || res.data || res || []
  } catch (error) {
    console.error('获取BOM列表失败:', error)
    bomItems.value = []
    ElMessage.error('获取BOM列表失败')
  } finally {
    loading.value = false
  }
}

const fetchItems = async () => {
  try {
    const res = await request.get('/masterdata/items/')
    items.value = res.data?.results || res.results || res.data || []
  } catch (error) {
    console.error('获取物料列表失败:', error)
  }
}

const fetchUsers = async () => {
  try {
    const res = await request.get('/auth/users/')
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
    const res = await request.get('/masterdata/suppliers/')
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
      await request.delete(`/projects/bom/${row.id}/`)
      ElMessage.success('删除成功')
      fetchBOM()
    } catch (error) {
      ElMessage.error('删除失败')
    }
  }).catch(() => {})
}

const handleSubmit = async () => {
  try {
    await formRef.value.validate()
    
    const data = { ...form, project: selectedProject.value }
    
    if (form.id) {
      await request.put(`/projects/bom/${form.id}/`, data)
      ElMessage.success('更新成功')
    } else {
      await request.post('/projects/bom/', data)
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

// 搜索处理
const handleSearch = () => {
  // 搜索时清空选择
  selectedRows.value = []
  if (tableRef.value) {
    tableRef.value.clearSelection()
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
    await request.post('/projects/bom/bulk_delete/', { ids })
    
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
    const remaining = (item.planned_qty || 0) - (item.actual_qty || 0)
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
  ElMessageBox.confirm(
    `将根据选中物料生成采购申请，包含 ${itemsToOrder.length} 种物料。确定继续？`, 
    '生成采购申请', 
    { type: 'info' }
  ).then(() => {
    // 将需要采购的物料信息存储到sessionStorage
    const prData = {
      project: selectedProject.value,
      projectName: currentProjectName.value,
      lines: itemsToOrder.map(item => ({
        item: item.item,
        item_sku: item.item_code,
        item_name: item.item_name,
        qty: Math.max(1, (item.planned_qty || 0) - (item.actual_qty || 0)),
        estimated_price: item.estimated_cost || 0
      }))
    }
    sessionStorage.setItem('bom_to_pr', JSON.stringify(prData))
    
    // 跳转到采购申请页面
    router.push('/purchase/requests?from_bom=1')
  }).catch(() => {})
}

// ========== 导入导出功能 ==========

const handleExportExcel = async () => {
  if (!selectedProject.value || !bomItems.value.length) {
    ElMessage.warning('没有可导出的数据')
    return
  }
  
  try {
    const response = await request.get('/projects/bom/export_excel/', {
      params: { project: selectedProject.value },
      responseType: 'blob'
    })
    
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
  if (!selectedProject.value || filteredBomItems.value.length === 0) {
    ElMessage.warning('没有可导出的数据')
    return
  }
  
  // 获取筛选后的物料ID列表
  const itemIds = filteredBomItems.value.map(item => item.id)
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
    const response = await request.post('/projects/bom/export_for_quote/', {
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
    const response = await request.get('/projects/bom/export_template/', {
      responseType: 'blob'
    })
    
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
    const response = await request.get('/projects/bom/export_quote_bom/', {
      params: { project: selectedProject.value },
      responseType: 'blob'
    })
    
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
    
    const response = await request.post('/projects/bom/import_quote_bom/', formData, {
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
    
    const response = await request.post('/projects/bom/import_excel/', formData, {
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
    const errData = error.response?.data
    if (errData?.errors?.length) {
      const preview = errData.errors
        .slice(0, 3)
        .map(e => `行${e.row}: ${e.error}`)
        .join('；')
      ElMessage.error(errData.error ? `${errData.error}（${preview}）` : preview)
      importResult.value = errData
    } else {
      ElMessage.error(errData?.error || '导入失败')
    }
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
    const response = await request.post('/projects/bom/copy_from_project/', {
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
    const response = await request.get('/projects/bom/material_check/', {
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

