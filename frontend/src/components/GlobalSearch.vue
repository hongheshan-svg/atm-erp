<template>
  <div class="global-search">
    <el-autocomplete
      v-model="searchQuery"
      :fetch-suggestions="fetchSuggestions"
      placeholder="搜索物料、客户、项目..."
      :trigger-on-focus="false"
      clearable
      size="large"
      style="width: 400px;"
      @select="handleSelect"
      @keyup.enter="performSearch"
    >
      <template #prefix>
        <el-icon><Search /></el-icon>
      </template>
      <template #default="{ item }">
        <div class="suggestion-item">
          <el-icon class="item-icon">
            <component :is="getIcon(item.type)" />
          </el-icon>
          <span class="item-text">{{ item.text }}</span>
          <span class="item-meta" v-if="item.meta">{{ item.meta }}</span>
        </div>
      </template>
    </el-autocomplete>

    <!-- Search Results Dialog -->
    <el-dialog
      v-model="resultsVisible"
      title="搜索结果"
      width="80%"
      top="5vh"
    >
      <div class="search-results" v-loading="loading">
        <el-tabs v-model="activeTab">
          <el-tab-pane label="全部" name="all">
            <div class="results-summary">
              找到 {{ totalHits }} 条结果
            </div>
            
            <!-- Items Results -->
            <div class="result-section" v-if="results.items && results.items.total > 0">
              <h3>
                <el-icon><Box /></el-icon>
                物料 ({{ results.items.total }})
              </h3>
              <el-table :data="results.items.hits" stripe>
                <el-table-column prop="sku" label="物料编码" width="120" />
                <el-table-column prop="name" label="名称" />
                <el-table-column prop="specification" label="规格" />
                <el-table-column label="操作" width="100">
                  <template #default="{ row }">
                    <el-button size="small" @click="viewDetails(row, 'item')">查看</el-button>
                  </template>
                </el-table-column>
              </el-table>
            </div>

            <!-- Customers Results -->
            <div class="result-section" v-if="results.customers && results.customers.total > 0">
              <h3>
                <el-icon><Avatar /></el-icon>
                客户 ({{ results.customers.total }})
              </h3>
              <el-table :data="results.customers.hits" stripe>
                <el-table-column prop="code" label="编码" width="120" />
                <el-table-column prop="name" label="名称" />
                <el-table-column prop="contact_person" label="联系人" />
                <el-table-column prop="phone" label="电话" />
                <el-table-column label="操作" width="100">
                  <template #default="{ row }">
                    <el-button size="small" @click="viewDetails(row, 'customer')">查看</el-button>
                  </template>
                </el-table-column>
              </el-table>
            </div>

            <!-- Projects Results -->
            <div class="result-section" v-if="results.projects && results.projects.total > 0">
              <h3>
                <el-icon><Management /></el-icon>
                项目 ({{ results.projects.total }})
              </h3>
              <el-table :data="results.projects.hits" stripe>
                <el-table-column prop="code" label="编码" width="120" />
                <el-table-column prop="name" label="名称" />
                <el-table-column prop="status" label="状态" width="100">
                  <template #default="{ row }">
                    <el-tag>{{ row.status }}</el-tag>
                  </template>
                </el-table-column>
                <el-table-column label="操作" width="100">
                  <template #default="{ row }">
                    <el-button size="small" @click="viewDetails(row, 'project')">查看</el-button>
                  </template>
                </el-table-column>
              </el-table>
            </div>

            <!-- No Results -->
            <el-empty v-if="totalHits === 0" description="未找到相关结果" />
          </el-tab-pane>
        </el-tabs>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { Search, Box, Avatar, Management, ShoppingCart } from '@element-plus/icons-vue'
import { useRouter } from 'vue-router'
import request from '@/utils/request'

const router = useRouter()
const searchQuery = ref('')
const resultsVisible = ref(false)
const loading = ref(false)
const activeTab = ref('all')
const results = ref({})

const totalHits = computed(() => {
  return Object.values(results.value).reduce((sum, r) => sum + (r.total || 0), 0)
})

const getIcon = (type) => {
  const icons = {
    'items': Box,
    'customers': Avatar,
    'suppliers': ShoppingCart,
    'projects': Management
  }
  return icons[type] || Box
}

const fetchSuggestions = async (queryString, cb) => {
  if (queryString.length < 2) {
    cb([])
    return
  }

  try {
    const { data } = await request.get('/core/search/suggest/', {
      params: {
        q: queryString,
        type: 'items',
        limit: 8
      }
    })
    cb(data.suggestions || [])
  } catch (error) {
    console.error('Failed to fetch suggestions:', error)
    cb([])
  }
}

const handleSelect = (item) => {
  viewDetails(item, item.type)
}

const performSearch = async () => {
  if (!searchQuery.value || searchQuery.value.length < 2) {
    return
  }

  loading.value = true
  resultsVisible.value = true

  try {
    const { data } = await request.get('/core/search/search/', {
      params: {
        q: searchQuery.value,
        limit: 20
      }
    })
    results.value = data.results || {}
  } catch (error) {
    console.error('Search failed:', error)
  } finally {
    loading.value = false
  }
}

const viewDetails = (item, type) => {
  // Navigate to detail page based on type
  const routes = {
    'item': `/items/${item.id}`,
    'customer': `/customers/${item.id}`,
    'supplier': `/suppliers/${item.id}`,
    'project': `/projects/${item.id}`
  }

  const route = routes[type]
  if (route) {
    resultsVisible.value = false
    router.push(route)
  }
}
</script>

<style scoped>
.global-search {
  display: flex;
  align-items: center;
}

.suggestion-item {
  display: flex;
  align-items: center;
  padding: 5px 0;
}

.item-icon {
  margin-right: 10px;
  color: #409EFF;
}

.item-text {
  flex: 1;
  font-weight: 500;
}

.item-meta {
  color: #909399;
  font-size: 12px;
}

.search-results {
  min-height: 400px;
}

.results-summary {
  margin-bottom: 20px;
  padding: 15px;
  background: #f5f7fa;
  border-radius: 4px;
  font-size: 16px;
  font-weight: 500;
}

.result-section {
  margin-bottom: 30px;
}

.result-section h3 {
  display: flex;
  align-items: center;
  margin-bottom: 15px;
  font-size: 18px;
  color: #303133;
}

.result-section h3 .el-icon {
  margin-right: 8px;
  color: #409EFF;
}
</style>

