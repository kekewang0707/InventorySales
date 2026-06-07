# InventorySales — 工厂销售出库管理系统

## v0.1.0 — 产品库 + 客户管理

### 快速启动

```bash
# 1. 安装依赖
pip install -r requirements.txt
cd frontend && npm install && cd ..

# 2. 启动后端（终端1）
python3 -m backend.main

# 3. 启动前端开发服务器（终端2）
cd frontend && npm run dev

# 4. 打开浏览器访问
# http://localhost:5173

# 5. 或者启动桌面应用（自动启动后端 + 加载前端）
cd desktop && python3 app.py
```

### API 文档
后端启动后访问 http://127.0.0.1:8732/docs

### 目录结构

```
InventorySales/
├── backend/          # FastAPI 后端
│   ├── main.py       # 应用入口
│   ├── config.py     # 配置
│   ├── database.py   # 数据库
│   ├── models/       # 数据模型
│   ├── schemas/      # Pydantic 模式
│   ├── routers/      # API 路由
│   └── services/     # 业务逻辑
├── frontend/         # Vue 3 前端
│   └── src/
│       ├── api/      # API 调用
│       ├── views/    # 页面
│       └── components/ # 公共组件
├── desktop/          # PyQt6 桌面壳
│   ├── app.py
│   └── server_manager.py
├── plan/             # 各版本实现计划
└── requirements.txt
```
