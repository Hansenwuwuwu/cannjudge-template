# CANNJudge Template

CANNJudge 算子比赛的通用起步仓库。下载下来，把比赛网站上的**题目空工程**整体放进 `code/`，就能开始改代码、看远端验证、自动提交、读评测结果。

仓库不含某道题的实现代码，也不带二进制包。远端验证要用的 `assets.tar.gz` 在第一次比赛时按 [prepare/remote/README.md](prepare/remote/README.md) 自己打。

## 三个阶段

```
prepare/    前期准备：环境、凭证、测 shape、远端验证、提交链路
optimize/   正式优化：版本目录、基线、每次提交的记录
cases/      每个 case 的详细优化记录，贯穿整个比赛
```

`prepare/` 下再分四部分：

```
prepare/
├── check_env.py   一键自检
├── credentials/   Cookie 与 userId
├── shape/         测隐藏 case 的 shape
├── remote/        远端 910B 验证：编译、九点、msprof
└── submit/        自动提交测试
```

`optimize/` 和 `cases/`：

```
optimize/
├── README.md      结构、迭代流程、记录规则
├── PROGRESS.md    每次提交一段：思路、效果、去向
├── HANDOFF.md     多电脑交接，按需维护
├── baseline.md    九点全 Pass 的基线
└── versions/      每个改动一个目录（code/ + NOTES.md）

cases/
├── README.md      怎么建、按优化思路分类的写法
├── _template.md   空模板
└── caseN.md       用的时候复制模板改名
```

先把 `prepare/` 全部跑通再进 `optimize/`。前期准备没做对，后面每次提交都可能是无效提交。

## 快速开始

```powershell
# 0. 克隆
git clone <this-repo> my-contest
cd my-contest

# 1. 写本地配置（不进 git）
Copy-Item prepare\contest.example.json prepare\contest.json
Copy-Item prepare\remote\config.example.json prepare\remote\config.json
#    按当前比赛改 contest.json；按当前题目改 remote\config.json

# 2. 把比赛网站下载的题目空工程解压后覆盖 code/
#    保持相对路径，例如 code/op_host/...、code/op_kernel/...

# 3. 自检：环境、网络、题目模板、code/ 是否齐全
python prepare/check_env.py

# 4. 按 prepare/credentials/GET_COOKIE.md 取一次 Cookie（会过期，每次提交前重新取）

# 5. 只核对要上传哪些文件，不提交
python prepare/submit/auto_submit.py --dry-run

# 6. 交一版基线，确认全部 case 通过
python prepare/submit/auto_submit.py --label 001_baseline

# 7. 题目不公开 shape 时，按 prepare/shape/README.md 逐轮探测，结果填进
#    prepare/remote/config.json

# 8. 可选：远端 910B 先编译并跑九点，减少无效提交
python prepare/remote/remote_verify.py all
```

跑完第 6 步会得到：

- 终端里的每个 case 用时表
- `prepare/submit/results/judge_<标签>_<时间>.json` 原始结果
- `prepare/submit/results/JUDGE_LOG.md` 追加一行汇总

把这次九点填进 `optimize/baseline.md`，就可以开始优化了。

## 每次提交后

两条记录都要写，缺一条下一轮就无法归因：

1. `optimize/PROGRESS.md` 追加一段：日期版本、思路、效果、链接
2. `cases/caseN.md` 在对应「优化思路」分类下写详细：假设、改动、结果、结论

模板和写法见 `cases/README.md`。

## 目录

