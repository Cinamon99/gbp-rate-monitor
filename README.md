# 英镑汇率自动监测工具

自动监测中国银行英镑现汇卖出价，当价格低于设定阈值时，自动生成日历事件并推送通知到手机（支持iOS/Android）。

## 功能特点

- ⏱️ **工作日10分钟监测**：周一至周五，每10分钟自动获取最新汇率，周末休市不监测
- 📊 **数据来源**：中国银行官方外汇牌价
- 📱 **多平台推送**：支持 Bark、PushDeer、Server酱（微信）、Telegram Bot、WxPusher，覆盖 iOS 和 Android
- 📈 **趋势图生成**：自动生成24小时、7天、30天及历史趋势图
- 📅 **日历事件记录**：生成标准 `.ics` 日历文件，可订阅查看历史提醒
- ⚙️ **灵活配置**：阈值价格可随时通过 GitHub Secrets 调整，无需改代码
- 🚫 **智能防重复**：价格未创新低时不重复骚扰，价格回升后跌破才再次提醒

## 快速开始

### 1. Fork 本仓库

点击右上角的 Fork 按钮，将本仓库复制到你的 GitHub 账号下。

### 2. 配置 Secrets

在你的 Fork 仓库中，进入 `Settings` → `Secrets and variables` → `Actions`，添加以下 Repository secrets：

#### 必填配置

| Secret 名称 | 说明 | 示例值 |
|------------|------|--------|
| `THRESHOLD_PRICE` | 英镑卖出价提醒阈值（100外币兑人民币） | `920` |

#### 推送配置（至少选一种，支持 iOS 和 Android）

| Secret 名称 | 平台 | 说明 |
|------------|------|------|
| `BARK_DEVICE_KEY` | iOS/Android | Bark 推送设备 Key |
| `PUSHDEER_KEY` | iOS/Android/Mac | PushDeer 推送 Key |
| `SERVERCHAN_SENDKEY` | 微信（全平台） | Server酱 Turbo SendKey |
| `TELEGRAM_BOT_TOKEN` | 全平台 | Telegram Bot Token |
| `TELEGRAM_CHAT_ID` | 全平台 | Telegram 接收消息的 Chat ID |
| `WXPUSHER_TOKEN` | 微信（全平台） | WxPusher App Token |
| `WXPUSHER_UIDS` | 微信（全平台） | WxPusher 用户 UID（多个用逗号分隔） |

#### 如何设置阈值价格？

- 中国银行外汇牌价格式为 **100外币兑换多少人民币**
- 例如当前英镑卖出价为 915.71，即 100英镑 = 915.71元人民币
- 如果你想在价格低于 900 时收到提醒，设置 `THRESHOLD_PRICE=900`
- 可随时修改此值，无需重新部署

### 3. 启用 GitHub Actions

1. 进入仓库的 `Actions` 页面
2. 点击 "I understand my workflows, go ahead and enable them"
3. 找到 `GBP Exchange Rate Monitor` workflow，点击 `Run workflow` 手动触发一次测试

### 4. 接收通知

配置好推送方式后，当价格低于阈值时你会立即收到弹窗通知。无需额外订阅日历即可收到实时提醒。

如果你想在日历中查看历史提醒记录，可以在日历App中订阅 `gbp_alert.ics` 文件。

## 各推送方式配置指南

### iOS 推荐：Bark

