<template>
  <div class="notification-settings">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>通知渠道设置</span>
          <el-button type="primary" @click="refreshStatus" :loading="loading">刷新状态</el-button>
        </div>
      </template>

      <el-alert
        title="配置说明"
        type="info"
        show-icon
        :closable="false"
        class="mb-20"
      >
        通知渠道配置需要在服务器环境变量中设置，请联系系统管理员进行配置。
        配置后可在此页面测试通知是否正常发送。
      </el-alert>

      <!-- Channel Status -->
      <el-row :gutter="20">
        <!-- Email -->
        <el-col :span="8">
          <el-card shadow="hover" class="channel-card">
            <template #header>
              <div class="channel-header">
                <el-icon size="24"><Message /></el-icon>
                <span>邮件通知</span>
              </div>
            </template>
            <div class="channel-status">
              <el-tag :type="channelStatus.email?.configured ? 'success' : 'info'">
                {{ channelStatus.email?.configured ? '已配置' : '未配置' }}
              </el-tag>
            </div>
            <p class="channel-desc">通过邮件发送系统通知，支持逾期提醒、审批通知等。</p>
          </el-card>
        </el-col>

        <!-- DingTalk -->
        <el-col :span="8">
          <el-card shadow="hover" class="channel-card">
            <template #header>
              <div class="channel-header">
                <el-icon size="24"><ChatDotRound /></el-icon>
                <span>钉钉通知</span>
              </div>
            </template>
            <div class="channel-status">
              <el-tag :type="channelStatus.dingtalk?.configured ? 'success' : 'info'">
                {{ channelStatus.dingtalk?.configured ? '已配置' : '未配置' }}
              </el-tag>
              <div class="status-detail" v-if="channelStatus.dingtalk?.configured">
                <el-tag size="small" :type="channelStatus.dingtalk?.webhook_enabled ? 'success' : 'info'">
                  Webhook: {{ channelStatus.dingtalk?.webhook_enabled ? '✓' : '✗' }}
                </el-tag>
                <el-tag size="small" :type="channelStatus.dingtalk?.app_enabled ? 'success' : 'info'">
                  应用: {{ channelStatus.dingtalk?.app_enabled ? '✓' : '✗' }}
                </el-tag>
              </div>
            </div>
            <p class="channel-desc">支持群机器人 Webhook 和工作通知两种方式。</p>
            <el-button 
              type="primary" 
              size="small" 
              @click="testDingTalk" 
              :loading="testing.dingtalk"
              :disabled="!channelStatus.dingtalk?.configured"
            >
              发送测试
            </el-button>
          </el-card>
        </el-col>

        <!-- WeChat Work -->
        <el-col :span="8">
          <el-card shadow="hover" class="channel-card">
            <template #header>
              <div class="channel-header">
                <el-icon size="24"><ChatLineSquare /></el-icon>
                <span>企业微信通知</span>
              </div>
            </template>
            <div class="channel-status">
              <el-tag :type="channelStatus.wechat_work?.configured ? 'success' : 'info'">
                {{ channelStatus.wechat_work?.configured ? '已配置' : '未配置' }}
              </el-tag>
              <div class="status-detail" v-if="channelStatus.wechat_work?.configured">
                <el-tag size="small" :type="channelStatus.wechat_work?.webhook_enabled ? 'success' : 'info'">
                  Webhook: {{ channelStatus.wechat_work?.webhook_enabled ? '✓' : '✗' }}
                </el-tag>
                <el-tag size="small" :type="channelStatus.wechat_work?.app_enabled ? 'success' : 'info'">
                  应用: {{ channelStatus.wechat_work?.app_enabled ? '✓' : '✗' }}
                </el-tag>
              </div>
            </div>
            <p class="channel-desc">支持群机器人 Webhook 和应用消息两种方式。</p>
            <el-button 
              type="primary" 
              size="small" 
              @click="testWeChatWork" 
              :loading="testing.wechat_work"
              :disabled="!channelStatus.wechat_work?.configured"
            >
              发送测试
            </el-button>
          </el-card>
        </el-col>
      </el-row>

      <!-- Broadcast Test -->
      <el-divider content-position="left">广播测试</el-divider>
      <el-form :inline="true" class="broadcast-form">
        <el-form-item label="标题">
          <el-input v-model="broadcastForm.title" placeholder="通知标题" style="width: 200px;" />
        </el-form-item>
        <el-form-item label="内容">
          <el-input v-model="broadcastForm.content" placeholder="通知内容" style="width: 300px;" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="sendBroadcast" :loading="testing.broadcast">发送广播</el-button>
        </el-form-item>
      </el-form>

      <!-- Configuration Guide -->
      <el-divider content-position="left">配置指南</el-divider>
      
      <el-collapse accordion>
        <el-collapse-item title="钉钉配置说明" name="dingtalk">
          <div class="config-guide">
            <h4>群机器人 Webhook</h4>
            <ol>
              <li>在钉钉群设置中添加"自定义机器人"</li>
              <li>获取 Webhook URL 和安全设置密钥</li>
              <li>设置环境变量：
                <pre>DINGTALK_WEBHOOK_URL=https://oapi.dingtalk.com/robot/send?access_token=xxx
