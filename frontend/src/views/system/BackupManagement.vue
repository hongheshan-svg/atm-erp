<template>
  <div class="backup-management">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>数据备份管理</span>
          <el-button type="primary" @click="createBackup" :loading="creating">
            <el-icon><Plus /></el-icon> 创建备份
          </el-button>
        </div>
      </template>

      <el-alert 
        type="info" 
        :closable="false" 
        style="margin-bottom: 20px"
      >
        <template #title>
          备份目录: {{ backupDir }}
        </template>
        定期备份可以保护您的数据安全。建议每天自动备份，并保留至少30天的备份历史。
      </el-alert>

      <el-table :data="backups" v-loading="loading" stripe style="width: 100%">
        <el-table-column prop="name" label="备份文件" min-width="250">
          <template #default="{ row }">
            <el-icon><Document /></el-icon>
            {{ row.name }}
          </template>
        </el-table-column>
        <el-table-column prop="size" label="文件大小" width="120" align="right">
          <template #default="{ row }">
            {{ formatSize(row.size) }}
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="180">
          <template #default="{ row }">
            {{ formatDateTime(row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button 
              type="success" 
              size="small" 
              @click="restoreBackup(row)"
              :loading="restoring === row.name"
            >
              恢复
            </el-button>
            <el-button 
              type="danger" 
              size="small" 
              @click="deleteBackup(row)"
            >
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-empty v-if="!loading && backups.length === 0" description="暂无备份记录" />
    </el-card>

    <!-- 清理过期备份 -->
    <el-card style="margin-top: 20px">
      <template #header>清理过期备份</template>
      <el-form :inline="true">
        <el-form-item label="保留天数">
          <el-input-number v-model="keepDays" :min="7" :max="365" :step="7" />
        </el-form-item>
        <el-form-item>
          <el-button type="warning" @click="cleanupBackups" :loading="cleaning">
            清理过期备份
          </el-button>
        </el-form-item>
      </el-form>
      <el-text type="info">
        将删除 {{ keepDays }} 天前的所有备份文件
      </el-text>
    </el-card>

    <!-- 创建备份对话框 -->
    <el-dialog v-model="showCreateDialog" title="创建备份" width="400px">
      <el-form>
        <el-form-item label="备份名称（可选）">
          <el-input v-model="backupName" placeholder="留空使用时间戳命名" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreateDialog = false">取消</el-button>
        <el-button type="primary" @click="confirmCreate" :loading="creating">确认创建</el-button>
      </template>
    </el-dialog>

    <!-- 恢复确认对话框 -->
    <el-dialog v-model="showRestoreDialog" title="恢复数据" width="500px">
      <el-alert type="warning" :closable="false" style="margin-bottom: 20px">
        <template #title>警告：此操作将覆盖当前数据库！</template>
        恢复备份将用备份文件中的数据替换当前数据库中的所有数据。此操作不可撤销！
      </el-alert>
      <p>确定要恢复备份 <strong>{{ selectedBackup?.name }}</strong> 吗？</p>
      <template #footer>
        <el-button @click="showRestoreDialog = false">取消</el-button>
        <el-button type="danger" @click="confirmRestore" :loading="restoring">确认恢复</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Document } from '@element-plus/icons-vue'
import request from '@/utils/request'

const loading = ref(false)
const creating = ref(false)
const restoring = ref('')
const cleaning = ref(false)
const backups = ref([])
const backupDir = ref('')
const keepDays = ref(30)
const backupName = ref('')
const showCreateDialog = ref(false)
const showRestoreDialog = ref(false)
const selectedBackup = ref(null)

const formatSize = (bytes) => {
  if (!bytes) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
}

const formatDateTime = (dateStr) => {
  if (!dateStr) return ''
  return new Date(dateStr).toLocaleString('zh-CN')
}

const fetchBackups = async () => {
  loading.value = true
  try {
    const res = await request({ url: '/core/backups/', method: 'get' })
    backups.value = res?.backups || []
    backupDir.value = res?.backup_dir || ''
  } catch (error) {
    ElMessage.error('获取备份列表失败')
  } finally {
    loading.value = false
  }
}

const createBackup = () => {
  backupName.value = ''
  showCreateDialog.value = true
}

const confirmCreate = async () => {
  creating.value = true
  try {
    const res = await request({
      url: '/core/backups/create/',
      method: 'post',
      data: { name: backupName.value || undefined }
    })
    ElMessage.success('备份创建成功')
    showCreateDialog.value = false
    fetchBackups()
  } catch (error) {
    ElMessage.error('备份创建失败: ' + (error.response?.data?.error || error.message))
  } finally {
    creating.value = false
  }
}

const restoreBackup = (backup) => {
  selectedBackup.value = backup
  showRestoreDialog.value = true
}

const confirmRestore = async () => {
  if (!selectedBackup.value) return
  
  restoring.value = selectedBackup.value.name
  try {
    await request({
      url: '/core/backups/restore/',
      method: 'post',
      data: { name: selectedBackup.value.name }
    })
    ElMessage.success('数据恢复成功，请刷新页面')
    showRestoreDialog.value = false
  } catch (error) {
    ElMessage.error('恢复失败: ' + (error.response?.data?.error || error.message))
  } finally {
    restoring.value = ''
  }
}

const deleteBackup = async (backup) => {
  try {
    await ElMessageBox.confirm(
      `确定要删除备份 "${backup.name}" 吗？此操作不可撤销！`,
      '确认删除',
      { type: 'warning' }
    )
    
    await request({
      url: `/core/backups/${backup.name}/`,
      method: 'delete'
    })
    ElMessage.success('备份已删除')
    fetchBackups()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('删除失败: ' + (error.response?.data?.error || error.message))
    }
  }
}

const cleanupBackups = async () => {
  try {
    await ElMessageBox.confirm(
      `确定要删除 ${keepDays.value} 天前的所有备份吗？`,
      '确认清理',
      { type: 'warning' }
    )
    
    cleaning.value = true
    const res = await request({
      url: '/core/backups/cleanup/',
      method: 'post',
      data: { keep_days: keepDays.value }
    })
    ElMessage.success(res?.message || '清理成功')
    fetchBackups()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('清理失败: ' + (error.response?.data?.error || error.message))
    }
  } finally {
    cleaning.value = false
  }
}

onMounted(() => {
  fetchBackups()
})
</script>

<style scoped>
.backup-management {
  padding: 20px;
}
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
</style>
