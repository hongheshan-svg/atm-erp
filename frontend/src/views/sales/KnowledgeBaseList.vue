<template>
  <div class="knowledge-base-list">
    <!-- 搜索和筛选 -->
    <el-card class="search-card">
      <el-row :gutter="16">
        <el-col :span="16">
          <el-input v-model="searchKeyword" placeholder="搜索知识库文章..." size="large" clearable
                    @keyup.enter="loadArticles">
            <template #prefix><el-icon><Search /></el-icon></template>
            <template #append>
              <el-button type="primary" @click="loadArticles">搜索</el-button>
            </template>
          </el-input>
        </el-col>
        <el-col :span="8">
          <el-select v-model="categoryFilter" placeholder="分类筛选" clearable style="width: 100%"
                     @change="loadArticles">
            <el-option label="故障排除" value="TROUBLESHOOTING" />
            <el-option label="操作指南" value="HOW_TO" />
            <el-option label="常见问题" value="FAQ" />
            <el-option label="技术规格" value="SPECIFICATION" />
            <el-option label="最佳实践" value="BEST_PRACTICE" />
          </el-select>
        </el-col>
      </el-row>
    </el-card>

    <el-row :gutter="16" style="margin-top: 16px">
      <!-- 文章列表 -->
      <el-col :span="18">
        <el-card>
          <template #header>
            <div class="card-header">
              <span>知识库文章 ({{ pagination.total }})</span>
              <el-button type="primary" @click="showCreateDialog = true">
                <el-icon><Plus /></el-icon>新建文章
              </el-button>
            </div>
          </template>

          <div v-loading="loading" class="article-list">
            <div v-for="article in articles" :key="article.id" class="article-item" @click="viewArticle(article)">
              <div class="article-header">
                <el-tag :type="getCategoryType(article.category)" size="small">{{ article.category_display }}</el-tag>
                <span class="article-title">{{ article.title }}</span>
                <el-tag v-if="article.is_featured" type="warning" size="small">精选</el-tag>
              </div>
              <div class="article-summary">{{ article.summary || truncate(article.content, 150) }}</div>
              <div class="article-meta">
                <span><el-icon><User /></el-icon> {{ article.author_name }}</span>
                <span><el-icon><Clock /></el-icon> {{ formatDate(article.updated_at) }}</span>
                <span><el-icon><View /></el-icon> {{ article.view_count }}</span>
                <span><el-icon><Star /></el-icon> {{ article.helpful_count }}</span>
              </div>
              <div class="article-tags">
                <el-tag v-for="tag in article.tags" :key="tag" size="small" type="info">{{ tag }}</el-tag>
              </div>
            </div>

            <el-empty v-if="!loading && articles.length === 0" description="暂无文章" />
          </div>

          <el-pagination
            v-model:current-page="pagination.page"
            v-model:page-size="pagination.pageSize"
            :total="pagination.total"
            :page-sizes="[10, 20, 50]"
            layout="total, sizes, prev, pager, next"
            @size-change="loadArticles"
            @current-change="loadArticles"
            style="margin-top: 16px; justify-content: flex-end"
          />
        </el-card>
      </el-col>

      <!-- 侧边栏 -->
      <el-col :span="6">
        <el-card class="sidebar-card">
          <template #header>热门文章</template>
          <div v-for="article in popularArticles" :key="article.id" class="popular-item" @click="viewArticle(article)">
            <span class="popular-title">{{ article.title }}</span>
            <span class="popular-views">{{ article.view_count }}次查看</span>
          </div>
        </el-card>

        <el-card class="sidebar-card" style="margin-top: 16px">
          <template #header>热门标签</template>
          <div class="tag-cloud">
            <el-tag v-for="tag in popularTags" :key="tag.name" class="tag-item" 
                    @click="searchByTag(tag.name)" style="cursor: pointer">
              {{ tag.name }} ({{ tag.count }})
            </el-tag>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 新建文章对话框 -->
    <el-dialog v-model="showCreateDialog" title="新建知识库文章" width="800px">
      <el-form :model="articleForm" :rules="articleRules" ref="articleFormRef" label-width="80px">
        <el-form-item label="标题" prop="title">
          <el-input v-model="articleForm.title" placeholder="文章标题" />
        </el-form-item>
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="分类" prop="category">
              <el-select v-model="articleForm.category" style="width: 100%">
                <el-option label="故障排除" value="TROUBLESHOOTING" />
                <el-option label="操作指南" value="HOW_TO" />
                <el-option label="常见问题" value="FAQ" />
                <el-option label="技术规格" value="SPECIFICATION" />
                <el-option label="最佳实践" value="BEST_PRACTICE" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="标签">
              <el-select v-model="articleForm.tags" multiple filterable allow-create
                         placeholder="输入标签" style="width: 100%" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="摘要">
          <el-input v-model="articleForm.summary" type="textarea" :rows="2" placeholder="文章摘要（可选）" />
        </el-form-item>
        <el-form-item label="内容" prop="content">
          <el-input v-model="articleForm.content" type="textarea" :rows="15" placeholder="文章内容，支持Markdown格式" />
        </el-form-item>
        <el-form-item label="适用设备">
          <el-input v-model="articleForm.applicable_equipment" placeholder="适用的设备型号（多个用逗号分隔）" />
        </el-form-item>
        <el-form-item label="选项">
          <el-checkbox v-model="articleForm.is_featured">设为精选</el-checkbox>
          <el-checkbox v-model="articleForm.is_public">公开可见</el-checkbox>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreateDialog = false">取消</el-button>
        <el-button @click="saveDraft">保存草稿</el-button>
        <el-button type="primary" @click="publishArticle" :loading="submitting">发布</el-button>
      </template>
    </el-dialog>

    <!-- 文章详情抽屉 -->
    <el-drawer v-model="showDetailDrawer" :title="currentArticle?.title" size="60%">
      <template v-if="currentArticle">
        <div class="article-detail">
          <div class="detail-meta">
            <el-tag :type="getCategoryType(currentArticle.category)">{{ currentArticle.category_display }}</el-tag>
            <span>作者: {{ currentArticle.author_name }}</span>
            <span>更新于: {{ formatDate(currentArticle.updated_at) }}</span>
            <span>{{ currentArticle.view_count }}次查看</span>
          </div>
          
          <el-divider />
          
          <div class="detail-content" v-html="renderMarkdown(currentArticle.content)"></div>
          
          <el-divider />
          
          <div class="detail-footer">
            <span>这篇文章对您有帮助吗？</span>
            <el-button-group>
              <el-button @click="markHelpful(true)">
                <el-icon><Check /></el-icon> 有帮助 ({{ currentArticle.helpful_count }})
              </el-button>
              <el-button @click="markHelpful(false)">
                <el-icon><Close /></el-icon> 没帮助 ({{ currentArticle.not_helpful_count }})
              </el-button>
            </el-button-group>
          </div>
        </div>
      </template>
    </el-drawer>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Search, Plus, User, Clock, View, Star, Check, Close } from '@element-plus/icons-vue'
