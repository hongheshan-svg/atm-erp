// 全局共享类型定义。后端契约对齐 server/internal/* 与旧前端 profile 结构。

// DRF 风格分页信封 {count,next,previous,results}(httpx.Page)。
export interface PageResult<T> {
  count: number
  next: string | null
  previous: string | null
  results: T[]
}

// 后端错误体 {detail}(httpx.Error)。
export interface ApiError {
  detail?: string
  error?: string
}

// 用户档案。刷新/登录后由后端回灌 permissions/menus/data_scopes。
export interface UserProfile {
  id: number
  username: string
  name?: string
  email?: string
  permissions?: string[]
  menus?: string[]
  data_scopes?: Record<string, string>
}

// 登录响应。token + 内联用户档案。
export interface LoginResult {
  access: string
  refresh: string
  user: UserProfile
}

// 物料,对齐 server/internal/masterdata/item Item。
export interface Item {
  id: number
  code: string
  name: string
  spec: string
  unit: string
  category: string
  price: number
  created_at?: string
  updated_at?: string
}

// 物料创建入参(对齐 CreateInput)。
export interface ItemCreateInput {
  code: string
  name: string
  spec?: string
  unit?: string
  category?: string
  price?: number
}

// 物料更新入参(对齐 UpdateInput,局部更新)。
export interface ItemUpdateInput {
  name?: string
  spec?: string
  unit?: string
  category?: string
  price?: number
}

// 物料列表查询条件。
export interface ItemListQuery {
  keyword?: string
  category?: string
  page?: number
  page_size?: number
}