1. 在 App Store 下载 [Bark](https://apps.apple.com/cn/app/bark/id1403753865)
2. 打开 App，复制你的设备 Key
3. 在 GitHub Secrets 添加 `BARK_DEVICE_KEY`

### Android 推荐方案

Android 用户有以下多种选择，推荐配置其中一种：

1. **Bark 安卓版**：从 F-Droid 或 Bark 官网下载安卓版 Bark 客户端
2. **PushDeer**：跨平台推送工具，支持 Android/iOS/Mac，官网：http://pushdeer.com
3. **Server酱（微信推送）**：通过微信接收通知，无需安装App。在 https://sct.ftqq.com 登录绑定微信获取 SendKey
4. **Telegram Bot**：全平台通用，适合已使用Telegram的用户
5. **WxPusher**：微信推送，类似Server酱

### Server酱配置（最简单，推荐安卓用户）

1. 访问 https://sct.ftqq.com
2. 用微信扫码登录
3. 复制你的 SendKey
4. 添加到 GitHub Secrets 的 `SERVERCHAN_SENDKEY`
5. 提醒会直接推送到你的微信「服务号通知」

### Telegram Bot 配置

1. 在 Telegram 中搜索 `@BotFather`，发送 `/newbot` 创建机器人，获取 Bot Token
2. 搜索刚创建的机器人，发送一条消息
3. 访问 `https://api.telegram.org/bot<你的Token>/getUpdates` 找到你的 Chat ID
4. 配置 `TELEGRAM_BOT_TOKEN` 和 `TELEGRAM_CHAT_ID`

## 趋势图查看

每次运行都会更新趋势图，保存在 `charts/` 目录下：

- `charts/daily.png` - 24小时价格走势
- `charts/weekly.png` - 7天价格走势（含最高/最低区间）
- `charts/monthly.png` - 30天价格走势
- `charts/all.png` - 全部历史走势

如果仓库是公开的，你可以通过以下链接直接查看：
```
https://raw.githubusercontent.com/你的用户名/你的仓库名/main/charts/daily.png
```

你可以将这些图片链接放在手机桌面快捷方式或小组件中随时查看。

## 日历订阅（可选）

如果你想在系统日历中记录所有提醒事件：

1. 仓库设置为公开（Public）
2. iOS: `设置` → `日历` → `账户` → `添加账户` → `其他` → `添加已订阅的日历`
3. Android: 在支持ICS订阅的日历App（如Google日历、DAVx5等）中添加订阅
4. 链接：`https://raw.githubusercontent.com/你的用户名/你的仓库名/main/gbp_alert.ics`

注意：日历事件本身不带闹钟提醒，真正的提醒通过推送通知实现。

## 手动运行

本地测试运行：

```bash
pip install -r requirements.txt
THRESHOLD_PRICE=920 python monitor.py
```

或者复制 `.env.example` 为 `.env`，修改配置后运行：

```bash
cp .env.example .env
python monitor.py
```

## 文件说明

| 文件/目录 | 说明 |
|------|------|
| [monitor.py](file:///Users/rose/Library/Application%20Support/TRAE%20SOLO%20CN/ModularData/ai-agent/work-mode-projects/6a4ef6ababa488f88b58d599/monitor.py) | 主监测脚本（汇率抓取、图表生成、推送） |
| [monitor.yml](file:///Users/rose/Library/Application%20Support/TRAE%20SOLO%20CN/ModularData/ai-agent/work-mode-projects/6a4ef6ababa488f88b58d599/.github/workflows/monitor.yml) | GitHub Actions 配置 |
| [requirements.txt](file:///Users/rose/Library/Application%20Support/TRAE%20SOLO%20CN/ModularData/ai-agent/work-mode-projects/6a4ef6ababa488f88b58d599/requirements.txt) | Python 依赖 |
| `charts/` | 趋势图输出目录（自动更新） |
| `gbp_alert.ics` | 日历事件文件（自动更新） |
| `rate_data.json` | 价格历史数据（自动更新） |
| `latest_rate.json` | 最新汇率数据（自动更新） |

## 修改阈值

随时调整提醒阈值，无需修改代码：

1. GitHub → `Settings` → `Secrets and variables` → `Actions`
2. 编辑 `THRESHOLD_PRICE`
3. 下次运行自动生效（工作日每10分钟一次）
4. 也可手动触发 workflow 立即生效

## 提醒逻辑

- 价格 **首次跌破阈值** → 立即推送弹窗通知
- 价格 **继续下跌创出新低**（低于上次提醒价）→ 再次推送通知
- 价格在阈值下但 **未创新低** → 不重复提醒（避免骚扰）
- 价格 **回升到阈值以上后再次跌破** → 重置并重新提醒
- 周末/非工作日 → 不运行（中国银行不更新牌价）
- 所有提醒事件都会记录到日历文件中供回溯查看

## 注意事项

- GitHub Actions 免费额度：每月2000分钟，按工作日每天运行约60次（10分钟一次），每次运行约1分钟计算，每月消耗约 22天 × 60次 × 1分钟 = 1320分钟，在免费额度内
- 中国银行外汇牌价主要在工作日更新，周末价格不变故不监测
- 趋势图会保留90天数据，旧数据自动清理
- 支持同时配置多种推送方式，会同时向所有配置的渠道发送通知

## 工作原理

1. GitHub Actions 工作日每10分钟运行脚本
2. 脚本爬取中国银行官网外汇牌价页面，解析英镑卖出价
3. 记录价格点到历史数据，更新趋势图
4. 与阈值比较：
   - 低于阈值且满足提醒条件 → 添加日历事件 + 发送推送通知
   - 高于阈值 → 仅记录数据，重置提醒状态
5. 自动提交所有更新回仓库
6. 手机收到推送弹窗通知

## License

MIT License
