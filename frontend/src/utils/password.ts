/** Generate locally without persisting or logging the initial password. */
export function randomPassword(): string {
  const alphabet = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_'
  const bytes = crypto.getRandomValues(new Uint8Array(20))
  // 64 divides 256, so this mapping has no modulo bias.
  return Array.from(bytes, byte => alphabet[byte % alphabet.length]).join('')
}
