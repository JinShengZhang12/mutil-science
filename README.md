# 三智能体协同学生科学推理系统（Gradio）

这是一个可部署到 Hugging Face Spaces 的 Python + Gradio 交互式网页，包含三类智能体协同：

1. **Judge Agent（评分）**：判断学生答案质量并输出 1/3/5 分。
2. **Analyzer Agent（诊断）**：分析学生当前推理阶段并提供针对性引导。
3. **Scheduler Agent（调度）**：控制回合流程、推进题目、汇总表现。

## 目录结构

- `app.py`：Gradio UI + 三智能体主流程
- `knowledge_base.py`：题库与标准答案
- `prompts.py`：评分与诊断提示词模板
- `state_manager.py`：会话状态、进度和总分管理
- `logger.py`：日志写入与教师端密码读取
- `requirements.txt`：依赖
- `.env.example`：环境变量示例

## 本地运行

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python app.py
```

## Hugging Face Spaces 部署

### 1) 新建 Space
- SDK 选择：**Gradio**
- Python 版本建议：3.10+

### 2) 上传文件
将本仓库文件推送到 Space 仓库根目录。

### 3) 设置 Secrets（推荐）
在 Space 的 **Settings → Repository secrets** 配置：
- `OPENAI_API_KEY`（或 `DEEPSEEK_API_KEY`）
- `OPENAI_BASE_URL`（默认 `https://api.deepseek.com`）
- `OPENAI_MODEL`（默认 `deepseek-chat`）
- `TEACHER_PASSWORD`

### 4) 启动
Hugging Face 会自动根据 `requirements.txt` 安装依赖并运行 `app.py`。

## 说明
- 若未配置 API key，系统会自动启用内置 fallback 规则评分与引导。
- 教师日志默认存储在 `logs/`，部署环境重启后可能不会持久化（取决于平台存储策略）。

## 静态 HTML 履历信息管理页（可部署 GitHub Pages）

本仓库新增了一个纯前端页面：
- `index.html`
- `styles.css`
- `script.js`

功能：
1. 分栏管理项目经历（项目名称、编号、主要工作、时间、级别）
2. 分栏管理论文信息（期刊、年份、作者排序等）
3. 分栏管理编著信息
4. 分栏管理讲座信息（时间、地点、摘要）
5. 每个栏目支持“启用编辑 + 新增/删除行”
6. 一键导出为 PDF

### 本地预览

```bash
python -m http.server 8000
```

浏览器打开：`http://localhost:8000`

### GitHub Pages 部署

1. 将代码推送到 GitHub 仓库（默认分支包含 `index.html`）
2. 进入仓库 **Settings → Pages**
3. Source 选择 **Deploy from a branch**
4. Branch 选择 `main`（或你的默认分支）和 `/root`
5. 保存后等待 Pages 构建完成，即可访问公开链接
