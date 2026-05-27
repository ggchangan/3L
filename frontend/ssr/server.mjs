/**
 * 3L 交易系统 — SSR 服务端
 * 监听端口 3001
 *   - SPA 路由 → 返回预渲染 HTML
 *   - /assets/* → 直接返回静态 JS/CSS 文件
 *   - /api/* → 不处理（Python 原生处理）
 */
import http from 'http'
import fs from 'fs'
import path from 'path'
import { fileURLToPath } from 'url'

var __dirname = path.dirname(fileURLToPath(import.meta.url))
var DIST_DIR = path.resolve(__dirname, '..', 'dist')
var ASSETS_DIR = path.join(DIST_DIR, 'assets')

var SPA_ROUTES = new Set([
  '/monitor', '/review', '/stock_analysis',
  '/holdings', '/industry', '/macro',
  '/top_gainers', '/tips', '/simulation',
  '/skills', '/journal', '/workbench',
  '/watchlist', '/trend_candidates', '/logic-tracking',
])

var MIME = {
  '.js': 'application/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.html': 'text/html; charset=utf-8',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.svg': 'image/svg+xml',
  '.ico': 'image/x-icon',
  '.json': 'application/json',
}

function isSpaRoute(p) {
  if (SPA_ROUTES.has(p)) return true
  var base = '/' + p.split('/').filter(Boolean)[0]
  return SPA_ROUTES.has(base)
}

function serveFile(res, filePath, ct) {
  try {
    var data = fs.readFileSync(filePath)
    res.writeHead(200, {
      'Content-Type': ct,
      'Content-Length': data.length,
      'Cache-Control': 'no-cache',
    })
    res.end(data)
  } catch (e) {
    res.writeHead(404)
    res.end('Not found')
  }
}

var renderModule = null

async function loadRender() {
  if (renderModule) return
  var renderPath = path.join(DIST_DIR, 'ssr', 'render.mjs')
  if (!fs.existsSync(renderPath)) {
    console.warn('[SSR] render.mjs 不存在')
    return
  }
  try {
    renderModule = await import(renderPath)
    console.log('[SSR] render 模块已加载')
  } catch (e) {
    console.error('[SSR] 加载 render 模块失败:', e.message)
  }
}

function handleSPA(res, pathname) {
  try {
    var templatePath = path.join(DIST_DIR, 'react.html')
    if (!fs.existsSync(templatePath)) throw new Error('模板未找到')

    var template = fs.readFileSync(templatePath, 'utf-8')

    if (renderModule) {
      try {
        var renderedHtml = renderModule.render(pathname)
        template = template.replace(
          '<div id="root">',
          '<div id="root">' + renderedHtml
        )
      } catch (e) {
        console.error('[SSR] 渲染失败:', e.message)
      }
    }

    res.writeHead(200, {
      'Content-Type': 'text/html; charset=utf-8',
    })
    res.end(template)
  } catch (e) {
    res.writeHead(500)
    res.end('SSR Error: ' + e.message)
  }
}

function handleAsset(res, pathname) {
  var rel = pathname.replace('/assets/', '')
  var filePath = path.join(ASSETS_DIR, rel)

  // 路径安全检查
  if (filePath.indexOf(ASSETS_DIR) !== 0) {
    res.writeHead(403)
    res.end('Forbidden')
    return
  }

  if (!fs.existsSync(filePath)) {
    res.writeHead(404)
    res.end('Not found: ' + pathname)
    return
  }

  var ext = path.extname(filePath)
  var ct = MIME[ext] || 'application/octet-stream'
  serveFile(res, filePath, ct)
}

var server = http.createServer(function (req, res) {
  var url = new URL(req.url || '/', 'http://' + (req.headers.host || 'localhost'))
  var pathname = url.pathname

  // /assets/* → 静态资源（Node 高效并发）
  if (pathname.startsWith('/assets/')) {
    handleAsset(res, pathname)
    return
  }

  // SPA 路由 → SSR 渲染
  if (isSpaRoute(pathname)) {
    handleSPA(res, pathname)
    return
  }

  // 其他（root + 未知）→ 404
  res.writeHead(404, { 'Content-Type': 'text/plain' })
  res.end('Not handled by SSR: ' + pathname)
})

var PORT = parseInt(process.env.SSR_PORT || '3001', 10)
server.listen(PORT, function () {
  console.log('[SSR] 服务启动于 http://localhost:' + PORT)
  loadRender()
})
