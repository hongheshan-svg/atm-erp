<script setup lang="ts">
import type { Field, Row } from '../types'
import { defaults } from '../forms'
import { reactive } from 'vue'
import RemoteSelect from './RemoteSelect.vue'
defineProps<{ fields: Field[]; disabled?: boolean; readonly?: boolean }>()
const model = defineModel<Row>({ required: true })
const pages = reactive<Record<string, number>>({})
const start = (key: string) => Math.min(pages[key] || 0, Math.max(0, Math.ceil((model.value[key]?.length || 0) / 20) - 1)) * 20
const indices = (key: string) => Array.from({ length: Math.min(20, (model.value[key]?.length || 0) - start(key)) }, (_, i) => start(key) + i)
function readonlyValue(field: Field) {
  const value = model.value[field.key]
  if (field.options) return field.options.filter(option => (Array.isArray(value) ? value : [value]).includes(option.value)).map(option => option.label).join('、') || '—'
  return value === true ? '启用' : value === false ? '停用' : value == null || value === '' ? '—' : String(value)
}
</script>
<template>
  <div class="fields" :class="{ 'readonly-fields': readonly }">
    <template v-for="field in fields" :key="field.key">
      <fieldset v-if="field.type === 'rows'" class="row-list">
        <legend>{{ field.label }} · {{ model[field.key]?.length || 0 }} 行</legend>
        <p v-if="field.hint" class="form-hint">{{ field.hint }}</p>
        <el-table v-if="readonly" :data="model[field.key]" max-height="430" stripe>
          <el-table-column v-for="column in field.fields?.filter(c => !c.hidden)" :key="column.key" :label="column.label" :prop="column.key" min-width="140" show-overflow-tooltip />
        </el-table>
        <div v-for="i in readonly ? [] : indices(field.key)" :key="i" class="line-fields">
          <p class="line-number">第 {{ i + 1 }} 行</p>
          <FormFields v-model="model[field.key][i]" :fields="field.fields!" :disabled="disabled" />
          <el-button v-if="!disabled && !field.readonly" @click="model[field.key].splice(i, 1)">移除此行</el-button>
        </div>
        <div v-if="!readonly && model[field.key]?.length > 20"><button type="button" :disabled="start(field.key) === 0" @click="pages[field.key] = start(field.key) / 20 - 1">上一页明细</button> {{ start(field.key) + 1 }}–{{ Math.min(start(field.key) + 20, model[field.key].length) }} / {{ model[field.key].length }} <button type="button" :disabled="start(field.key) + 20 >= model[field.key].length" @click="pages[field.key] = start(field.key) / 20 + 1">下一页明细</button></div>
        <el-button v-if="!disabled && !field.readonly" @click="model[field.key].push(defaults(field.fields!)); pages[field.key] = Math.floor((model[field.key].length - 1) / 20)">添加行</el-button>
      </fieldset>
      <fieldset v-else-if="field.type === 'checks' && !field.hidden" class="role-checks" :disabled="disabled || field.readonly">
        <legend>{{ field.label }}</legend>
        <label v-for="option in field.options" :key="option.value">
          <input v-model="model[field.key]" type="checkbox" :value="option.value" /> {{ option.label }}
        </label>
        <small v-if="field.hint">{{ field.hint }}</small>
      </fieldset>
      <label v-else-if="!field.hidden" class="field" :class="{ 'field-wide': field.wide || field.type === 'textarea' }">
        <span>{{ field.label }}<small v-if="field.optional && !readonly">（选填）</small></span>
        <textarea v-if="readonly" :value="readonlyValue(field)" :aria-label="field.label" readonly rows="1" class="readonly-text" />
        <RemoteSelect v-else-if="field.remotePath" v-model="model[field.key]" :path="field.remotePath" :params="field.remoteParams" :accept="field.remoteFilter" :label="field.label" :required="!field.optional" :disabled="disabled || field.readonly" />
        <select
          :aria-label="field.label"
          v-else-if="field.type === 'select' || field.type === 'multi'"
          v-model="model[field.key]"
          :multiple="field.type === 'multi'"
          :disabled="disabled || field.readonly"
          :required="!field.optional"
        >
          <option v-if="field.type !== 'multi'" value="">请选择</option>
          <option v-for="option in field.options" :key="option.value" :value="option.value">
            {{ option.label }}
          </option>
        </select>
        <input
          :aria-label="field.label"
          v-else-if="field.type === 'boolean'"
          v-model="model[field.key]"
          type="checkbox"
          :disabled="disabled || field.readonly"
        />
        <input
          :aria-label="field.label"
          v-else-if="field.type === 'file'"
          type="file"
          :disabled="disabled || field.readonly"
          :required="!field.optional"
          @change="model[field.key] = ($event.target as HTMLInputElement).files?.[0]"
        />
        <textarea
          :aria-label="field.label"
          v-else-if="field.type === 'textarea'"
          v-model="model[field.key]"
          :disabled="disabled || field.readonly"
          :placeholder="field.placeholder"
          rows="4"
          :required="!field.optional"
        />
        <input
          :aria-label="field.label"
          v-else
          v-model="model[field.key]"
          :type="field.type === 'date' ? 'date' : field.type === 'password' ? 'password' : 'text'"
          :disabled="disabled || field.readonly"
          :required="!field.optional"
          :autocomplete="field.type === 'password' ? 'new-password' : 'off'"
          :placeholder="field.placeholder"
          :inputmode="field.numeric ? (field.numeric.signed ? 'text' : field.numeric.scale ? 'decimal' : 'numeric') : undefined"
        />
        <small v-if="field.hint && !readonly">{{ field.hint }}</small>
      </label>
    </template>
  </div>
</template>
<style scoped>
.readonly-fields input:not([type='checkbox']), .readonly-fields textarea, .readonly-fields select { border-color: transparent; background: transparent; color: #25364d; padding: 0; min-height: 24px; font-size: 14px; opacity: 1; -webkit-text-fill-color: #25364d; }
.readonly-fields .field > span { color: #64748b; font-size: 12px; }
.readonly-fields .field { gap: 4px; }
.readonly-fields .readonly-text { field-sizing: content; resize: none; line-height: 1.6; width: 100%; min-height: 26px; }
</style>
