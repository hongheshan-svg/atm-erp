export type Row = Record<string, any>
export type Option = { value: string | number; label: string }
export type Field = {
  key: string
  label: string
  type?: 'text' | 'password' | 'date' | 'select' | 'multi' | 'checks' | 'boolean' | 'rows' | 'file' | 'textarea'
  options?: Option[]
  fields?: Field[]
  optional?: boolean
  initial?: any
  readonly?: boolean
  hidden?: boolean
  hint?: string
  displayOnly?: boolean
  remotePath?: string
  remoteParams?: Row
  remoteFilter?: (row: Row) => boolean
}
export type Command = {
  title: string
  subject?: string
  path: string
  method?: 'post' | 'patch'
  fields: Field[]
  initial?: Row
  readonly?: boolean
  notice?: { type: 'warning' | 'info'; text: string }
  prepare?: (data: Row) => Row
  actions?: { label: string; run: () => void | Promise<void> }[]
  previewPath?: string
}
export type Column = { key: string; label: string; format?: (row: Row) => string }
