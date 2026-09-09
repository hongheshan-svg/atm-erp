<script setup lang="ts">
import type { Field, Row } from '../types'
import { defaults } from '../forms'
defineProps<{ fields: Field[]; disabled?: boolean }>()
const model = defineModel<Row>({ required: true })
</script>
<template>
  <div class="fields">
    <template v-for="field in fields" :key="field.key">
      <fieldset v-if="field.type === 'rows'" class="row-list">
        <legend>{{ field.label }}</legend>
        <div v-for="(_, i) in model[field.key]" :key="i" class="line-fields">
          <FormFields v-model="model[field.key][i]" :fields="field.fields!" :disabled="disabled" />
          <el-button v-if="!disabled" @click="model[field.key].splice(i, 1)">移除此行</el-button>
        </div>
        <el-button v-if="!disabled" @click="model[field.key].push(defaults(field.fields!))">添加行</el-button>
      </fieldset>
      <label v-else class="field">
        <span>{{ field.label }}<small v-if="field.optional">（选填）</small></span>
        <select
          :aria-label="field.label"
          v-if="field.type === 'select' || field.type === 'multi'"
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
