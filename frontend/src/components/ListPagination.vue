<script setup lang="ts">
import { computed } from 'vue'
import { pageSize as globalSize, pageSizes as allSizes, setPageSize } from '../pagination'
const props = withDefaults(defineProps<{ page: number; total: number; minSize?: number }>(), { minSize: 0 })
// 调用方给了每页下限时，只提供不低于下限的选项，显示值与实际请求一致。
const pageSizes = computed(() => allSizes.filter(size => size >= props.minSize))
const pageSize = computed(() => Math.max(globalSize.value, props.minSize))
const emit = defineEmits<{ change: [page: number] }>()
</script>
<template>
  <div class="list-pagination">
    <label>每页显示
      <select :value="pageSize" aria-label="每页显示条目" @change="setPageSize(Number(($event.target as HTMLSelectElement).value))">
        <option v-for="size in pageSizes" :key="size" :value="size">{{ size }} 条</option>
      </select>
    </label>
    <el-pagination :current-page="page" :page-size="pageSize" :total="total" :pager-count="5" layout="prev,pager,next,total" @current-change="emit('change', $event)" />
  </div>
</template>
