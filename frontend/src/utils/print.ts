// 浏览器「另存为 PDF」默认用页面标题作文件名：单据页把标题设成「单据-对方-单号」，保存时不用再手动改名。
// 去掉 Windows 文件名不允许的字符，连续空白收成一个空格。
const unsafe = /[\\/:*?"<>|\s]+/g
export function printFileName(...parts: unknown[]) {
  return parts.map(part => String(part ?? '').replace(unsafe, ' ').trim()).filter(Boolean).join('-')
}
