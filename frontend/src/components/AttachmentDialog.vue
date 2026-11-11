<script setup lang="ts">
import BusinessTable from './BusinessTable.vue'
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { read, download } from '../api'
import { can, purchasing } from '../session'
import { display } from '../business'
import { message } from '../utils/request'
import { pageSize } from '../pagination'
import type { Row, Command } from '../types'
import ActionDialog from './ActionDialog.vue'
import ListPagination from './ListPagination.vue'
import RecordDeletionDialog from './RecordDeletionDialog.vue'
import AttachmentRemovalDialog from './AttachmentRemovalDialog.vue'
import { useBatchSelection } from '../utils/batch-selection'
import { canDeleteRecords, deletionLimit, deletionLabel } from '../modules/deletions'
import { openDocumentPreview } from '../document-preview'

const props = defineProps<{ owner: 'sale' | 'purchase'; record: Row }>()
const emit = defineEmits<{ close: [] }>()
const title = computed(() => `${props.owner === 'sale' ? '销售' : '采购'}附件 · ${props.record.code}`)
const writable = computed(() => props.record.status !== 'cancelled' && (props.owner === 'sale' ? can(['admin', 'manager', 'sales_manager']) : purchasing()))
const records = ref<Row[]>([])
const total = ref(0)
const page = ref(1)
const loading = ref(false)
const error = ref('')
const command = ref<Command | null>(null)
const deletionAllowed = computed(() => canDeleteRecords('documents'))
const selection = ref<Row[]>([]), deleting = ref<Row[] | null>(null), deletionHistory = ref(false)
// 管理员沿用“已删除记录”体系的批量删除；其他人只能撤回自己（或作为项目经理）有权删除的附件，
// 两套勾选互斥：管理员看到的是原有勾选栏，其余角色只给 can_remove 为真的行显示复选框。
const removalLimit = 50
const limit = () => deletionAllowed.value ? deletionLimit('documents') : removalLimit
const batch = useBatchSelection(selection, 'id', limit)
const removing = ref<Row[] | null>(null)
const pickable = (row: Row) => deletionAllowed.value || Boolean(row.can_remove)
const pickableRows = computed(() => records.value.filter(pickable))
const removalMode = computed(() => !deletionAllowed.value && records.value.some(row => row.can_remove))
const selectingAll = ref(false)
let selectionGeneration = 0
let generation = 0
function cancelSelection() { selectionGeneration++; selectingAll.value = false; selection.value = [] }
onBeforeUnmount(() => { generation++; cancelSelection() })
watch(deletionAllowed, allowed => { cancelSelection(); removing.value = null; if (!allowed) { deleting.value = null; deletionHistory.value = false } })
async function selectFilteredRows() {
  if (!deletionAllowed.value || loading.value || selectingAll.value) return
  const current = ++selectionGeneration
  const params = { [props.owner]: props.record.id }
  selectingAll.value = true; error.value = ''
  try {
    await batch.replacePages(
      (page, page_size) => read('/business/documents/', { ...params, page, page_size }),
      () => current === selectionGeneration && deletionAllowed.value,
    )
  } catch (e) { if (current === selectionGeneration) error.value = message(e) }
  finally { if (current === selectionGeneration) selectingAll.value = false }
}
function saved() { page.value = 1; void load() }
async function load(preserveSelection: unknown = false) {
  selectionGeneration++; selectingAll.value = false
  if (preserveSelection !== true) selection.value = []
  const current = ++generation
  loading.value = true
  error.value = ''
  try {
    const result = await read('/business/documents/', { [props.owner]: props.record.id, page: page.value, page_size: pageSize.value })
    if (current === generation) { records.value = result.results; total.value = result.count }
  } catch (e) { if (current === generation) { records.value = []; total.value = 0; error.value = message(e) } }
  finally { if (current === generation) loading.value = false }
}
function upload() {
  command.value = {
    title: props.owner === 'sale' ? '上传销售附件' : '上传采购附件', path: '/business/documents/',
    fields: [
      { key: 'category', label: '分类', type: 'select', options: [{ value: 'contract', label: '合同' }, { value: 'other', label: '其他（报价及技术资料）' }] },
      { key: 'file', label: '文件', type: 'file', hint: '单个文件不超过 20 MB；重新上传会保留原文件。' },
    ], initial: { category: 'contract' }, prepare: data => ({ ...data, [props.owner]: props.record.id }),
  }
}
async function downloadFile(row: Row) {
  try { await download(row.download_url, row.original_name) }
  catch (e) { error.value = message(e) }
}
watch([() => props.owner, () => props.record.id], () => { page.value = 1; deleting.value = null; removing.value = null; deletionHistory.value = false; void load() }, { immediate: true })
watch(pageSize, () => { page.value = 1; void load(true) })
</script>
<template>
  <el-dialog class="transfer-dialog" :model-value="true" :title="title" width="min(800px, 94vw)" append-to-body @close="emit('close')">
    <p class="muted">附件关联当前单据，项目中自动汇总。仅有权限的人员可查看和下载。</p>
    <el-alert v-if="error" :title="error" type="error" :closable="false" role="alert" />
    <div class="toolbar"><el-button :loading="loading" @click="load">刷新</el-button><el-button v-if="writable" type="primary" @click="upload">上传附件</el-button><el-button v-if="deletionAllowed" type="danger" plain :disabled="loading || selectingAll || !selection.length" @click="deleting = [...selection]">批量删除{{ selection.length ? `（${selection.length}）` : '' }}</el-button><el-button v-if="removalMode" type="danger" plain :disabled="loading || !selection.length" @click="removing = [...selection]">删除所选{{ selection.length ? `（${selection.length}）` : '' }}</el-button><el-button v-if="deletionAllowed" @click="deletionHistory = true">已删除记录</el-button></div>
    <div v-if="deletionAllowed" class="attachment-batch-selection" aria-label="附件批量选择">
      <span>已选 <strong>{{ selection.length }}</strong> 项（跨页保留），每批最多 {{ deletionLimit('documents') }} 项</span>
      <el-button :loading="selectingAll" :disabled="loading || !total" @click="selectFilteredRows">{{ total > deletionLimit('documents') ? '选择筛选结果前' + deletionLimit('documents') + '项（跨页）' : '全选筛选结果（' + total + '项，跨页）' }}</el-button>
      <el-button text :disabled="loading || selectingAll || !selection.length" @click="selection = []">清空选择</el-button>
    </div>
    <BusinessTable label="附件" :row-offset="(page - 1) * pageSize" :data="records" :aria-busy="loading" max-height="420" row-key="id">
      <el-table-column v-if="deletionAllowed || removalMode" label="选择" width="44">
        <template #header><input type="checkbox" aria-label="选择本页附件" :checked="batch.all(pickableRows)" :indeterminate="batch.some(pickableRows)" :disabled="loading || selectingAll || !pickableRows.length || (selection.length >= limit() && !batch.all(pickableRows))" @change="batch.togglePage(pickableRows)" /></template>
        <template #default="{ row }"><input v-if="pickable(row)" type="checkbox" :aria-label="'选择附件 ' + deletionLabel(row)" :checked="batch.has(row)" :disabled="loading || selectingAll || !batch.selectable(row)" @change="batch.toggle(row)" /></template>
      </el-table-column>
      <el-table-column prop="original_name" label="文件" min-width="220"><template #default="{ row }"><button class="attachment-name" @click="openDocumentPreview(row.id, row.original_name)">{{ row.original_name }}</button></template></el-table-column>
      <el-table-column label="分类" min-width="80"><template #default="{ row }">{{ display(row.category, 'category') }}</template></el-table-column>
      <el-table-column label="大小" width="100"><template #default="{ row }">{{ Math.max(1, Math.ceil(row.size / 1024)) }} KB</template></el-table-column>
      <el-table-column label="上传时间" min-width="170"><template #default="{ row }">{{ new Date(row.created_at).toLocaleString('zh-CN', { hour12: false }) }}</template></el-table-column>
      <el-table-column label="操作" :width="deletionAllowed || removalMode ? 200 : 140" fixed="right"><template #default="{ row }"><el-button size="small" type="primary" @click="openDocumentPreview(row.id, row.original_name)">预览</el-button><el-button size="small" @click="downloadFile(row)">下载</el-button><el-button v-if="deletionAllowed" type="danger" text size="small" :disabled="loading || selectingAll" @click="deleting = [row]">删除</el-button><el-button v-if="removalMode && row.can_remove" type="danger" text size="small" :disabled="loading" @click="removing = [row]">删除</el-button></template></el-table-column>
    </BusinessTable>
    <ListPagination :page="page" :total="total" @change="page = $event; load(true)" />
    <template #footer><el-button @click="emit('close')">关闭</el-button></template>
  </el-dialog>
  <ActionDialog :command="command" @close="command = null" @saved="saved" />
  <AttachmentRemovalDialog v-if="removing" :rows="removing" @close="removing = null" @saved="saved" />
  <RecordDeletionDialog v-if="deletionAllowed && (deleting || deletionHistory)" resource="documents" title="附件" :rows="deleting || undefined" :sale-id="owner === 'sale' ? record.id : undefined" :purchase-id="owner === 'purchase' ? record.id : undefined" :show-original="false" @close="deleting = null; deletionHistory = false" @saved="saved" />
</template>
<style scoped>
.attachment-batch-selection { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; margin: 12px 0; }
.toolbar { margin-bottom: 12px; }
.attachment-name { border: 0; background: none; padding: 0; color: var(--el-color-primary); cursor: pointer; text-align: left; overflow-wrap: anywhere; font: inherit; }
@media (max-width: 600px) {
  .toolbar .el-button, .attachment-batch-selection .el-button { min-height: 40px; }
  :global(.transfer-dialog .el-dialog__footer .el-button) { min-height: 40px; }
}
</style>