DINGTALK_WEBHOOK_SECRET=SECxxx</pre>
              </li>
            </ol>
            <h4>工作通知（需企业应用）</h4>
            <ol>
              <li>在钉钉开放平台创建企业内部应用</li>
              <li>获取 AppKey、AppSecret 和 AgentId</li>
              <li>设置环境变量：
                <pre>DINGTALK_APP_KEY=xxx
DINGTALK_APP_SECRET=xxx
DINGTALK_AGENT_ID=xxx</pre>
              </li>
            </ol>
          </div>
        </el-collapse-item>
        
        <el-collapse-item title="企业微信配置说明" name="wechat_work">
          <div class="config-guide">
            <h4>群机器人 Webhook</h4>
            <ol>
              <li>在企业微信群设置中添加"群机器人"</li>
              <li>获取 Webhook URL</li>
              <li>设置环境变量：
                <pre>WECHAT_WORK_WEBHOOK_URL=https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxx</pre>
              </li>
            </ol>
            <h4>应用消息（需企业应用）</h4>
            <ol>
              <li>在企业微信管理后台创建自建应用</li>
              <li>获取 CorpId、Secret 和 AgentId</li>
              <li>设置环境变量：
                <pre>WECHAT_WORK_CORP_ID=xxx
WECHAT_WORK_CORP_SECRET=xxx
WECHAT_WORK_AGENT_ID=xxx</pre>
              </li>
            </ol>
          </div>
        </el-collapse-item>
      </el-collapse>
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { Message, ChatDotRound, ChatLineSquare } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import request from '@/utils/request'

const loading = ref(false)
const channelStatus = ref({})
const enabledChannels = ref([])

const testing = reactive({
  dingtalk: false,
  wechat_work: false,
  broadcast: false
})

const broadcastForm = reactive({
  title: 'ERP系统通知',
  content: '这是一条广播测试消息'
})

const refreshStatus = async () => {
  loading.value = true
  try {
    const { data } = await request.get('/core/notification-channels/status/')
    channelStatus.value = data.channels || {}
    enabledChannels.value = data.enabled || []
  } catch (error) {
    console.error('获取状态失败:', error)
  } finally {
    loading.value = false
  }
}

const testDingTalk = async () => {
  testing.dingtalk = true
  try {
    const { data } = await request.post('/core/notification-channels/test_dingtalk/', {
      title: 'ERP系统测试',
      content: '这是一条钉钉测试消息，用于验证通知配置是否正确。\n\n发送时间: ' + new Date().toLocaleString()
    })
    ElMessage.success(data.message || '发送成功')
  } catch (error) {
    ElMessage.error(error.response?.data?.message || '发送失败')
  } finally {
    testing.dingtalk = false
  }
}

const testWeChatWork = async () => {
  testing.wechat_work = true
  try {
    const { data } = await request.post('/core/notification-channels/test_wechat_work/', {
      title: 'ERP系统测试',
      content: '这是一条企业微信测试消息，用于验证通知配置是否正确。\n\n发送时间: ' + new Date().toLocaleString()
    })
    ElMessage.success(data.message || '发送成功')
  } catch (error) {
    ElMessage.error(error.response?.data?.message || '发送失败')
  } finally {
    testing.wechat_work = false
  }
}

const sendBroadcast = async () => {
  if (!broadcastForm.title || !broadcastForm.content) {
    ElMessage.warning('请输入标题和内容')
    return
  }
  
  testing.broadcast = true
  try {
    const { data } = await request.post('/core/notification-channels/broadcast/', {
      title: broadcastForm.title,
      content: broadcastForm.content
    })
    
    const successCount = Object.values(data.results || {}).filter(v => v).length
    const totalCount = Object.keys(data.results || {}).length
    
    if (successCount > 0) {
      ElMessage.success(`广播完成: ${successCount}/${totalCount} 个渠道成功`)
    } else {
      ElMessage.warning('没有渠道发送成功，请检查配置')
    }
  } catch (error) {
    ElMessage.error('广播失败')
  } finally {
    testing.broadcast = false
  }
}

onMounted(() => {
  refreshStatus()
})
</script>

<style scoped>
.notification-settings {
  padding: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.mb-20 {
  margin-bottom: 20px;
}

.channel-card {
  text-align: center;
  min-height: 200px;
}

.channel-header {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  font-weight: bold;
}

.channel-status {
  margin: 15px 0;
}

.status-detail {
  margin-top: 10px;
  display: flex;
  justify-content: center;
  gap: 8px;
}

.channel-desc {
  color: #666;
  font-size: 13px;
  margin: 15px 0;
  min-height: 40px;
}

.broadcast-form {
  margin-top: 20px;
}

.config-guide {
  padding: 10px;
  font-size: 14px;
}

.config-guide h4 {
  margin: 15px 0 10px;
  color: #333;
}

.config-guide ol {
  padding-left: 20px;
}

.config-guide li {
  margin: 8px 0;
}

.config-guide pre {
  background: #f5f5f5;
  padding: 10px;
  border-radius: 4px;
  overflow-x: auto;
  font-size: 12px;
}
</style>

