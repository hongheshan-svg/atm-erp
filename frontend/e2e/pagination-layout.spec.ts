import { test, expect, login } from './fixtures'

test('业务列表序号跨页连续，宽表左右可查看且勾选仍对应原记录', async ({ page }, info) => {
  await login(page, 'admin', process.env.E2E_ADMIN_PASSWORD!)
  const token = await page.evaluate(() => localStorage.getItem('access_token'))
  const headers = { Authorization: 'Bearer ' + token }
  const prefix = '表格验收' + Date.now() + info.project.name
  for (let i = 1; i <= 21; i++) {
    const response = await page.request.post('/api/business/partners/', { headers: { ...headers, 'Idempotency-Key': crypto.randomUUID() }, data: { name: prefix + '-' + i, kind: 'supplier' } })
    expect(response.ok(), await response.text()).toBeTruthy()
  }
  // 选择列只在「批量管理」开启后出现。
  await page.addInitScript(() => { try { localStorage.setItem('erp.batch-mode', '1') } catch { /* 无存储的文档 */ } })
  await page.goto('/erp/masterdata?resource=partners')
  await page.getByRole('tab', { name: '客户与供应商', exact: true }).click()
  const panel = page.getByRole('region', { name: '客户与供应商', exact: true })
  const search = panel.getByRole('searchbox', { name: '搜索客户与供应商', exact: true })
  await search.fill(prefix)
  await panel.getByRole('button', { name: '搜索', exact: true }).click()
  const rows = panel.locator('.el-table__body tr')
  await expect(rows).toHaveCount(10)
  const sequence = panel.locator('td.business-row-number')
  // 手机窄屏只留名称、状态和操作列，不显示序号：跨页连续改由页码提示和各页记录顺序核对（每行勾选框以记录命名）。
  const mobile = info.project.name === 'mobile'
  const pageStatus = panel.getByRole('group', { name: '翻页', exact: true }).getByText(/^第 \d+\/\d+ 页$/)
  const names = () => rows.getByRole('checkbox').evaluateAll(boxes => boxes.map(box => box.getAttribute('aria-label')!))
  // 翻页后页码先变、记录随后加载；等到本页记录与上一页完全不同再读取。
  const loadedPage = async (previous: string[], size: number) => {
    let current: string[] = []
    await expect.poll(async () => { current = await names(); return current.length === size && current.every(name => !previous.includes(name)) }).toBe(true)
    return current
  }
  const pages = [await loadedPage([], 10)]
  if (mobile) {
    await expect(sequence).toHaveCount(0)
    await expect(pageStatus).toHaveText('第 1/3 页')
  } else await expect(sequence).toHaveText(Array.from({ length: 10 }, (_, i) => String(i + 1)))
  await panel.getByRole('button', { name: '下一页', exact: true }).click()
  if (mobile) await expect(pageStatus).toHaveText('第 2/3 页')
  else await expect(sequence).toHaveText(Array.from({ length: 10 }, (_, i) => String(i + 11)))
  pages.push(await loadedPage(pages[0]!, 10))
  await expect(rows.first().getByRole('checkbox')).toBeEnabled()
  const selectedName = await rows.first().getByRole('checkbox').getAttribute('aria-label')
  await rows.first().getByRole('checkbox').check()
  await panel.getByRole('button', { name: '下一页', exact: true }).click()
  if (mobile) await expect(pageStatus).toHaveText('第 3/3 页')
  else await expect(sequence).toHaveText(['21'])
  pages.push(await loadedPage(pages[1]!, 1))
  await panel.getByRole('button', { name: '上一页', exact: true }).click()
  await expect(rows.first().getByRole('checkbox')).toHaveAttribute('aria-label', selectedName!)
  await expect(rows.first().getByRole('checkbox')).toBeChecked()
  await panel.getByLabel('每页显示条目', { exact: true }).selectOption('50')
  if (!mobile) await expect(sequence).toHaveText(Array.from({ length: 21 }, (_, i) => String(i + 1)))
  // 一页显示全部时的顺序与逐页翻看拼起来一致，没有跳过或重复。
  await expect.poll(names).toEqual(pages.flat())

  const wrap = panel.locator('.el-table__body-wrapper .el-scrollbar__wrap')
  const tools = panel.getByRole('group', { name: '客户与供应商左右查看', exact: true })
  await expect(tools).toBeVisible()
  // 翻页遮罩淡出期间点击会让 Playwright 换对齐方式重试并横移表格；左右查看从起点开始验证。
  await wrap.evaluate(el => { el.scrollLeft = 0 })
  const right = tools.getByRole('button', { name: '向右查看 →', exact: true })
  await right.click()
  await expect.poll(() => wrap.evaluate(el => el.scrollLeft)).toBeGreaterThan(0)
  if (info.project.name === 'mobile') {
    expect(await panel.locator('td.el-table-fixed-column--right').first().evaluate(el => getComputedStyle(el).position)).toBe('static')
  }
  await tools.getByRole('button', { name: '← 向左查看', exact: true }).click()
  await expect.poll(() => wrap.evaluate(el => el.scrollLeft)).toBe(0)
  const bar = panel.locator('.el-scrollbar__bar.is-horizontal')
  await expect(bar).toBeVisible()
  await wrap.evaluate(el => { el.scrollTop = el.scrollHeight })
  await page.screenshot({ path: info.outputPath('numbered-business-table.png'), animations: 'disabled' })

  // 过滤后显示序号重新开始，业务编码仍由服务端保留；不执行删除。
  await search.fill(prefix + '-21')
  await panel.getByRole('button', { name: '搜索', exact: true }).click()
  if (mobile) await expect(rows).toHaveCount(1)
  else await expect(sequence).toHaveText(['1'])
  await expect(rows.first()).toContainText(prefix + '-21')
  await expect(rows.first()).toContainText('供应商')
})

