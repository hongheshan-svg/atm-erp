<template>
  <div class="webhook-list">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>Webhook管理</span>
          <el-button type="primary" @click="showForm = true">
            <el-icon><Plus /></el-icon>
            新增Webhook
          </el-button>
        </div>
      </template>

      <!-- Table -->
      <el-table :data="webhooks" v-loading="loading" stripe>
        <el-table-column prop="name" label="名称" width="150" />
        <el-table-column prop="url" label="回调URL" min-width="250" show-overflow-tooltip />
        <el-table-column prop="events" label="订阅事件" width="200">
          <template #default="{ row }">
            <el-tag v-for="event in row.events?.slice(0, 2)" :key="event" size="small" class="event-tag">
              {{ event }}
            </el-tag>
            <span v-if="row.events?.length > 2">+{{ row.events.length - 2 }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="is_active" label="状态" width="80">
          <template #default="{ row }">
            <el-switch v-model="row.is_active" @change="toggleStatus(row)" />
          </template>
        </el-table-column>
        <el-table-column prop="success_rate" label="成功率" width="100">
          <template #default="{ row }">
            <span v-if="row.success_rate !== null">{{ row.success_rate }}%</span>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column prop="delivery_count" label="投递次数" width="100" />
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="testWebhook(row)">测试</el-button>
            <el-button size="small" type="primary" @click="editWebhook(row)">编辑</el-button>
            <el-button size="small" type="danger" @click="deleteWebhook(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- Form Dialog -->
    <el-dialog v-model="showForm" :title="editingId ? '编辑Webhook' : '新增Webhook'" width="600px">
      <el-form :model="form" :rules="rules" ref="formRef" label-width="100px">
        <el-form-item label="名称" prop="name">
          <el-input v-model="form.name" placeholder="Webhook名称" />
        </el-form-item>
        <el-form-item label="回调URL" prop="url">
          <el-input v-model="form.url" placeholder="https://example.com/webhook" />
        </el-form-item>
        <el-form-item label="签名密钥" prop="secret">
          <el-input v-model="form.secret" placeholder="用于验证请求签名" show-password />
        </el-form-item>
        <el-form-item label="订阅事件" prop="events">
          <el-select v-model="form.events" multiple placeholder="选择事件" style="width: 100%">
            <el-option
              v-for="event in eventTypes"
              :key="event.value"
              :label="event.label"
              :value="event.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="超时时间">
          <el-input-number v-model="form.timeout" :min="5" :max="120" /> 秒
        </el-form-item>
        <el-form-item label="最大重试">
          <el-input-number v-model="form.max_retries" :min="0" :max="10" /> 次
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showForm = false">取消</el-button>
        <el-button type="primary" @click="submitForm" :loading="submitting">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import * as webhookApi from '@/api/webhook'

const loading = ref(false)
const submitting = ref(false)
const showForm = ref(false)
const webhooks = ref([])
const eventTypes = ref([])
const editingId = ref(null)
const formRef = ref(null)

const form = reactive({
  name: '',
  url: '',
  secret: '',
  events: [],
  timeout: 30,
  max_retries: 3
})

const rules = {
  name: [{ required: true, message: '请输入名称', trigger: 'blur' }],
  url: [
    { required: true, message: '请输入URL', trigger: 'blur' },
    { type: 'url', message: '请输入有效的URL', trigger: 'blur' }
  ],
  events: [{ required: true, message: '请选择事件', trigger: 'change' }]
}

const fetchData = async () => {
  loading.value = true
  try {
    const res = await webhookApi.getWebhooks()
    webhooks.value = res.results || res
  } finally {
    loading.value = false
  }
}

const fetchEventTypes = async () => {
  const res = await webhookApi.getEventTypes()
  eventTypes.value = res
}

const toggleStatus = async (row) => {
  try {
    await webhookApi.toggleWebhook(row.id)
    ElMessage.success('状态已更新')
  } catch (error) {
    console.error(error)
    row.is_active = !row.is_active
  }
}

const testWebhook = async (row) => {
  try {
    const res = await webhookApi.testWebhook(row.id)
    if (res.success) {
      ElMessage.success('测试成功')
    } else {
      ElMessage.error(`测试失败: ${res.error_message}`)
    }
  } catch (err) {
    ElMessage.error('测试请求失败')
  }
}

const editWebhook = (row) => {
  editingId.value = row.id
  Object.assign(form, {
    name: row.name,
    url: row.url,
    secret: '',
    events: row.events || [],
    timeout: row.timeout,
    max_retries: row.max_retries
  })
  showForm.value = true
}

const deleteWebhook = async (row) => {
  await ElMessageBox.confirm('确定删除此Webhook?', '确认')
  await webhookApi.deleteWebhook(row.id)
  ElMessage.success('删除成功')
  fetchData()
}

const submitForm = async () => {
  await formRef.value.validate()
  submitting.value = true
  try {
    if (editingId.value) {
      await webhookApi.updateWebhook(editingId.value, form)
    } else {
      await webhookApi.createWebhook(form)
    }
    ElMessage.success('保存成功')
    showForm.value = false
    resetForm()
    fetchData()
  } finally {
    submitting.value = false
  }
}

const resetForm = () => {
  editingId.value = null
  Object.assign(form, {
    name: '',
    url: '',
    secret: '',
    events: [],
    timeout: 30,
    max_retries: 3
  })
}

onMounted(() => {
  fetchData()
  fetchEventTypes()
})
</script>

<style scoped>
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.event-tag {
  margin-right: 4px;
}
</style>
