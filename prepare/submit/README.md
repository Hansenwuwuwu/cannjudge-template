# 自动提交测试

一条命令完成：**提交 → 等 180 秒 → 读结果 → 落盘**。

```powershell
python prepare/submit/auto_submit.py
```

默认提交仓库根目录的 `code/`，标签为 `baseline`。

## 常用变体

```powershell
# 只核对要上传哪些文件，不 POST
python prepare/submit/auto_submit.py --dry-run

# 给这一版起个名字，方便在结果表里区分
python prepare/submit/auto_submit.py --label c8_split32

# 提交后不等这么久
python prepare/submit/auto_submit.py --wait 90

# 提交卡住或没读到结果时，只读指定编号
python prepare/submit/auto_submit.py --read-only 6a1b2c3d

# CI / 非交互：直接用存档 Cookie
python prepare/submit/auto_submit.py --yes
```

| 参数 | 默认 | 说明 |
| --- | --- | --- |
| `code_dir` | `code/` | 含 `op_host/`、`op_kernel/` 的目录 |
| `--dry-run` | 关 | 只核对载荷，不提交 |
| `--read-only ID` | — | 不提交，只读这个编号 |
| `--label` | 目录名 | 结果 JSON 与日志表里的版本名 |
| `--wait` | `180` | 提交后先等多少秒 |
| `--poll-interval` | `3` | 轮询间隔（秒） |
| `--max-polls` | `100` | 最多轮询次数 |
| `--cookie` / `--user-id` | 空 | 覆盖存档凭证 |
| `--contest` / `--problem` / `--group` | `2026_electronic` / `swiglu` / 公开小组 | 赛事与题目 token |
| `--extra-file` | 无 | 额外上传 `code_dir` 下的文件，可重复 |
| `--yes` | 关 | 非交互，直接用存档 Cookie |

换比赛时最常改的是 `--contest` 和 `--problem`，也可以设环境变量：

```powershell
$env:CANNJUDGE_CONTEST = "2026_xxx"
$env:CANNJUDGE_PROBLEM = "yyy"
```

## 时间线

```
t=0       POST /api/submissions/submit
t=0       submissionId 写入 results/last_submission.json
t=0~180   sleep（这段时间评测在云端跑）
t=180     开始 GET /api/submissions/{id}，每 3 秒一次
t≈180-480 出结果：打印九点、写 JSON、追加 JUDGE_LOG.md
t>480     仍未出结果：提示用 --read-only 稍后再读
```

180 秒是按「通常 1-3 分钟出结果」留的余量。等太久浪费，等太短会频繁打接口。

## 落盘

```
prepare/submit/results/
├── JUDGE_LOG.md                     # 一行一次提交，方便横向比较
├── last_submission.json             # 最近一次提交的编号与文件指纹
└── judge_<标签>_<时间>.json         # 完整响应 + 九点
```

`JUDGE_LOG.md` 的列：

| 列 | 含义 |
| --- | --- |
| 标签 | `--label` 或目录名 |
| 结果 | `通过数/总数` |
| c1–cN | 每个 case 的用时（µs）或错误状态，N 是当前题目的 case 数 |
| 合计 | 全部 case 用时相加 |
| 编号 | submission id 前 8 位 |

`judge_*.json` 里保留了完整的 `submission` 原始响应，后续要查 `best_time`、`precision_ratio`、报错文本都以它为准。

## 结果怎么读

终端输出示例：

```
评测结束: 状态 = Accepted，通过 9/9
  case 1: Pass  [用时 1.23 µs ★本次最优]
  case 2: Pass  [误差比例 0.00%，用时 4.56 µs，最优 4.40 µs]
  ...
用时合计: 56.86 µs，单 case 最长 12.34 ms
```

- `★本次最优`：这次用时 ≤ 历史最优，说明是有效进步或至少没退
- `误差比例`：`(1 - precision_ratio) * 100%`，不为 0 说明数值有偏
- 有 `msg` 时会先打印编译/运行错误，此时不打印用时表

退出码：

| 码 | 含义 |
| --- | --- |
| `0` | 状态 `Accepted` / `Pass` |
| `1` | 网络、凭证、载荷错误 |
| `2` | 没读到最终结果，或归属核对不通过 |
| `3` | 读到了结果，但状态不是 Accepted |

## 归属核对

一次只交一份。结果落盘前会查账号下最新一条提交：

- 最新编号 == 本次编号 → 记录
- 不相等 → 拒绝记录，避免把别人的结果当成自己的

没有 userId 时会跳过这一步并打印提示。

## 常见失败

| 现象 | 原因 | 处理 |
| --- | --- | --- |
| `本地缺少模板要求的文件` | `code/` 路径和模板不一致 | 重新解压题目空工程，保持相对路径 |
| `编译错误` 且带 `msg` | 代码问题 | 看 `msg` 第一段，通常是缺头文件或 API 名不对 |
| 九点全 `Wrong Answer` | 数值或 shape 分支错 | 先本地跑数值比对，再提交 |
| `触发限流` | 提交太频繁 | 脚本会等 5 秒重试，超过 2 倍限流阈值会直接停 |
| 一直 `Pending` | 队列长 | 用 `--read-only` 过几分钟再读 |
| `注意: xxx 引用了 yyy` | 本地头文件不在模板里，接口不会上传 | 要么内联进 `.cpp`，要么用 `--extra-file` 显式上传 |

## 为什么不直接调网页

网页提交要手点、要等、要复制结果。这个脚本做的是同一套接口：

- `POST /api/submissions/submit`：提交
- `GET /api/submissions/{id}`：读结果

和 [cannjudge-auto-submit](https://gitcode.com/luanchess/cannjudge-auto-submit) 的 `submit-api.js` 一致，只是不需要 Node。