test('每页数量跨页面保存，长表格内部滚动且桌面侧栏背景覆盖到底', async ({ page }, info) => {
  await login(page, 'admin', process.env.E2E_ADMIN_PASSWORD!)
  const first = page.waitForResponse(r => r.url().includes('/api/business/reports/'))
  await page.goto('/erp/reports')
  const baseline = await (await first).json()
  const panel = page.getByRole('region', { name: '项目经营明细', exact: true })
  const size = panel.getByLabel('每页显示条目', { exact: true })
  await expect(size).toHaveValue('10')
  expect(baseline.page_size).toBe(10)
  const changed = page.waitForResponse(r => r.url().includes('/api/business/reports/') && new URL(r.url()).searchParams.get('page_size') === '50')
  await size.selectOption('50')
  const result = await (await changed).json()
  expect(result.summary).toEqual(baseline.summary)
  expect(result.page).toBe(1)
  await expect(panel.getByLabel('每页显示条目', { exact: true })).toHaveValue('50')
  expect(await panel.locator('.el-table').evaluate(el => el.getBoundingClientRect().height)).toBeLessThanOrEqual(561)
  await page.goto('/erp/masterdata')
  for (const name of ['物料', '客户与供应商']) {
    await page.getByRole('tab', { name, exact: true }).click()
    await expect(page.getByRole('region', { name, exact: true }).getByLabel('每页显示条目', { exact: true })).toHaveValue('50')
  }
  await page.reload()
  await page.getByRole('tab', { name: '物料', exact: true }).click()
  await expect(page.getByRole('region', { name: '物料', exact: true }).getByLabel('每页显示条目', { exact: true })).toHaveValue('50')
  await page.getByRole('region', { name: '物料', exact: true }).getByLabel('每页显示条目', { exact: true }).selectOption('10')
  await page.goto('/erp/reports')
  await expect(page.getByRole('region', { name: '项目经营明细', exact: true }).getByLabel('每页显示条目', { exact: true })).toHaveValue('10')
  if (info.project.name === 'desktop') {
    // 侧栏底色取自 --side，比对 token 本身，换配色时这里不该跟着改。
    const layout = await page.locator('.shell').evaluate(el => {
      const probe = document.createElement('div')
      probe.style.background = 'var(--side)'
      el.append(probe)
      const token = getComputedStyle(probe).backgroundColor
      probe.remove()
      return { color: getComputedStyle(el).backgroundColor, token, height: el.getBoundingClientRect().height, documentHeight: document.documentElement.scrollHeight }
    })
    expect(layout.token).not.toBe('rgba(0, 0, 0, 0)')
    expect(layout.color).toBe(layout.token)
    expect(layout.height).toBeGreaterThanOrEqual(layout.documentHeight - 1)
    await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight))
    await expect(page.locator('.sidebar-navigation')).toBeInViewport({ ratio: 1 })
    const footer = await page.locator('.sidebar-note').evaluate(el => ({ bottom: el.getBoundingClientRect().bottom + window.scrollY, documentHeight: document.documentElement.scrollHeight }))
    expect(footer.documentHeight - footer.bottom).toBeGreaterThanOrEqual(23)
    expect(footer.documentHeight - footer.bottom).toBeLessThanOrEqual(25)
    await page.evaluate(() => window.scrollTo(0, 0))
  }
  await page.screenshot({ path: info.outputPath('compact-reports.png'), fullPage: true, animations: 'disabled' })
})