import { getKnowledgeArticles, getKnowledgeArticle, getPopularArticles, getKnowledgeTags, createKnowledgeArticle, viewKnowledgeArticle, feedbackKnowledgeArticle } from '@/api/sales'

const loading = ref(false)
const submitting = ref(false)
const showCreateDialog = ref(false)
const showDetailDrawer = ref(false)

const articles = ref([])
const popularArticles = ref([])
const popularTags = ref([])
const currentArticle = ref(null)

const searchKeyword = ref('')
const categoryFilter = ref('')

const pagination = reactive({
  page: 1,
  pageSize: 10,
  total: 0
})

const articleForm = reactive({
  title: '',
  category: 'HOW_TO',
  tags: [],
  summary: '',
  content: '',
  applicable_equipment: '',
  is_featured: false,
  is_public: true
})

const articleRules = {
  title: [{ required: true, message: '请输入文章标题', trigger: 'blur' }],
  category: [{ required: true, message: '请选择分类', trigger: 'change' }],
  content: [{ required: true, message: '请输入文章内容', trigger: 'blur' }]
}

const articleFormRef = ref(null)

const formatDate = (date) => {
  if (!date) return '-'
  return new Date(date).toLocaleDateString('zh-CN')
}

const truncate = (text, length) => {
  if (!text) return ''
  return text.length > length ? text.substring(0, length) + '...' : text
}

const getCategoryType = (category) => {
  const map = {
    TROUBLESHOOTING: 'danger',
    HOW_TO: 'primary',
    FAQ: 'success',
    SPECIFICATION: 'info',
    BEST_PRACTICE: 'warning'
  }
  return map[category] || 'info'
}

