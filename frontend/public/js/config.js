/**
 * 前端全局配置
 * 开发环境(Vite): API 通过 Vite proxy 代理到后端
 * 生产环境: 直接使用相对路径（同源）
 */
window.API_BASE = '/api'

// 保持向后兼容
if (!window.API_CONFIG) {
  window.API_CONFIG = {
    base: window.API_BASE,
  }
}
