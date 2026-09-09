<script setup lang="ts">
import { ref, watch } from 'vue'
import { read, write, download } from '../api'
import { bomCommand, shortageCommand, permission } from '../business'
import { manager } from '../session'
import type { Row, Command } from '../types'
import { message } from '../utils/request'
import ActionDialog from './ActionDialog.vue'
const props = defineProps<{ projectId: number; revision?: number; status?: string }>()
const emit = defineEmits<{ changed: [] }>()
const demand = ref<Row>({ lines: [] })
const preview = ref<Row | null>(null)
const error = ref('')
const busy = ref(false)
const command = ref<Command | null>(null)
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
async function start(kind: string) {
  error.value = ''
  try {
    command.value = await (kind === 'bom' ? bomCommand : shortageCommand)(props.projectId)
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
    fields: [],
    prepare: () => ({
      expected_revision: result.expected_revision,
      lines: result.lines.map((r: Row) => ({
        item: r.item,
        quantity: r.quantity,
        change_note: r.change_note,
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
          ><el-button type="primary" @click="start('bom')">维护 BOM</el-button></template
        ><el-button
          v-if="permission.buyer() && ['active', 'delivering', 'warranty'].includes(status || '')"
          @click="start('purchase')"
          >按缺料采购</el-button
        >
      </div>
    </header>
    <p class="muted">缺料按当前库存、已领料和在途量计算；库存为共享库存，不自动预留。</p>
    <el-alert v-if="error" :title="error" type="error" :closable="false" role="alert" />
    <el-table :data="demand.lines" empty-text="尚未维护 BOM"
      ><el-table-column prop="item_code" label="物料编码" /><el-table-column
        prop="item_name"
        label="物料" /><el-table-column prop="quantity" label="需求" /><el-table-column
        prop="issued"
        label="已领" /><el-table-column prop="incoming" label="在途" /><el-table-column
        prop="available"
        label="可用库存" /><el-table-column prop="shortage" label="缺料"
    /></el-table>
    <div v-if="preview" class="import-preview">
      <h3>导入预览</h3>
      <el-alert
        v-if="!preview.can_import"
        :title="JSON.stringify(preview.errors)"
        type="error"
        :closable="false"
      /><el-table :data="preview.lines"
        ><el-table-column prop="item" label="物料" /><el-table-column
          prop="quantity"
          label="数量" /><el-table-column prop="change_note" label="变更说明" /></el-table
      ><el-button type="primary" :disabled="!preview.can_import" @click="confirmImport">确认导入</el-button
      ><el-button @click="preview = null">取消导入</el-button>
    </div>
    <ActionDialog :command="command" @close="command = null" @saved="saved" />
  </section>
</template>
