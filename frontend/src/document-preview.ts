import { shallowRef } from 'vue'

export const documentPreview = shallowRef<{ id: number; name?: string } | null>(null)
export function openDocumentPreview(id: number | string, name?: string) {
  if (Number.isSafeInteger(Number(id)) && Number(id) > 0) documentPreview.value = { id: Number(id), name }
}
export function closeDocumentPreview() { documentPreview.value = null }

// Every entry uses the same authenticated viewer; file contents are never sent to a public viewer.
export function previewAction(id: number | string, name = '附件') {
  return { label: `预览 ${name}`, run: () => openDocumentPreview(id, name) }
}
