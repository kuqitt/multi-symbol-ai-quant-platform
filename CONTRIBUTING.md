# Contributing / 贡献指南

## English

Thank you for considering contributing to this project.

### Before You Start

- Read [README.md](README.md), [DISCLAIMER.md](DISCLAIMER.md), and [LICENSE](LICENSE).
- Do not submit real API keys, exchange credentials, bot tokens, chat IDs, or operator-specific secrets.
- Keep the project safety-first. Changes that weaken default risk controls are unlikely to be accepted.

### Recommended Workflow

1. Open an issue for bugs, roadmap ideas, or architectural proposals.
2. Keep pull requests focused and small when possible.
3. Add or update tests for behavior changes.
4. Update documentation when changing APIs, config, or operator workflow.
5. Prefer paper, testnet, and demo workflows over live-trading assumptions.

### Coding Expectations

- Preserve existing style unless a refactor is necessary.
- Fix root causes instead of adding surface-level patches.
- Avoid unrelated formatting churn.
- Add comments only when the logic is not obvious.
- Keep operator safety and observability in mind.

### Pull Request Checklist

- I verified the feature locally.
- I ran relevant backend tests.
- I updated docs if behavior changed.
- I did not commit secrets or personal runtime data.
- I considered risk-control and approval implications.

### Security Issues

Do not open a public issue for credential leaks, auth bypasses, or vulnerabilities that could put user funds or systems at risk.

Instead, disclose responsibly to the repository maintainers through a private channel once the project governance process is established.

## 简体中文

感谢你参与这个项目的开源共创。

### 开始之前

- 先阅读 [README.md](README.md)、[DISCLAIMER.md](DISCLAIMER.md) 和 [LICENSE](LICENSE)。
- 不要提交真实 API Key、交易所密钥、机器人 Token、聊天 ID 或运维侧私密信息。
- 项目以安全优先为原则。任何削弱默认风控的改动都不太可能被接受。

### 推荐流程

1. 对 bug、路线图或架构方案先提 issue。
2. PR 尽量聚焦，避免一次性混入太多无关修改。
3. 行为变化要补测试或更新现有测试。
4. 改动 API、配置或操作流程时同步更新文档。
5. 优先围绕 paper、testnet、demo 场景设计，不要默认按实盘处理。

### 代码要求

- 尽量保持现有风格，除非确实需要重构。
- 优先修根因，不要只做表层补丁。
- 避免无关格式化噪音。
- 只有在逻辑不直观时才补注释。
- 始终考虑操作安全和可观测性。

### PR 自查清单

- 我已经在本地验证过功能。
- 我已经运行过相关后端测试。
- 如果行为变化，我已经更新文档。
- 我没有提交任何密钥或个人运行数据。
- 我已经考虑风控和审批链路的影响。

### 安全问题

如果发现密钥泄露、鉴权绕过、资金风险类漏洞，不要直接公开提 issue。

请在项目治理流程建立后，通过维护者指定的私下渠道负责任披露。