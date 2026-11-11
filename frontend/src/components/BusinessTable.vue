<script setup lang="ts">
import { useSlots } from 'vue'
import TableScroll from './TableScroll.vue'

defineOptions({ inheritAttrs: false })
// numberWidth：序号列宽，默认 70；列多的明细表（如 BOM 采购视图）可收窄。
const props = withDefaults(defineProps<{ label?: string; rowOffset?: number; numbered?: boolean; numberWidth?: number }>(), { label: '表格', rowOffset: 0, numbered: true, numberWidth: 70 })
const slots = useSlots()
const numberOf = (index: number) => props.rowOffset + index + 1
</script>
<template>
  <TableScroll :label="label">
    <template #default="{ narrow }">
      <el-table v-bind="$attrs" scrollbar-always-on>
        <el-table-column v-if="numbered" type="index" label="序号" :width="numberWidth" :index="numberOf" :fixed="narrow ? undefined : 'left'" class-name="business-row-number" />
        <slot />
        <template v-for="name in Object.keys(slots).filter(key => key !== 'default')" :key="name" #[name]="scope"><slot :name="name" v-bind="scope || {}" /></template>
      </el-table>
    </template>
  </TableScroll>
</template>
