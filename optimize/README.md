# 阶段二：正式优化

前期准备跑通、九点全 Pass、基线记好之后，所有改动都在这里进行。

规则只有一条：**一次只改一个假设，一次只留一个版本目录，每次提交后必须落两条记录。**

## 结构

```
optimize/
├── README.md        本文件：干什么、怎么用、怎么迭代
├── PROGRESS.md      每次提交一小段：思路 + 效果
├── HANDOFF.md       多电脑交接，按需维护
├── baseline.md      第一次九点全 Pass 的基线与九点用时
└── versions/        每个改动一个目录
    └── 003_c8_split32/
        ├── code/            完整可提交目录
        └── NOTES.md         这次改了什么、为什么、预期
```

每个 case 的详细记录在仓库根的 `cases/`，一个 case 一个 md，按优化思路分类。

## 一次完整的流程

```powershell
# 1. 从当前最好版本复制（Windows PowerShell）
Copy-Item -Recurse optimize\versions\002_xxx optimize\versions\003_yyy

# 2. 改 003_yyy/code，写 NOTES.md（假设、改动、预期）

# 3. 提交
python prepare/submit/auto_submit.py optimize/versions/003_yyy/code --label 003_yyy

# 4. 拿到九点结果

# 5. 落两条记录
#    a. optimize/PROGRESS.md 追加一小段：这次思路 + 效果
#    b. cases/caseN.md 在对应「优化思路」分类下写详细：改了什么、用时变化

# 6. 决定去留
#    有收益：把 003_yyy/code 同步回根 code/，更新 baseline.md
#    无收益：NOTES.md 和 case md 都记结论，删掉 code/，只留文字
```

第 5 步是硬要求。没有记录的一次提交等于没做，下一轮无法判断是「这次真没收益」还是「上次记错了」。

## 三个记录文件的分工

| 文件 | 写什么 | 多长 |
| --- | --- | --- |
| `optimize/PROGRESS.md` | 每次提交一小段：日期版本、思路、效果、链接到 case md | 2–3 行 |
| `cases/caseN.md` | 这个 case 的详细记录，按优化思路分类 | 不限 |
| `optimize/HANDOFF.md` | 换机器时的状态交接 | 一页 |

`optimize/versions/<版本>/NOTES.md` 是改动前的计划，`PROGRESS.md` 是改动后的结果，两者不要混。

## PROGRESS.md 一段长什么样

```markdown
### 2026-11-12 003_c8_split32

- 思路：c8 改成八行一核，用 GatherMask 常量模式替掉运行时索引
- 效果：c8 9.00 → 6.00 µs，九点合计 56.86 → 53.86 µs，9/9 通过
- 详见：[case8](../cases/case8.md)
```

三段：思路、效果、去向。超过三行就说明应该写进 case md。

## case md 怎么分类

按**优化思路**分二级标题，不按时间流水账：

```markdown
# case8

## 概况
| 项 | 值 |
| --- | --- |
| shape | (5, 17, 33) |
| 基线用时 | 9.00 µs |
| 当前最好 | 6.00 µs |

## 访存：Gather 索引

### 2026-11-12 003_c8_split32
- 假设：每行固定开销 2.3µs 来自运行时构造索引
- 改动：常量位模式 + GatherMask(n)
- 结果：9.00 → 6.00 µs
- 结论：保留

## 归约

### ...
```

同一个 case 试过几条思路，就有几个二级标题。同一条思路下的多次尝试按时间往下排。

模板在 `cases/_template.md`，复制改名即可。

## 版本命名

```
001_baseline          原样提交，作为对照
002_c8_split32        一个假设一个目录
003_c5_dual_l0c
```

编号递增，名字里带 case 和手法。不要用 `test1`、`tmp`、`new`。

## 怎么判断去留

- 九点必须全 Pass，否则直接回退
- 总用时下降，且目标 case 明显下降 → 保留
- 单点变化 < 2 µs 且 < 10% → 视为噪声，不据此下结论
- 总用时下降但别的 case 明显变慢 → 先确认是不是把开销挪过去了
- 两次提交九点完全一致 → 先核对文件指纹，可能根本没提交上去

对着 `baseline.md` 比，不要对着上一次比。对着上一次容易把两个错误互相抵消当成进步。

## 和根 `code/` 的关系

- `code/` 永远等于「当前最好且已验证」的那一版
- 试验只在 `versions/<版本>/code` 里做
- 有收益才同步回 `code/`，并更新 `baseline.md`
- 无收益只留文字结论，删掉代码

## 什么时候更新 HANDOFF

只有换机器或交给别人继续时。写清楚当前最好版本、九点、卡点、下一步、远端环境和 Cookie 状态。平时不用动。
