<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { read, write, download } from '../api'
import { bomCommand, permission } from '../business'
import { manager } from '../session'
import type { Row, Command } from '../types'
import { message } from '../utils/request'
import ActionDialog from './ActionDialog.vue'
import ListPagination from './ListPagination.vue'
import TransferTools from './TransferTools.vue'
import BOMPurchasePicker from './BOMPurchasePicker.vue'
import { pageSize } from '../pagination'
const props = defineProps<{ projectId: number; revision?: number; status?: string }>()
const emit = defineEmits<{ changed: [] }>()
const demand = ref<Row>({ lines: [] })
const preview = ref<Row | null>(null)
const error = ref('')
const busy = ref(false)
const command = ref<Command | null>(null)
const impact = ref<Row | null>(null)
async function inspectImpact() {
  try { impact.value = await read(`/business/projects/${props.projectId}/bom-impact/`) } catch (e) { error.value = message(e) }
}
const page = ref(1)
const previewPage = ref(1)
const visibleLines = computed(() => demand.value.lines.slice((page.value - 1) * pageSize.value, page.value * pageSize.value))
const visiblePreview = computed(() => (preview.value?.lines || []).slice((previewPage.value - 1) * pageSize.value, previewPage.value * pageSize.value))
watch([pageSize, () => demand.value.lines], () => { page.value = 1 })
watch([pageSize, preview], () => { previewPage.value = 1 })
let generation = 0
async function load() {
  const id = ++generation
  try {
    const result = await read(`/business/projects/${props.projectId}/demand/`)
    if (id === generation) demand.value = result
  } catch (e) {
    if (id === generation) error.value = message(e)
  }
}
watch(
  () => [props.projectId, props.revision],
  () => {
    preview.value = null
    void load()
  },
  { immediate: true },
)
async function start() {
  error.value = ''
  try {
    command.value = await bomCommand(props.projectId)
  } catch (e) {
    error.value = message(e)
  }
}
async function importFile(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  busy.value = true
  error.value = ''
  try {
    const body = new FormData()
    body.append('file', file)
    preview.value = await write(
      `/business/projects/${props.projectId}/import-preview/`,
      body,
      crypto.randomUUID(),
    )
  } catch (e) {
    error.value = message(e)
  } finally {
    busy.value = false
    input.value = ''
  }
}
function confirmImport() {
  if (!preview.value?.can_import) return
  const result = preview.value
  command.value = {
    title: '确认导入 BOM',
    path: `/business/projects/${props.projectId}/revise-bom/`,
    previewPath: `/business/projects/${props.projectId}/bom-change-preview/`,
    fields: [],
    prepare: () => ({
      expected_revision: result.expected_revision,
      lines: result.lines.map((r: Row) => ({
        item: r.item,
        quantity: r.quantity,
        change_note: r.change_note,
        assembly_unit: r.assembly_unit,
      })),
    }),
  }
}
function saved() {
  preview.value = null
  void load()
  emit('changed')
}
</script>
<template>
  <section class="panel" aria-label="BOM 缺料需求">
    <header class="panel-heading">
      <h2>BOM 与缺料</h2>
      <div class="toolbar">
        <TransferTools resource="bom" path="/business/bom/" :params="{ project: projectId }" />
        <el-button @click="load">刷新需求</el-button
        ><template v-if="manager() && ['draft', 'quoted', 'active', 'delivering'].includes(status || '')"
          ><el-button
            @click="
              download('/business/projects/bom-template/', 'bom-template.csv').catch(
                (e) => (error = message(e)),
              )
            "
            >下载模板</el-button
          ><label class="file-button"
            >导入预览<input type="file" accept=".csv,.xlsx" :disabled="busy" @change="importFile" /></label
          ><el-button @click="inspectImpact">变更影响与处理</el-button><el-button type="primary" @click="start">维护 BOM</el-button></template
        ><BOMPurchasePicker
          v-if="permission.buyer() && ['active', 'delivering', 'warranty'].includes(status || '')"
          :project-id="projectId" label="按缺料采购" @saved="saved"
        />
      </div>
    </header>
    <p class="muted">库存为共享库存，不预留，当前可用不保证后续可领。同物料可分属多个单元；已领、在途及库存按行顺序分摊，非单元实际领用记录。</p>
    <el-dialog :model-value="Boolean(impact)" title="BOM 变更影响与处理" width="min(900px, 94vw)" @close="impact = null">
      <template v-if="impact"><p>{{ impact.note }}</p><el-table :data="impact.items" max-height="360"><el-table-column prop="item_code" label="物料编码" /><el-table-column prop="item_name" label="物料" /><el-table-column prop="quantity" label="需求总量" /><el-table-column prop="issued" label="已领" /><el-table-column prop="incoming" label="在途/草稿" /><el-table-column prop="minimum" label="当前最低可改量" /></el-table><p v-for="purchase in impact.purchases" :key="purchase.id"><router-link :to="{ path: `/projects/${projectId}`, query: { tab: 'purchases', resource: 'purchases', focus: purchase.id } }" @click="impact = null">{{ purchase.code }}：查看采购并处理未收余量</router-link></p><router-link :to="{ path: '/inventory', query: { project: projectId } }">查看本项目库存流水，处理未用材料退回</router-link></template>
      <template #footer><el-button @click="impact = null">关闭</el-button></template>
    </el-dialog>
    <el-alert v-if="error" :title="error" type="error" :closable="false" role="alert" />
    <el-table :data="visibleLines" :max-height="560" empty-text="尚未维护 BOM"
      ><el-table-column prop="item_code" label="物料编码" /><el-table-column
        prop="item_name"
        label="物料" /><el-table-column prop="brand" label="品牌" /><el-table-column prop="assembly_unit" label="单元" /><el-table-column prop="quantity" label="需求" /><el-table-column
        prop="issued"
        label="已领" /><el-table-column prop="incoming" label="在途" /><el-table-column
        prop="available"
        label="可用库存" /><el-table-column prop="shortage" label="缺料"
    /></el-table>
    <ListPagination :page="page" :total="demand.lines.length" @change="page = $event" />
    <div v-if="preview" class="import-preview">
      <h3>导入预览</h3>
      <el-alert
        v-if="!preview.can_import"
        :title="JSON.stringify(preview.errors)"
        type="error"
        :closable="false"
      /><el-table :data="visiblePreview" :max-height="560"
        ><el-table-column prop="item" label="物料" /><el-table-column
          prop="quantity"
          label="数量" /><el-table-column prop="change_note" label="变更说明" /></el-table
      ><ListPagination :page="previewPage" :total="preview.lines.length" @change="previewPage = $event" />
      <el-button type="primary" :disabled="!preview.can_import" @click="confirmImport">确认导入</el-button
      ><el-button @click="preview = null">取消导入</el-button>
    </div>
    <ActionDialog :command="command" @close="command = null" @saved="saved" />
  </section>
</template>
