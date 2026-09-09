<script setup lang="ts">
import { pageSize, pageSizes, setPageSize } from '../pagination'
defineProps<{ page: number; total: number }>()
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
