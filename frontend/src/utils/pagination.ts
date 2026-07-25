type PaginatedData = {
  count?: number | null
  readonly length?: number | null
}

export const getPaginationTotal = <T extends PaginatedData>(data: T): number => {
  return data.count ?? data.length ?? 0
}
