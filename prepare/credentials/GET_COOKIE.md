# 取 Cookie 与 userId

**Cookie 会过期。每次开始一轮提交前，都要重新向使用者要一次。**

工具不会把 Cookie 写进仓库。它只存在仓库外的：

```
%USERPROFILE%\.cannjudge\cookie.txt     # 一行，形如 a=b; c=d
%USERPROFILE%\.cannjudge\user_id.txt    # 一行，账号 _id
```

`auto_submit.py` 每次启动都会先打印上次保存的时间，然后询问：

- 直接回车 → 重新粘贴新的 Cookie
- 输入 `y` → 复用上次的

这是刻意设计的：Cookie 静默复用是「提交莫名其妙 401」的最常见原因。

## 取 Cookie

1. 浏览器登录 <https://cannjudge.cn>
2. `F12` → `Network`
3. 刷新页面
4. 点任意一条发往 `cannjudge.cn` 的请求
5. 在 `Request Headers` 里找到 `Cookie:`，复制**冒号后面的整段**

```
cannjudge_auth=eyJhbGciOi...; other=value
```

注意：

- 不要用 `document.cookie`，登录态通常是 `HttpOnly`，在 Console 里读出来是空的
- 不要带 `Cookie:` 前缀
- 不要只复制一个裸 token，格式必须是 `name=value; name2=value2`

## 取 userId

在 <https://cannjudge.cn> 页面按 `F12` → `Console`：

```javascript
JSON.parse(localStorage.getItem('cannjudge_user'))._id
```

复制输出的字符串。`userId` 不会过期，保存一次即可；换账号时需要重新取。

## 手动写入（可选）

```powershell
New-Item -ItemType Directory -Force "$env:USERPROFILE\.cannjudge" | Out-Null
Set-Content -Path "$env:USERPROFILE\.cannjudge\cookie.txt" -Value 'cannjudge_auth=...; other=...' -NoNewline
Set-Content -Path "$env:USERPROFILE\.cannjudge\user_id.txt" -Value '<你的 userId>' -NoNewline
```

## 也可以用参数或环境变量

优先级从高到低：

1. `--cookie` / `--user-id`
2. 环境变量 `CANNJUDGE_COOKIE` / `CANNJUDGE_USER_ID`
3. `%USERPROFILE%\.cannjudge\*` 存档

CI 或脚本里用 `--yes` 跳过交互，直接读存档或环境变量。

## 常见错误

| 现象 | 原因 | 处理 |
| --- | --- | --- |
| `401` / `403` | Cookie 过期 | 重新取一次 |
| `找不到用户` / `userId` | 缺 userId | 按上面 Console 取 |
| Cookie 格式不对 | 只粘了裸 token | 复制整段 `name=value; ...` |
| 提交成功但结果页是别人的 | 账号切换过 | 重新取 userId，`auto_submit.py` 会核对账号最新一条 |

## 安全

- Cookie 等价于账号登录态，不要发群、不要贴 issue、不要提交进 git
- `.gitignore` 已排除 `cookie.txt`、`user_id.txt`、`*.cookie`
- 共用机器时，用完可以删除 `%USERPROFILE%\.cannjudge\` 整个目录
