import { readFileSync, readdirSync } from 'node:fs'
import { createRequire } from 'node:module'
import { dirname, join } from 'node:path'
import type { Plugin } from 'vite'

// Ship PDF fonts/CMaps/decoders with the app, including on offline factory networks.
export function pdfAssets(): Plugin {
  const root = dirname(createRequire(import.meta.url).resolve('pdfjs-dist/package.json'))
  const assets = new Map<string, Buffer>()
  for (const folder of ['cmaps', 'standard_fonts', 'wasm']) {
    for (const name of readdirSync(join(root, folder))) assets.set(`pdfjs/${folder}/${name}`, readFileSync(join(root, folder, name)))
  }
  return {
    name: 'local-pdf-assets',
    configureServer(server) {
      server.middlewares.use((req, res, next) => {
        const path = (req.url || '').split('?')[0]!.replace(/^\/(?:erp\/)?/, '')
        const source = assets.get(path)
        if (!source) return next()
        res.setHeader('Content-Type', path.endsWith('.wasm') ? 'application/wasm' : /\.m?js$/.test(path) ? 'text/javascript' : 'application/octet-stream')
        res.end(source)
      })
    },
    generateBundle() { for (const [fileName, source] of assets) this.emitFile({ type: 'asset', fileName, source }) },
  }
}
