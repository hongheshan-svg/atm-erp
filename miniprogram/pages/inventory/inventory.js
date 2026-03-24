Page({
  data: {
    searchKeyword: '',
    stockList: [],
    loading: false,
    page: 1,
    hasMore: true
  },
  onLoad() { this.loadStock() },
  onInput(e) { this.setData({ searchKeyword: e.detail.value }) },
  onSearch() { this.setData({ stockList: [], page: 1, hasMore: true }); this.loadStock() },
  loadStock() {
    if (this.data.loading || !this.data.hasMore) return
    this.setData({ loading: true })
    wx.request({
      url: getApp().globalData.baseUrl + '/api/inventory/stocks/',
      data: { search: this.data.searchKeyword, page: this.data.page, page_size: 20 },
      header: { Authorization: 'Bearer ' + wx.getStorageSync('token') },
      success: (res) => {
        const results = res.data.results || []
        this.setData({
          stockList: this.data.stockList.concat(results),
          hasMore: !!res.data.next,
          page: this.data.page + 1
        })
      },
      complete: () => { this.setData({ loading: false }) }
    })
  },
  onReachBottom() { this.loadStock() },
  onPullDownRefresh() {
    this.setData({ stockList: [], page: 1, hasMore: true })
    this.loadStock()
    wx.stopPullDownRefresh()
  }
})
