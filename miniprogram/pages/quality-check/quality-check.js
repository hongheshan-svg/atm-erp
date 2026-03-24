Page({
  data: {
    inspectionList: [],
    photos: [],
    form: { work_order: '', result: 'pass', defect_description: '', notes: '' },
    loading: false
  },
  onLoad() {},
  takePhoto() {
    wx.chooseMedia({
      count: 9, mediaType: ['image'], sourceType: ['camera', 'album'],
      success: (res) => {
        const photos = this.data.photos.concat(res.tempFiles.map(f => f.tempFilePath))
        this.setData({ photos })
      }
    })
  },
  removePhoto(e) {
    const idx = e.currentTarget.dataset.index
    const photos = this.data.photos.filter((_, i) => i !== idx)
    this.setData({ photos })
  },
  onInput(e) {
    const field = e.currentTarget.dataset.field
    this.setData({ ['form.' + field]: e.detail.value })
  },
  onResultChange(e) { this.setData({ 'form.result': e.detail.value }) },
  submitInspection() {
    const { form, photos } = this.data
    if (!form.work_order) { wx.showToast({ title: '请输入工单号', icon: 'none' }); return }
    this.setData({ loading: true })
    // Upload photos first, then submit
    const uploadTasks = photos.map(p => new Promise((resolve, reject) => {
      wx.uploadFile({
        url: getApp().globalData.baseUrl + '/api/core/attachments/',
        filePath: p, name: 'file',
        header: { Authorization: 'Bearer ' + wx.getStorageSync('token') },
        success: (res) => resolve(JSON.parse(res.data).id),
        fail: reject
      })
    }))
    Promise.all(uploadTasks).then(ids => {
      wx.request({
        url: getApp().globalData.baseUrl + '/api/production/quality-inspections/',
        method: 'POST',
        header: { Authorization: 'Bearer ' + wx.getStorageSync('token'), 'Content-Type': 'application/json' },
        data: { ...form, photo_ids: ids },
        success: () => {
          wx.showToast({ title: '提交成功' })
          this.setData({ form: { work_order: '', result: 'pass', defect_description: '', notes: '' }, photos: [] })
        },
        fail: () => { wx.showToast({ title: '提交失败', icon: 'none' }) },
        complete: () => { this.setData({ loading: false }) }
      })
    }).catch(() => { this.setData({ loading: false }); wx.showToast({ title: '照片上传失败', icon: 'none' }) })
  }
})
