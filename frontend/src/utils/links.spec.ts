import { expect, it } from 'vitest'
import { linkLabel, purchaseLink } from './links'

it('只把 http(s) 链接当作购买链接，其他写法不渲染成链接', () => {
  expect(purchaseLink(' https://item.taobao.com/item.htm?id=1 ')).toBe('https://item.taobao.com/item.htm?id=1')
  expect(purchaseLink('HTTP://m.tb.cn/h.Abc')).toBe('HTTP://m.tb.cn/h.Abc')
  for (const value of ['javascript:alert(1)', 'item.taobao.com/item.htm', '淘宝收藏夹', '', null, undefined, 12]) expect(purchaseLink(value)).toBe('')
})

it('按网店域名写链接文字，认不出的写「购买链接」', () => {
  expect(linkLabel('https://item.taobao.com/item.htm?id=1')).toBe('淘宝')
  expect(linkLabel('https://m.tb.cn/h.Abc?tk=1')).toBe('淘宝')
  expect(linkLabel('https://detail.tmall.com/item.htm?id=2')).toBe('天猫')
  expect(linkLabel('https://item.jd.com/100012.html')).toBe('京东')
  expect(linkLabel('https://detail.1688.com/offer/1.html')).toBe('1688')
  expect(linkLabel('https://mobile.yangkeduo.com/goods.html?goods_id=1')).toBe('拼多多')
  expect(linkLabel('https://www.misumi.com.cn/vona2/detail/1')).toBe('购买链接')
  expect(linkLabel('https://faketaobao.com/x')).toBe('购买链接')
})
