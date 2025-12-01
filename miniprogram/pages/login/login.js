/**
 * 登录页面
 */
const app = getApp()

Page({
  data: {
    username: '',
    password: '',
    showPassword: false,
    loading: false
  },

  onUsernameInput(e) {
    this.setData({ username: e.detail.value })
  },

  onPasswordInput(e) {
    this.setData({ password: e.detail.value })
  },

  togglePassword() {
    this.setData({ showPassword: !this.data.showPassword })
  },

  async handleLogin() {
    const { username, password } = this.data

    if (!username.trim()) {
      wx.showToast({ title: '请输入用户名', icon: 'none' })
      return
    }

    if (!password.trim()) {
      wx.showToast({ title: '请输入密码', icon: 'none' })
      return
    }

    this.setData({ loading: true })

    try {
      const res = await app.request({
        url: '/accounts/login/',
        method: 'POST',
        data: { username, password },
        showLoading: false
      })

      // 保存token和用户信息
      wx.setStorageSync('token', res.access)
      wx.setStorageSync('refreshToken', res.refresh)
      wx.setStorageSync('userInfo', res.user)

      app.globalData.token = res.access
      app.globalData.userInfo = res.user

      wx.showToast({ title: '登录成功', icon: 'success' })

      // 跳转首页
      setTimeout(() => {
        wx.switchTab({ url: '/pages/index/index' })
      }, 1000)

    } catch (err) {
      wx.showToast({ 
        title: err.detail || '登录失败', 
        icon: 'none' 
      })
    } finally {
      this.setData({ loading: false })
    }
  }
})
