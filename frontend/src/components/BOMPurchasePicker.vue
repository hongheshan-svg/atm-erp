<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { ElSelect, ElOption } from 'element-plus'
import { all, read } from '../api'
import { shortageCommand } from '../modules/purchases'
import { buyer } from '../modules/shared'
import { message } from '../utils/request'
import type { Row, Command } from '../types'
import { pageSize } from '../pagination'
import ListPagination from './ListPagination.vue'
import ActionDialog from './ActionDialog.vue'

const props = withDefaults(defineProps<{ projectId?: number; label?: string }>(), { label: '从 BOM 多选下单' })
const emit = defineEmits<{ saved: [] }>()
const opened = ref(false)
const projects = ref<Row[]>([])
const project = ref<number>()
const lines = ref<Row[]>([])
const selected = ref<number[]>([])
const search = ref('')
const brands = ref<string[]>([])
const units = ref<string[]>([])
const types = ref<string[]>([])
const page = ref(1)
const busy = ref(false)
const error = ref('')
const command = ref<Command | null>(null)
const typeName = (value: string) => ({ standard: '标准件', custom: '非标件' }[value] || '未分类')
const options = (key: string) => [...new Set(lines.value.map(r => String(r[key] || '')))].sort()
const filtered = computed(() => lines.value.filter(r =>
  (!brands.value.length || brands.value.includes(r.brand || '')) &&
  (!units.value.length || units.value.includes(r.assembly_unit || '')) &&
  (!types.value.length || types.value.includes(r.part_type || '')) &&
  [r.item_code, r.item_name, r.specification].join(' ').toLowerCase().includes(search.value.trim().toLowerCase()),
))
const visible = computed(() => filtered.value.slice((page.value - 1) * pageSize.value, page.value * pageSize.value))
const eligible = (row: Row) => Number(row.shortage) > 0 && row.is_active !== false
watch([search, brands, units, types, pageSize], () => { page.value = 1 }, { deep: true })
function toggle(id: number) {
  selected.value = selected.value.includes(id) ? selected.value.filter(v => v !== id) : [...selected.value, id]
}
function selectFiltered() {
  selected.value = [...new Set([...selected.value, ...filtered.value.filter(eligible).map(r => r.bom_line)])]
}
async function load() {
  lines.value = []
  error.value = ''
  if (!project.value) return
  busy.value = true
  try {
    const result = await read(`/business/projects/${project.value}/demand/`)
    lines.value = result.lines
    selected.value = selected.value.filter(id => result.lines.some((r: Row) => r.bom_line === id && eligible(r)))
    page.value = 1
  } catch (e) { error.value = message(e) } finally { busy.value = false }
}
async function changeProject() {
  selected.value = []; brands.value = []; units.value = []; types.value = []; search.value = ''
  await load()
}
async function open() {
  opened.value = true
  project.value = props.projectId
  busy.value = true
  error.value = ''
  try {
    if (!props.projectId) projects.value = (await all('/business/projects/')).filter(p => ['active', 'delivering', 'warranty'].includes(p.status))
    await changeProject()
  } catch (e) { error.value = message(e) } finally { busy.value = false }
}
async function generate() {
  if (!project.value || !selected.value.length) return
  busy.value = true
  error.value = ''
  try {
    command.value = await shortageCommand(project.value, selected.value)
    opened.value = false
  } catch (e) { error.value = message(e) } finally { busy.value = false }
}
function saved() { selected.value = []; emit('saved') }
</script>
<template>
  <el-button v-if="buyer()" :disabled="busy" @click="open">{{ label }}</el-button>
  <el-dialog v-model="opened" class="transfer-dialog" title="选择 BOM 下单" width="min(1150px, 96vw)" :close-on-click-modal="false" :close-on-press-escape="!busy" :show-close="!busy" destroy-on-close>
    <div class="bom-purchase-filters">
      <label v-if="!projectId">项目<select v-model="project" aria-label="采购项目" :disabled="busy" @change="changeProject"><option :value="undefined">请选择项目</option><option v-for="p in projects" :key="p.id" :value="p.id">{{ p.code }} · {{ p.name }}</option></select></label>
      <label>搜索物料<input v-model="search" aria-label="搜索 BOM 物料" placeholder="编码、名称或规格" :disabled="busy" /></label>
      <label>品牌<ElSelect v-model="brands" multiple clearable filterable aria-label="筛选品牌" placeholder="全部品牌" :disabled="busy"><ElOption v-for="v in options('brand')" :key="v" :label="v || '未填写'" :value="v" /></ElSelect></label>
      <label>单元<ElSelect v-model="units" multiple clearable filterable aria-label="筛选单元" placeholder="全部单元" :disabled="busy"><ElOption v-for="v in options('assembly_unit')" :key="v" :label="v || '未填写'" :value="v" /></ElSelect></label>
      <label>类别<ElSelect v-model="types" multiple clearable aria-label="筛选类别" placeholder="全部类别" :disabled="busy"><ElOption v-for="v in options('part_type')" :key="v" :label="typeName(v)" :value="v" /></ElSelect></label>
    </div>
    <p class="muted">可组合筛选并跨页勾选；切换筛选保留已选项。无缺口或停用物料不可勾选，每张订单选择一个供应商。</p>
    <div class="toolbar"><el-button :disabled="busy || !project" @click="load">刷新缺料</el-button><el-button :disabled="busy || !filtered.some(eligible)" @click="selectFiltered">全选筛选结果</el-button><el-button :disabled="busy || !selected.length" @click="selected = []">清空选择</el-button><strong role="status">已选 {{ selected.length }} 项 · 筛选结果 {{ filtered.length }} 项</strong></div>
    <el-alert v-if="error" :title="error" type="error" :closable="false" role="alert" />
    <el-table :data="visible" :max-height="440" row-key="bom_line" empty-text="请选择项目，或调整筛选条件">
      <el-table-column label="选择" width="65" fixed><template #default="{ row }"><input type="checkbox" :aria-label="`选择 ${row.item_code}`" :checked="selected.includes(row.bom_line)" :disabled="busy || !eligible(row)" @change="toggle(row.bom_line)" /></template></el-table-column>
      <el-table-column prop="item_code" label="物料编码" min-width="140" /><el-table-column prop="item_name" label="物料" min-width="150" /><el-table-column prop="specification" label="规格" min-width="140" /><el-table-column prop="brand" label="品牌" min-width="100" /><el-table-column prop="assembly_unit" label="单元" min-width="120" /><el-table-column label="类别" min-width="100"><template #default="{ row }">{{ typeName(row.part_type) }}</template></el-table-column>
      <el-table-column prop="quantity" label="BOM需求" width="100" /><el-table-column prop="incoming" label="已下单未收" width="115" /><el-table-column prop="available" label="可用库存" width="100" /><el-table-column prop="shortage" label="缺口" width="100" fixed="right" />
    </el-table>
    <ListPagination :page="page" :total="filtered.length" @change="page = $event" />
    <template #footer><el-button :disabled="busy" @click="opened = false">取消</el-button><el-button type="primary" :loading="busy" :disabled="!selected.length" @click="generate">填写采购单（{{ selected.length }} 项）</el-button></template>
  </el-dialog>
  <ActionDialog :command="command" @close="command = null" @saved="saved" />
</template>
