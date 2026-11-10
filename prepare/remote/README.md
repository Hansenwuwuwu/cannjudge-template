# 远端验证

不排队等 Judge，直接连 910B 把代码编译、跑九点、做 msprof。确认「编得过、数值对、哪个 pipe 慢」之后再走 `prepare/submit/`。

## 依赖

本地：

```powershell
pip install paramiko
```

远端：CANN 9.0.0（`/usr/local/Ascend/cann-9.0.0`）、`cmake`、`make`、`python3` + `numpy`、`msprof`，`/tmp` 可写。

## 服务器

服务器地址不预设，第一次用要自己提供：

| 项 | 默认 | 覆盖 |
| --- | --- | --- |
| host | 无，交互询问 | `--host` / `REMOTE_HOST` |
| port | `22` | `--port` / `REMOTE_PORT` |
| user | `root` | `--user` / `REMOTE_USER` |
| password | 每次运行询问 | `--password` / `REMOTE_PASSWORD` |

密码只走 `getpass`，不写文件、不进命令行历史。

## 准备 assets.tar.gz

仓库不带二进制包。第一次用之前自己打一个，结构：

```
assets/
├── source/                  # 从 assets_template/source 复制
├── runner/                  # 从 assets_template/runner 复制，main.cpp 按题目改
└── inputs/
    ├── case1/               # 每个 case 一个目录，放该题目的输入 bin
    └── case2/
```

```powershell
Copy-Item -Recurse prepare\remote\assets_template\* assets\
# 把九点输入放进 assets\inputs\caseN\
# 按题目改 assets\runner\main.cpp
tar -czf prepare\remote\assets.tar.gz -C assets .
```

`assets.tar.gz` 不进 git。`inputs/` 的文件名和 `runner/main.cpp`、`scripts/chk9.py` 的读取方式是绑定的，换题目要一起改。

远端目录：

```
/tmp/cannverify/
├── assets.tar.gz     # 自己打包的骨架 + runner + 输入
├── config.json       # 题目信息：算子名、文件路径、case 列表
├── source/           # 改名后的算子工程
├── runner/           # C++ runner
├── inputs/caseN/     # 每个 case 一个目录
├── up/               # 刚上传的 host.cpp / kernel.cpp / tiling.h / key.h
├── scripts/          # 远端执行脚本
├── build/            # libcust_opapi.so
└── build_runner/     # current_audit_runner
```

## 命令

```powershell
# 上传 → 编译 → 九点，一次连接做完，只问一次密码
python prepare/remote/remote_verify.py all

# 分步
python prepare/remote/remote_verify.py upload
python prepare/remote/remote_verify.py build
python prepare/remote/remote_verify.py run9

# 单个 case 做 msprof
python prepare/remote/remote_verify.py prof --case case8 --shape 5,17,33 --launches 8

# 临时命令 / 传文件
python prepare/remote/remote_verify.py shell --cmd "npu-smi info"
python prepare/remote/remote_verify.py put --local a.bin --remote /tmp/a.bin
python prepare/remote/remote_verify.py get --remote /tmp/out_case8/output_f16.bin --local out.bin
```

换机器时加参数即可：

```powershell
python prepare/remote/remote_verify.py all --host 10.0.0.1 --port 2222
```

`build` / `run9` 不会重新上传，改完本地代码要先 `upload`。

## 题目配置

先复制模板：

```powershell
Copy-Item prepare\remote\config.example.json prepare\remote\config.json
```

`config.json` 不进 git，换题目只改它。上传哪四个文件、有哪些 case，全部写在里面：

```json
{
  "op_name": "spmm_sum",
  "class_name": "SpmmSum",
  "audit_name": "spmm_sum_current_audit",
  "audit_class": "SpmmSumCurrentAudit",
  "aclnn_entry": "aclnnSpmmSumCurrentAudit",
  "files": {
    "host.cpp": "op_host/spmm_sum.cpp",
    "kernel.cpp": "op_kernel/spmm_sum.cpp",
    "tiling.h": "op_kernel/spmm_sum_tiling.h",
    "key.h": "op_kernel/tiling_key_spmm_sum.h"
  },
  "cases": []
}
```

`files` 的 key 是远端统一用的名字，value 是 `code/` 下的相对路径。
`rename_gen.py` 按 `op_name → audit_name`、`class_name → audit_class` 做替换，避免和线上的同名算子冲突。

`cases` 为空表示评测 shape 还没测。填法：

```json
"cases": [
  { "name": "case1", "shape": [1, 4] }
]
```

`shape` 写该题输入的主形状，具体到哪几维由题目决定。`spmmsum` 这类范围型题目，先跑通自适应实现，再用 `prepare/shape/` 的探针把 case 填进来。

## 输出怎么读

```
=== case1 -> R27_RUN_OK workspaceBytes=0 prefill=90 guards=OK inputs_immutable=OK wall_us=812 device_ms=0.31
...
=== numbers
case1  maxdiff=0.000244 bad=0
case2  maxdiff=0.000488 bad=0
```

| 输出 | 含义 |
| --- | --- |
| `R27_RUN_OK` + `guards=OK inputs_immutable=OK` | 没踩内存，输入没被改写 |
| `R27_RUN_ERROR` | 调用失败，多为 workspace / shape / tiling |
| `wrong input size` | 输入 bin 和 shape 对不上 |
| `maxdiff < 2e-3` 且 `bad=0` | 数值通过 |
| `bad>0` | 尾部或 padding 有问题 |
| `MISSING OUTPUT` | runner 没跑成功，先看上面报错 |

`device_ms` 含 launch 开销，不能当 Judge 用时。看分项用 `prof`：

```
 launch     dur     aic    cube     fix   a_scl    a_m1    a_m2     aiv     vec   v_scl    v_m2    v_m3
      0   12.34    9.87    9.10    0.32    0.45    3.21    2.10    2.47    2.18    0.30    1.90    0.12
```

## 换题目

| 文件 | 改什么 |
| --- | --- |
| `config.json` | `op_name`、`class_name`、`audit_*`、`aclnn_entry`、`files`、`cases` |
| `scripts/chk9.py` | `reference()` 换成新题目的公式 |
| `assets.tar.gz` | `runner/main.cpp` 的输入接口、`inputs/` 数据 |

只需要动这三处。`remote_verify.py`、`build_gen.sh`、`best9_gen.sh`、`t173_prof.sh` 都不用改。

## 常见错误

| 现象 | 处理 |
| --- | --- |
| `SSH 连接失败: timed out` | 机器关机或端口变了，换 `--host/--port` |
| `Authentication failed` | 密码错，重新输入 |
| `cmake_fail` | 看 `/tmp/cannverify/cmake.log`，确认 CANN 路径 |
| `runner_cmake_fail` | 看 `rcmake.log`，多为 aclnn 入口名不对 |
| `generated symbols absent` | 生成的 aclnn 名字和 runner 里的 `R27_API` 不一致 |
| `msprof 没有产出` | 看 `/tmp/prof_*/log` |
