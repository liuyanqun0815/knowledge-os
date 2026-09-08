# AKOS Admin Web

AKOS 管理台前端（React + Vite + TypeScript）。

## 本地开发

1. 安装依赖：

   ```bash
   npm install
   ```

2. 启动后端 API（默认 `http://127.0.0.1:8000`）。

3. 启动开发服务器：

   ```bash
   npm run dev
   ```

4. 在浏览器打开 [http://127.0.0.1:5173](http://127.0.0.1:5173)。

Vite 开发服会将 `/admin` 与 `/ask` 代理到后端 `:8000`。

## 脚本

| 命令 | 说明 |
|------|------|
| `npm run dev` | 开发模式 |
| `npm run build` | 生产构建 |
| `npm run preview` | 预览构建产物 |
| `npm test` | 运行测试（单次） |
| `npm run test:watch` | 监听模式测试 |

## 环境变量

复制 `.env.example` 为 `.env.local` 并按需填写：

- `VITE_ADMIN_API_TOKEN` — 可选，与后端 `ADMIN_API_TOKEN` 对齐的管理 API 令牌。
