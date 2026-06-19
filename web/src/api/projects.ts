import { computed, type MaybeRefOrGetter, toValue } from 'vue'
import { useMutation, useQuery, useQueryClient } from '@tanstack/vue-query'
import request from '@/utils/request'
import type {
  PageResult,
  Project,
  ProjectCreateInput,
  ProjectListQuery,
  ProjectUpdateInput
} from '@/types'

const PROJECTS_BASE = '/projects/projects'

// ===== 原子 API(纯 HTTP 调用,可独立复用)=====

export function fetchProjects(query: ProjectListQuery): Promise<PageResult<Project>> {
  return request.get<PageResult<Project>>(PROJECTS_BASE, { params: query })
}

export function fetchProject(id: number): Promise<Project> {
  return request.get<Project>(`${PROJECTS_BASE}/${id}`)
}

export function createProject(input: ProjectCreateInput): Promise<Project> {
  return request.post<Project>(PROJECTS_BASE, input)
}

export function updateProject(id: number, input: ProjectUpdateInput): Promise<Project> {
  return request.put<Project>(`${PROJECTS_BASE}/${id}`, input)
}

export function deleteProject(id: number): Promise<void> {
  return request.delete<void>(`${PROJECTS_BASE}/${id}`)
}

// ===== TanStack Query 封装 =====

export const projectKeys = {
  all: ['projects'] as const,
  list: (query: ProjectListQuery) => ['projects', 'list', query] as const
}

// 项目列表查询。
export function useProjectsQuery(query: MaybeRefOrGetter<ProjectListQuery>) {
  const queryKey = computed(() => projectKeys.list(toValue(query)))
  return useQuery({
    queryKey,
    queryFn: () => fetchProjects(toValue(query))
  })
}

// 项目新建。
export function useCreateProjectMutation() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (input: ProjectCreateInput) => createProject(input),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: projectKeys.all })
    }
  })
}

// 项目更新。
export function useUpdateProjectMutation() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (vars: { id: number; input: ProjectUpdateInput }) => updateProject(vars.id, vars.input),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: projectKeys.all })
    }
  })
}

// 项目删除。
export function useDeleteProjectMutation() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => deleteProject(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: projectKeys.all })
    }
  })
}
