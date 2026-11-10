# 阶段一：前期准备

目标：在动第一行算子代码之前，确认「能编译、能验证、能提交、能读到结果」。这一阶段不改算法，只把链路打通。

前期准备分四部分，另有一个总自检：

```
prepare/
├── check_env.py     一键自检：Python、目录、网络、题目模板、凭证状态
├── credentials/     凭证：Cookie 与 userId，每次重新取
├── shape/           测隐藏 case 的 shape：空转计时、误差反推、解码工具
├── remote/          远端验证：SSH 到 910B 编译、跑九点、msprof
└── submit/          自动提交测试：提交 → 等 180 秒 → 读结果 → 落盘
```

| 部分 | 入口 | 完成标志 |
| --- | --- | --- |
| 总自检 | `python prepare/check_env.py` | Python、目录、网络、题目解析全部 `[OK]` |
| 题目空工程 | 直接把下载的工程覆盖 `code/` | 自检显示「已覆盖模板要求的全部可编辑文件」 |
| 凭证 | [credentials/GET_COOKIE.md](credentials/GET_COOKIE.md) | 自检凭证一行显示 `[有]` |
| 测 shape | [shape/README.md](shape/README.md) | 每个 case 的 `d`、秩、`M`、完整 shape 都有读数支撑 |
| 远端验证 | [remote/README.md](remote/README.md) | 九点 `bad=0`，或 `msprof` 出分项 |
| 自动提交测试 | [submit/README.md](submit/README.md) | 九点出结果，`submit/results/JUDGE_LOG.md` 出现一行 |

## 顺序

1. **自检**：`python prepare/check_env.py`，确认能连上 cannjudge.cn、能解析到当前题目
2. **放空工程**：把比赛网站下载的题目工程整体覆盖到 `code/`，保持 `op_host/`、`op_kernel/` 相对路径
3. **凭证**：按 [credentials/GET_COOKIE.md](credentials/GET_COOKIE.md) 取 Cookie 与 userId；Cookie 会过期，每轮提交前重取
4. **只核对**：`python prepare/submit/auto_submit.py --dry-run`，确认要上传的文件
5. **测 shape**（题目不公开时）：按 [shape/README.md](shape/README.md) 先用全 Pass 基线确认 case 数，再逐轮用空转探针测出每个 case 的维度，填进 `remote/config.json`
6. **远端验证**（可选但推荐）：按 [remote/README.md](remote/README.md) 跑九点，先排除编译和数值问题
7. **第一次真提交**：`python prepare/submit/auto_submit.py`，等 180 秒读九点
8. **记基线**：把九点用时填进 [../optimize/baseline.md](../optimize/baseline.md)

第 7 步是链路验证，不是优化。哪怕九点全是 `Compile Error` 也算打通了链路——说明提交、等待、读结果三件事都通了，接下来只需要关心代码。

测 shape 之所以放在这里，是因为它依赖「能提交、能读用时」这条链路。如果题目已经公开 shape，跳过这一步。

## 远端验证和自动提交的分工

| | 远端验证 | 自动提交 |
| --- | --- | --- |
| 机器 | 自己连的 910B | Judge 云端 |
| 等多久 | 编译 1-3 分钟，跑九点几十秒 | 提交后等 180 秒起 |
| 能拿到什么 | 编译错误、`maxdiff`、`bad`、msprof 分项 | 官方九点用时、误差比例、排名 |
| 适合什么时候用 | 每次改完代码 | 确认远端九点通过后 |

远端验证不能替代 Judge：两边机器的核数、频率、调度都可能有差异。它只用来减少无效提交。

## 为什么单独做一个阶段

失败的提交有四种，前两种在这一阶段就该排除：

- 文件没放对 → `code/` 缺模板文件，提交直接报错
- Cookie 过期 → 401/403，或者提交请求被拒
- 代码编译不过 → 后面的结果全无意义
- 数值不对 → 属于 `optimize/` 的事

## 凭证

两套凭证都在这一阶段处理：

- **CANNJudge**：Cookie + userId，会过期，每次提交前重新取，见 [credentials/GET_COOKIE.md](credentials/GET_COOKIE.md)
- **远端 SSH**：host / port / user / password，密码每次运行都重新询问，不写文件，见 [remote/README.md](remote/README.md)

两套都遵守同一条规则：**凭证不进仓库，密码不落盘。**
