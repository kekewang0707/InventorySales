# InventorySales — 工厂销售出库管理系统

本文件夹按版本存放各阶段的详细实现计划。

## 版本路线

| 版本 | 核心功能 | 计划文件 |
|------|---------|---------|
| v0.1.0 | 产品库 + 客户管理 | [v0.1.0-product-customer.md](./v0.1.0-product-customer.md) |
| v0.2.0 | 销售出库 + 送货单打印 | [v0.2.0-delivery-print.md](./v0.2.0-delivery-print.md) |
| v0.3.0 | 客户对账单 | [v0.3.0-statement.md](./v0.3.0-statement.md) |
| v1.0.0 | AI 快捷操作 | [v1.0.0-ai-command.md](./v1.0.0-ai-command.md) |

## 项目架构概览

- **后端**: FastAPI + SQLAlchemy + SQLite
- **前端**: Vue 3 + Element Plus
- **桌面壳**: PyQt6 + QWebEngineView（内嵌 Web 前端）
- **打印方案**: ReportLab 生成 PDF → 系统打印对话框
- **AI (v1.0.0)**: OpenAI Function Calling 解析自然语言指令

## 全局决策

- 部署方式: 单机 Windows exe，PyInstaller 打包分发
- 数据目录: 程序同级 `data/` 子目录
- 后端端口: `127.0.0.1:8732`
- 送货单编号: `DH-YYYYMMDD-NNN`，每日重置
- 中文字体: 内置思源黑体（Source Han Sans SC）
- AI API Key: 通过 `.env` 文件配置
- 用户系统: 单用户免登录
