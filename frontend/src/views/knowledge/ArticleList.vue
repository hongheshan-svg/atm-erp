<template>
  <div class="knowledge-container">
    <el-row :gutter="20">
      <!-- 左侧分类 -->
      <el-col :span="5">
        <el-card class="category-card">
          <template #header>
            <div class="card-header">
              <span>知识分类</span>
              <el-button size="small" @click="fetchCategories"><el-icon><Refresh /></el-icon></el-button>
            </div>
          </template>
          <el-tree
            :data="categoryTree"
            :props="{ label: 'name', children: 'children' }"
            node-key="id"
            @node-click="handleCategoryClick"
            highlight-current
            default-expand-all
          >
            <template #default="{ node, data }">
              <span class="tree-node">
                <span>{{ node.label }}</span>
                <span class="article-count">({{ data.article_count || 0 }})</span>
              </span>
            </template>
          </el-tree>
        </el-card>
      </el-col>

      <!-- 右侧内容 -->
      <el-col :span="19">
        <!-- 搜索和统计 -->
        <el-card class="search-card">
          <el-row :gutter="20" align="middle">
            <el-col :span="12">
              <el-input
                v-model="searchKeyword"
                placeholder="搜索知识文章..."
                size="large"
                clearable
                @keyup.enter="handleSearch"
              >
                <template #prefix><el-icon><Search /></el-icon></template>
                <template #append>
                  <el-button @click="handleSearch">搜索</el-button>
                </template>
              </el-input>
            </el-col>
            <el-col :span="12">
              <div class="quick-stats">
                <div class="stat-item">
                  <span class="stat-value">{{ statistics.total }}</span>
                  <span class="stat-label">文章总数</span>
                </div>
                <div class="stat-item">
                  <span class="stat-value">{{ statistics.published }}</span>
                  <span class="stat-label">已发布</span>
                </div>
                <el-button type="primary" @click="handleCreate"><el-icon><Plus /></el-icon> 新建文章</el-button>
              </div>
            </el-col>
          </el-row>
        </el-card>

        <!-- 筛选 -->
        <el-card class="filter-card">
          <div class="filter-area">
            <el-radio-group v-model="queryParams.article_type" @change="handleFilter">
              <el-radio-button label="">全部</el-radio-button>
              <el-radio-button label="SOLUTION">解决方案</el-radio-button>
              <el-radio-button label="STANDARD">标准规范</el-radio-button>
              <el-radio-button label="TUTORIAL">教程指南</el-radio-button>
              <el-radio-button label="FAQ">常见问题</el-radio-button>
              <el-radio-button label="CASE">案例分享</el-radio-button>
              <el-radio-button label="LESSON">经验教训</el-radio-button>
            </el-radio-group>
            <el-select v-model="queryParams.status" placeholder="状态" clearable @change="handleFilter">
              <el-option label="草稿" value="DRAFT" />
              <el-option label="已发布" value="PUBLISHED" />
            </el-select>
          </div>
        </el-card>

        <!-- 文章列表 -->
        <div class="article-list">
          <el-card v-for="article in articles" :key="article.id" class="article-card" @click="handleView(article)">
            <div class="article-header">
              <el-tag :type="getTypeTagType(article.article_type)" size="small">{{ article.article_type_display }}</el-tag>
              <span class="article-date">{{ formatDate(article.created_at) }}</span>
            </div>
            <h3 class="article-title">{{ article.title }}</h3>
            <p class="article-summary">{{ article.summary }}</p>
            <div class="article-footer">
              <div class="tags">
                <el-tag v-for="tag in (article.tags || []).slice(0, 3)" :key="tag" size="small" type="info">{{ tag }}</el-tag>
              </div>
              <div class="meta">
                <span><el-icon><View /></el-icon> {{ article.view_count }}</span>
                <span><el-icon><Star /></el-icon> {{ article.like_count }}</span>
                <span>{{ article.author_name }}</span>
              </div>
            </div>
          </el-card>
        </div>

        <el-pagination
          v-model:current-page="queryParams.page"
          v-model:page-size="queryParams.page_size"
          :total="total"
          :page-sizes="[12, 24, 48]"
          layout="total, sizes, prev, pager, next"
          style="margin-top: 20px; justify-content: center"
          @size-change="fetchData"
          @current-change="fetchData"
        />
      </el-col>
    </el-row>

    <!-- 新建/编辑对话框 -->
    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="800px" destroy-on-close>
      <el-form ref="formRef" :model="formData" :rules="formRules" label-width="80px">
        <el-form-item label="标题" prop="title">
          <el-input v-model="formData.title" />
        </el-form-item>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="分类">
              <el-select v-model="formData.category" placeholder="选择分类" style="width: 100%">
                <el-option v-for="c in flatCategories" :key="c.id" :label="c.name" :value="c.id" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="类型">
              <el-select v-model="formData.article_type" style="width: 100%">
                <el-option label="解决方案" value="SOLUTION" />
                <el-option label="标准规范" value="STANDARD" />
                <el-option label="教程指南" value="TUTORIAL" />
                <el-option label="常见问题" value="FAQ" />
                <el-option label="案例分享" value="CASE" />
                <el-option label="经验教训" value="LESSON" />
                <el-option label="其他" value="OTHER" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="摘要">
          <el-input v-model="formData.summary" type="textarea" :rows="2" />
        </el-form-item>
        <el-form-item label="内容" prop="content">
          <el-input v-model="formData.content" type="textarea" :rows="12" />
        </el-form-item>
        <el-form-item label="标签">
          <el-select v-model="formData.tags" multiple filterable allow-create style="width: 100%" placeholder="输入后回车添加">
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button @click="handleSaveDraft" :loading="submitting">保存草稿</el-button>
        <el-button type="primary" @click="handlePublish" :loading="submitting">发布</el-button>
      </template>
    </el-dialog>

    <!-- 文章详情抽屉 -->
    <el-drawer v-model="detailVisible" title="文章详情" size="60%">
      <div v-if="currentArticle" class="article-detail">
        <div class="detail-header">
          <el-tag :type="getTypeTagType(currentArticle.article_type)">{{ currentArticle.article_type_display }}</el-tag>
          <el-tag v-if="currentArticle.status === 'DRAFT'" type="info">草稿</el-tag>
        </div>
        <h2 class="detail-title">{{ currentArticle.title }}</h2>
        <div class="detail-meta">
          <span>作者: {{ currentArticle.author_name }}</span>
          <span>发布时间: {{ formatDate(currentArticle.published_at || currentArticle.created_at) }}</span>
          <span><el-icon><View /></el-icon> {{ currentArticle.view_count }}</span>
          <span><el-icon><Star /></el-icon> {{ currentArticle.like_count }}</span>
        </div>
        <el-divider />
        <div class="detail-content" v-html="formatContent(currentArticle.content)"></div>
        <el-divider />
        <div class="detail-tags">
          <el-tag v-for="tag in (currentArticle.tags || [])" :key="tag" type="info">{{ tag }}</el-tag>
        </div>
        <div class="detail-actions">
          <el-button @click="handleLike" :loading="liking"><el-icon><Star /></el-icon> 点赞</el-button>
          <el-button @click="handleEdit(currentArticle)"><el-icon><Edit /></el-icon> 编辑</el-button>
        </div>
      </div>
    </el-drawer>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Plus, Search, Refresh, View, Star, Edit } from '@element-plus/icons-vue'
