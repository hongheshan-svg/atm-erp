<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import PageHeader from '@/components/PageHeader.vue'
import SearchForm from '@/components/SearchForm.vue'
import { useUsersQuery } from '@/api/accounts'
import type { User, UserListQuery } from '@/types'

// ===== 查询条件与分页(用户列表只读)=====
const filters = reactive({ keyword: '' })
const isActiveFilter = ref<boolean | undefined>(undefined)
const page = ref(1)
const pageSize = ref(20)

const submittedQuery = reactive<UserListQuery>({ keyword: '' })

const query = computed<UserListQuery>(() => ({
  keyword: submittedQuery.keyword,
  is_active: submittedQuery.is_active,
  page: page.value,
  page_size: pageSize.value
}))

const { data, isFetching } = useUsersQuery(query)

const rows = computed<User[]>(() => data.value?.results ?? [])
const total = computed(() => data.value?.count ?? 0)

function handleSearch() {
  submittedQuery.keyword = filters.keyword
  submittedQuery.is_active = isActiveFilter.value
  page.value = 1
}

function handleReset() {
  filters.keyword = ''
  isActiveFilter.value = undefined
  handleSearch()
}

function handlePageChange(val: number) {
  page.value = val
}

function handleSizeChange(val: number) {
  pageSize.value = val
  page.value = 1
}

// 拼接姓名(姓 + 名,空则回退 username)。
function displayName(row: User): string {
  const name = `${row.last_name}${row.first_name}`
  return name || row.username
}
</script>

<template>
  <div>
    <PageHeader title="用户列表" subtitle="accounts / users(只读)" />

    <SearchForm @search="handleSearch" @reset="handleReset">
      <el-form-item label="关键字">
        <el-input v-model="filters.keyword" placeholder="用户名/姓名" clearable @keyup.enter="handleSearch" />
      </el-form-item>
      <el-form-item label="启用状态">
        <el-select v-model="isActiveFilter" placeholder="全部" clearable style="width: 120px">
          <el-option label="启用" :value="true" />
          <el-option label="停用" :value="false" />
        </el-select>
      </el-form-item>
    </SearchForm>

    <el-table v-loading="isFetching" :data="rows" border stripe>
      <el-table-column prop="username" label="用户名" width="160" />
      <el-table-column label="姓名" width="140">
        <template #default="{ row }">{{ displayName(row) }}</template>
      </el-table-column>
      <el-table-column prop="employee_id" label="工号" width="140" />
      <el-table-column prop="email" label="邮箱" min-width="180" />
      <el-table-column prop="phone" label="手机" width="140" />
      <el-table-column prop="position" label="岗位" width="140" />
      <el-table-column label="状态" width="100">
        <template #default="{ row }">
          <el-tag :type="row.is_active ? 'success' : 'info'">{{ row.is_active ? '启用' : '停用' }}</el-tag>
        </template>
      </el-table-column>
    </el-table>

    <el-pagination
      class="pager"
      layout="total, prev, pager, next, sizes"
      :total="total"
      :current-page="page"
      :page-size="pageSize"
      :page-sizes="[10, 20, 50, 100]"
      @current-change="handlePageChange"
      @size-change="handleSizeChange"
    />
  </div>
</template>

<style scoped>
.pager {
  margin-top: 16px;
  justify-content: flex-end;
}
</style>