const renderMarkdown = (content) => {
  // 简单的Markdown渲染
  if (!content) return ''
  return content
    .replace(/#{3}\s(.+)/g, '<h3>$1</h3>')
    .replace(/#{2}\s(.+)/g, '<h2>$1</h2>')
    .replace(/#{1}\s(.+)/g, '<h1>$1</h1>')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    .replace(/`(.+?)`/g, '<code>$1</code>')
    .replace(/\n/g, '<br>')
}

const loadArticles = async () => {
  loading.value = true
  try {
    const params = { page: pagination.page, page_size: pagination.pageSize }
    if (searchKeyword.value) params.search = searchKeyword.value
    if (categoryFilter.value) params.category = categoryFilter.value

    const res = await getKnowledgeArticles(params)
    articles.value = res.results || res
    pagination.total = res.count || articles.value.length
  } catch (e) {
    ElMessage.error('加载文章列表失败')
  } finally {
    loading.value = false
  }
}

const loadPopularArticles = async () => {
  try {
    const res = await getPopularArticles()
    popularArticles.value = res || []
  } catch (e) {
    console.error('加载热门文章失败')
  }
}

const loadPopularTags = async () => {
  try {
    const res = await getKnowledgeTags()
    popularTags.value = res || []
  } catch (e) {
    console.error('加载热门标签失败')
  }
}

const viewArticle = async (article) => {
  try {
    const res = await getKnowledgeArticle(article.id)
    currentArticle.value = res
    showDetailDrawer.value = true
    // 增加查看次数
    viewKnowledgeArticle(article.id)
  } catch (e) {
    ElMessage.error('加载文章详情失败')
  }
}

const searchByTag = (tag) => {
  searchKeyword.value = tag
  loadArticles()
}

const saveDraft = async () => {
  try {
    await articleFormRef.value.validate()
    submitting.value = true
    await createKnowledgeArticle({ ...articleForm, status: 'DRAFT' })
    ElMessage.success('草稿已保存')
    showCreateDialog.value = false
    loadArticles()
  } catch (e) {
    if (e !== false) ElMessage.error('保存失败')
  } finally {
    submitting.value = false
  }
}

const publishArticle = async () => {
  try {
    await articleFormRef.value.validate()
    submitting.value = true
    await createKnowledgeArticle({ ...articleForm, status: 'PUBLISHED' })
    ElMessage.success('文章已发布')
    showCreateDialog.value = false
    loadArticles()
  } catch (e) {
    if (e !== false) ElMessage.error('发布失败')
  } finally {
    submitting.value = false
  }
}

const markHelpful = async (helpful) => {
  try {
    await feedbackKnowledgeArticle(currentArticle.value.id, { helpful })
    ElMessage.success('感谢您的反馈')
    // 刷新文章
    const res = await getKnowledgeArticle(currentArticle.value.id)
    currentArticle.value = res
  } catch (e) {
    ElMessage.error('反馈失败')
  }
}

onMounted(() => {
  loadArticles()
  loadPopularArticles()
  loadPopularTags()
})
</script>

<style scoped>
.knowledge-base-list {
  padding: 20px;
}
.search-card {
  margin-bottom: 16px;
}
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.article-list {
  min-height: 400px;
}
.article-item {
  padding: 16px;
  border-bottom: 1px solid #ebeef5;
  cursor: pointer;
  transition: background 0.3s;
}
.article-item:hover {
  background: #f5f7fa;
}
.article-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}
.article-title {
  font-size: 16px;
  font-weight: 500;
  color: #303133;
}
.article-summary {
  color: #606266;
  font-size: 14px;
  margin-bottom: 8px;
}
.article-meta {
  display: flex;
  gap: 16px;
  color: #909399;
  font-size: 13px;
  margin-bottom: 8px;
}
.article-meta span {
  display: flex;
  align-items: center;
  gap: 4px;
}
.article-tags {
  display: flex;
  gap: 4px;
  flex-wrap: wrap;
}
.sidebar-card {
  max-height: 300px;
}
.popular-item {
  padding: 8px 0;
  border-bottom: 1px solid #ebeef5;
  cursor: pointer;
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.popular-item:hover {
  color: #409EFF;
}
.popular-title {
  font-size: 13px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex: 1;
}
.popular-views {
  font-size: 12px;
  color: #909399;
}
.tag-cloud {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.article-detail {
  padding: 16px;
}
.detail-meta {
  display: flex;
  gap: 16px;
  align-items: center;
  color: #909399;
  font-size: 14px;
}
.detail-content {
  line-height: 1.8;
  font-size: 15px;
}
.detail-footer {
  display: flex;
  align-items: center;
  gap: 16px;
}
</style>
