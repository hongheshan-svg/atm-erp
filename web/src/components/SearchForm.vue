<script setup lang="ts">
// 通用内联搜索表单容器:默认插槽放字段,自带查询/重置按钮。
const emit = defineEmits<{
  search: []
  reset: []
}>()
</script>

<template>
  <el-form inline class="search-form" @submit.prevent>
    <slot />
    <el-form-item>
      <el-button type="primary" @click="emit('search')">查询</el-button>
      <el-button @click="emit('reset')">重置</el-button>
    </el-form-item>
  </el-form>
</template>

<style scoped>
.search-form {
  margin-bottom: 8px;
}
</style>
