# 产品演示材料

本目录只存放真实运行的产品截图。v0.2.1 本轮已通过本机隔离 DemoMode 完成真实浏览器视觉检查，并完成 M08 直接重命名提案与确认。截图显示 1280×720 深色界面和标题更新。当前浏览器截图接口没有将原始图像保存为仓库文件的本地能力，因此没有伪造或导出截图；截图目录仍为空，README 不引用不存在的图片。

| 计划文件 | 采集步骤 | 验收条件 | 状态 |
|---|---|---|---|
| `screenshots/01-conversation.png` | 打开 ChatWorkspace，显示会话与历史消息 | 来自真实本机 UI；不含私人内容 | TODO |
| `screenshots/02-memory-recovery.png` | 建立演示会话，重启本机服务后重新打开 | 从持久化目录恢复原会话及消息 | TODO |
| `screenshots/03-orchestration-clarification.png` | 输入“把当前会话改名” | 显示缺参追问；尚未执行 Command | TODO |
| `screenshots/04-orchestration-execution.png` | 提供标题、确认后等待查询读回和侧栏刷新 | 真实 Command 与 Query；不暗示通用 Planner | 本轮浏览器已检查；原图待人工保存 |
| `screenshots/05-follow-up-suggestions.png` | 开启推荐，点击建议使其填入输入框 | 输入框预填；没有自动发送 | TODO |
| `screenshots/06-test-results.png` | 在 PowerShell 执行测试与独立 API Smoke | 显示本轮实际命令和成绩 | TODO |
| `screenshots/07-architecture.png` | 在 GitHub 展示真实 README Mermaid 渲染 | GitHub 页面实际渲染，不制作模拟图 | TODO |
| `screenshots/08-learner-profile.png` | 展示学习者资料和 CEFR 字段 | 使用隔离 DemoMode 示例资料 | TODO |
| `screenshots/09-version-center.png` | 展开系统信息和 M01–M10 | 当前版本和十项演进真实可见 | TODO |

## 浏览器实测及人工截图步骤

本轮通过真实浏览器访问 `http://127.0.0.1:18501`，布局检查视口为 1280×720。核对了深色主题、演示提示、中文侧栏、标题、聊天区和成功反馈；完成了“我让你把当前对话改名为德语A1复习”及“确认”，页面显示 Command 执行后经 Conversation Query 核验，主标题显示新名称。图片只能在浏览器工具结果中查看，未保存为本地文件，因此没有新增截图证据文件。

后续人工截图步骤：

1. 在发布目录运行 `.\scripts\start_app.ps1 -DemoMode`，等待后端 `/health` 与 Streamlit `/_stcore/health` 通过。
2. 打开 `http://127.0.0.1:18501`，确认顶部显示“本机隔离演示模式”。
3. 新建会话，输入“把当前会话改名”，截图记录澄清问题；输入“德语A1复习”，截图记录待确认提案。
4. 输入“确认”，等待标题及侧栏同步，截图记录实际反馈。
5. 开启后续问题推荐，发送普通学习问题并点击一条推荐；截图应显示问题只填入输入框，未提交。
6. 展开学习者资料查看 CEFR；再展开“系统信息 · 版本更新”查看 v0.2.1 与 M01–M10。
7. 在 PowerShell 分别运行 `.\scripts\run_tests.ps1` 和 API Smoke，记录本轮终端输出。
8. 截图检查不得包含密钥、真实账号、真实会话或私人附件，确认后保存至本目录并更新上表。