import {
  getKnowledgeArticleList,
  getKnowledgeArticle,
  getKnowledgeArticleStatistics,
  getKnowledgeCategoryTree,
  createKnowledgeArticle,
  updateKnowledgeArticle,
  publishKnowledgeArticle,
  likeKnowledgeArticle,
  searchKnowledgeArticles
} from '@/api/projects/knowledge'

const loading = ref(false)
const submitting = ref(false)
const liking = ref(false)
const dialogVisible = ref(false)
const detailVisible = ref(false)
const dialogTitle = ref('新建文章')
const searchKeyword = ref('')
const articles = ref([])
const total = ref(0)
const categoryTree = ref([])
const currentArticle = ref(null)

const statistics = reactive({
  total: 0,
  published: 0,
  draft: 0
})

const queryParams = reactive({
  search: '',
  category: '',
  article_type: '',
  status: '',
  page: 1,
  page_size: 12
})

const formRef = ref(null)
const formData = reactive({
  id: null,
  title: '',
  category: null,
  article_type: 'SOLUTION',
  summary: '',
  content: '',
  tags: []
})

const formRules = {
  title: [{ required: true, message: '请输入标题', trigger: 'blur' }],
  content: [{ required: true, message: '请输入内容', trigger: 'blur' }]
}

const flatCategories = computed(() => {
  const flatten = (items, result = []) => {
    items.forEach(item => {
      result.push(item)
      if (item.children?.length) {
        flatten(item.children, result)
      }
    })
    return result
  }
  return flatten(categoryTree.value)
})