| 路径 | 作用 |
| --- | --- |
| `code/` | 比赛题目空工程落点，提交时上传这里的内容；仓库本身留空 |
| `prepare/contest.example.json` | 赛事与题目 token 的模板，复制成 `contest.json` 使用 |
| `prepare/remote/config.example.json` | 题目文件映射与 case 列表模板，复制成 `config.json` 使用 |
| `prepare/check_env.py` | 前期准备自检，不提交、不改代码 |
| `prepare/credentials/GET_COOKIE.md` | 如何取 Cookie 和 userId |
| `prepare/shape/decode.py` | 按编码表把 Judge 用时解码成维度 |
| `prepare/remote/remote_verify.py` | SSH 到 910B：上传、编译、跑九点、msprof |
| `prepare/remote/config.json` | 题目名、四个文件路径、case 列表 |
| `prepare/remote/assets_template/` | runner 与 source 的 CMakeLists 骨架，用来打 `assets.tar.gz` |
| `prepare/submit/cannjudge_api.py` | CANNJudge HTTP 接口封装（只用标准库） |
| `prepare/submit/auto_submit.py` | 提交 → 等 180 秒 → 轮询结果 → 落盘 |
| `prepare/submit/results/` | 每次结果 JSON 和汇总表 |
| `cases/README.md` | case 记录怎么建、按优化思路分类的写法 |
| `cases/_template.md` | case 记录空模板 |
| `optimize/README.md` | 正式优化阶段：结构、迭代方式、记录规则 |
| `optimize/PROGRESS.md` | 每次提交一段：思路、效果、去向 |
| `optimize/HANDOFF.md` | 多电脑交接，按需维护 |
| `optimize/baseline.md` | 九点全 Pass 的基线 |
| `optimize/versions/` | 每个改动一个目录，含 `code/` 与 `NOTES.md` |

## 关于凭证

两套凭证都不进仓库：

- **CANNJudge Cookie**：会过期，每次提交前重新取。工具把最近一次存在仓库外的 `%USERPROFILE%\.cannjudge\cookie.txt`，下次运行仍会询问是否复用，直接回车就是重新粘贴。详情见 [prepare/credentials/GET_COOKIE.md](prepare/credentials/GET_COOKIE.md)。
- **远端 SSH 密码**：每次运行都重新询问，不写文件、不进命令行历史。地址和用户可用参数或环境变量提供，见 [prepare/remote/README.md](prepare/remote/README.md)。

`.gitignore` 排除了凭证、结果 JSON 和构建产物；`.gitattributes` 强制脚本与文档用 LF，避免远端 bash 读到 CRLF。

## 已知限制

| 项 | 当前行为 | 影响 |
| --- | --- | --- |
| 重复提交同一份代码 | 不拦截，直接 POST | 会白等一次评测；想避免可在提交前比对 `last_submission.json` 里的 sha256 |
| `--read-only` 的标签 | 默认 `baseline` | 单独读旧结果时日志会标错版本，需要手动传 `--label` |
| `prof` 的 shape | 要手输 `--case` 和 `--shape` | 容易和 `config.json` 不一致，核对一下再跑 |
| `versions/<版本>/code` | 整份复制 | kernel 变大后仓库会膨胀，超过二十个版本再考虑只存差异 |

## 上传到 GitHub

本机若没有 git，先安装 [Git for Windows](https://git-scm.com/download/win)，然后：

```powershell
cd cannjudge-template
git init
git add .
git commit -m "init: CANNJudge competition template"
git branch -M main
git remote add origin https://github.com/<你的账号>/<仓库名>.git
git push -u origin main
```

之后每次比赛：克隆仓库 → 覆盖 `code/` → 跑 `prepare/`。

## 参考资料

**赛事操作**

- [CANNJudge 开发者指南](https://gitcode.com/fuyangchenghu/cann-judge/blob/master/docs/%E5%9C%BA%E6%99%AF%E5%8C%96%E6%8C%87%E5%8D%97/CANNJudge%E5%BC%80%E5%8F%91%E8%80%85%E6%8C%87%E5%8D%97.md)：平台规则、提交方式、评测口径

**获奖代码与分析**

- [ascend-c-competition-archive](https://github.com/Hansenwuwuwu/ascend-c-competition-archive)：2026 电力巡检比赛获奖代码及逐题分析，本仓库的远端脚本与 shape 探测方法来自这里

**算子实现参考**

- [CANN-AscendC-optimization-Cases](https://github.com/HyosungSink/CANN-AscendC-optimization-Cases)：910B4 上的优质算子实现
- [CANN Samples](https://gitee.com/ascend/samples)：官方算子样例
- [CANN 9.0.0 文档](https://www.hiascend.com/document)：Ascend C API、`msprof`、CMake 构建规则

写新算子的代码时，先在这几份里找同名或同结构的实现，比从零试 API 快。
