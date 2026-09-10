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
</script>
<template>
  <div class="fields">
    <template v-for="field in fields" :key="field.key">
      <fieldset v-if="field.type === 'rows'" class="row-list">
        <legend>{{ field.label }}</legend>
        <el-table v-if="readonly" :data="model[field.key]" max-height="430" stripe>
          <el-table-column v-for="column in field.fields?.filter(c => !c.hidden)" :key="column.key" :label="column.label" :prop="column.key" min-width="140" show-overflow-tooltip />
        </el-table>
        <div v-for="i in readonly ? [] : indices(field.key)" :key="i" class="line-fields">
          <FormFields v-model="model[field.key][i]" :fields="field.fields!" :disabled="disabled" />
          <el-button v-if="!disabled && !field.readonly" @click="model[field.key].splice(i, 1)">移除此行</el-button>
        </div>
        <div v-if="!readonly && model[field.key]?.length > 20"><button type="button" :disabled="start(field.key) === 0" @click="pages[field.key] = start(field.key) / 20 - 1">上一页明细</button> {{ start(field.key) + 1 }}–{{ Math.min(start(field.key) + 20, model[field.key].length) }} / {{ model[field.key].length }} <button type="button" :disabled="start(field.key) + 20 >= model[field.key].length" @click="pages[field.key] = start(field.key) / 20 + 1">下一页明细</button></div>
        <el-button v-if="!disabled && !field.readonly" @click="model[field.key].push(defaults(field.fields!))">添加行</el-button>
      </fieldset>
      <fieldset v-else-if="field.type === 'checks' && !field.hidden" class="role-checks" :disabled="disabled || field.readonly">
        <legend>{{ field.label }}</legend>
        <label v-for="option in field.options" :key="option.value">
          <input v-model="model[field.key]" type="checkbox" :value="option.value" /> {{ option.label }}
        </label>
        <small v-if="field.hint">{{ field.hint }}</small>
      </fieldset>
      <label v-else-if="!field.hidden" class="field">
        <span>{{ field.label }}<small v-if="field.optional">（选填）</small></span>
        <RemoteSelect v-if="field.remotePath" v-model="model[field.key]" :path="field.remotePath" :params="field.remoteParams" :accept="field.remoteFilter" :label="field.label" :required="!field.optional" :disabled="disabled || field.readonly" />
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
          :disabled="disabled"
          :required="!field.optional"
          @change="model[field.key] = ($event.target as HTMLInputElement).files?.[0]"
        />
        <textarea
          :aria-label="field.label"
          v-else-if="field.type === 'textarea'"
          v-model="model[field.key]"
          :disabled="disabled"
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
        />
        <small v-if="field.hint">{{ field.hint }}</small>
      </label>
    </template>
  </div>
</template>