const getTypeTagType = (type) => {
  const map = {
    SOLUTION: 'success',
    STANDARD: '',
    TUTORIAL: 'warning',
    FAQ: 'info',
    CASE: '',
    LESSON: 'danger'
  }
  return map[type] || 'info'
}

const formatDate = (dateStr) => {
  if (!dateStr) return ''
  return new Date(dateStr).toLocaleDateString('zh-CN')
}

const formatContent = (content) => {
  if (!content) return ''
  // 简单处理Markdown格式
  return content
    .replace(/## (.*)/g, '<h3>$1</h3>')
    .replace(/# (.*)/g, '<h2>$1</h2>')
    .replace(/\n/g, '<br>')
}

const fetchData = async () => {
  loading.value = true
  try {
    const res = await getKnowledgeArticleList(queryParams)
    articles.value = res.data.results || res.data
    total.value = res.data.count || articles.value.length
  } catch (error) {
    console.error('获取数据失败', error)
  } finally {
    loading.value = false
  }
}

const fetchCategories = async () => {
  try {
    const res = await getKnowledgeCategoryTree()
    categoryTree.value = res.data
  } catch (error) {
    console.error('获取分类失败', error)
  }
}

const fetchStatistics = async () => {
  try {
    const res = await getKnowledgeArticleStatistics()
    Object.assign(statistics, res.data)
  } catch (error) {
    console.error('获取统计失败', error)
  }
}

const handleSearch = async () => {
  if (searchKeyword.value) {
    try {
      const res = await searchKnowledgeArticles(searchKeyword.value)
      articles.value = res.data
      total.value = articles.value.length
    } catch (error) {
      console.error('搜索失败', error)
    }
  } else {
    fetchData()
  }
}

const handleFilter = () => {
  queryParams.page = 1
  fetchData()
}

const handleCategoryClick = (data) => {
  queryParams.category = data.id
  queryParams.page = 1
  fetchData()
}

const handleCreate = () => {
  dialogTitle.value = '新建文章'
  Object.assign(formData, {
    id: null,
    title: '',
    category: null,
    article_type: 'SOLUTION',
    summary: '',
    content: '',
    tags: []
  })
  dialogVisible.value = true
}

const handleEdit = (article) => {
  dialogTitle.value = '编辑文章'
  Object.assign(formData, article)
  dialogVisible.value = true
  detailVisible.value = false
}

const handleView = async (article) => {
  try {
    const res = await getKnowledgeArticle(article.id)
    currentArticle.value = res.data
    detailVisible.value = true
  } catch (error) {
    ElMessage.error('获取详情失败')
  }
}

const handleSaveDraft = async () => {
  const valid = await formRef.value.validate()
  if (!valid) return

  submitting.value = true
  try {
    const data = { ...formData, status: 'DRAFT' }
    if (formData.id) {
      await updateKnowledgeArticle(formData.id, data)
      ElMessage.success('保存成功')
    } else {
      await createKnowledgeArticle(data)
      ElMessage.success('创建成功')
    }
    dialogVisible.value = false
    fetchData()
    fetchStatistics()
  } catch (error) {
    ElMessage.error('保存失败')
  } finally {
    submitting.value = false
  }
}

const handlePublish = async () => {
  const valid = await formRef.value.validate()
  if (!valid) return

  submitting.value = true
  try {
    if (formData.id) {
      await updateKnowledgeArticle(formData.id, formData)
      await publishKnowledgeArticle(formData.id)
    } else {
      const res = await createKnowledgeArticle(formData)
      await publishKnowledgeArticle(res.data.id)
    }
    ElMessage.success('发布成功')
    dialogVisible.value = false
    fetchData()
    fetchStatistics()
  } catch (error) {
    ElMessage.error('发布失败')
  } finally {
    submitting.value = false
  }
}

const handleLike = async () => {
  if (!currentArticle.value) return
  liking.value = true
  try {
    const res = await likeKnowledgeArticle(currentArticle.value.id)
    currentArticle.value.like_count = res.data.like_count
    ElMessage.success('点赞成功')
  } catch (error) {
    ElMessage.error('点赞失败')
  } finally {
    liking.value = false
  }
}

onMounted(() => {
  fetchData()
  fetchCategories()
  fetchStatistics()
})
</script>

<style scoped lang="scss">
.knowledge-container {
  padding: 20px;
  background: #f5f7fa;
  min-height: 100vh;
}

.category-card {
  position: sticky;
  top: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.tree-node {
  display: flex;
  align-items: center;
  gap: 8px;
  
  .article-count {
    color: #909399;
    font-size: 12px;
  }
}

.search-card {
  margin-bottom: 16px;
}

.quick-stats {
  display: flex;
  align-items: center;
  gap: 24px;
  justify-content: flex-end;
  
  .stat-item {
    text-align: center;
    
    .stat-value {
      font-size: 24px;
      font-weight: 600;
      color: #303133;
    }
    
    .stat-label {
      font-size: 12px;
      color: #909399;
    }
  }
}

.filter-card {
  margin-bottom: 16px;
}

.filter-area {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.article-list {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(350px, 1fr));
  gap: 16px;
}

.article-card {
  cursor: pointer;
  transition: all 0.2s;
  
  &:hover {
    box-shadow: 0 4px 12px rgba(0,0,0,0.1);
    transform: translateY(-2px);
  }
}

.article-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
  
  .article-date {
    font-size: 12px;
    color: #909399;
  }
}

.article-title {
  margin: 0 0 8px;
  font-size: 16px;
  color: #303133;
  line-height: 1.4;
}

.article-summary {
  font-size: 14px;
  color: #606266;
  line-height: 1.6;
  margin: 0 0 12px;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.article-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  
  .tags {
    display: flex;
    gap: 4px;
  }
  
  .meta {
    display: flex;
    gap: 12px;
    font-size: 12px;
    color: #909399;
    
    span {
      display: flex;
      align-items: center;
      gap: 4px;
    }
  }
}

.article-detail {
  padding: 0 20px;
}

.detail-header {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
}

.detail-title {
  margin: 0 0 12px;
  font-size: 24px;
  color: #303133;
}

.detail-meta {
  display: flex;
  gap: 20px;
  font-size: 14px;
  color: #909399;
  
  span {
    display: flex;
    align-items: center;
    gap: 4px;
  }
}

.detail-content {
  font-size: 15px;
  line-height: 1.8;
  color: #303133;
}

.detail-tags {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.detail-actions {
  margin-top: 20px;
  display: flex;
  gap: 12px;
}
</style>
