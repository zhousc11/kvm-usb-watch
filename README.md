# kvm-usb-watch

用一个普通 USB KVM 切换器 + DDC/CI，在 macOS 上实现「键鼠切到哪台电脑，显示器输入源就自动跟过去」。

## 原理

1. **盯 KVM 的 USB Hub**：每 100ms 扫 IOKit `IOUSBHostDevice`，按 VID/PID + `locationID` 精确匹配 KVM 那颗 Hub（不是盯键鼠本身，所以 Hub 后面拔插设备不会误触）。
2. **防抖**：状态变化需稳定 0.4s 才确认。
3. **切输入**：Hub 消失 → 用 [`m1ddc`](https://github.com/waydabber/m1ddc) 写 VCP 60 切到另一台电脑的输入；Hub 回来 → 切回本机输入。
4. **校验重试**：写完等 0.8s 读回 VCP 60，不符合预期最多重试 3 次；`m1ddc` 单次 5s 超时。
5. **Windows 无信号复查**：切到 Windows 10s 后若键鼠仍不在本机、而显示器已自动回到本机输入（Windows 关机/无信号），弹通知提醒按 KVM 切回。
6. **通知 + 日志**：`osascript` 弹通知；日志写 `~/Library/Logs/kvm-usb-watch.log`，1MB 轮转、保留 3 份。
7. **常驻**：LaunchAgent，`RunAtLoad` + `KeepAlive`，限定 `Aqua`（图形登录会话，通知才弹得出来）。

## 适配你自己的设备

改 `kvm-usb-watch.py` 顶部常量：

| 常量 | 含义 | 怎么查 |
|---|---|---|
| `HUB_VID` / `HUB_PID` / `HUB_LOC` | KVM 的 USB Hub | `ioreg -p IOUSB -l -w0`，切 KVM 前后对比消失的 Hub |
| `INPUT_WIN` / `INPUT_MAC` | 两台电脑对应的 VCP 60 输入值 | `m1ddc display 1 get input`，或显示器 capabilities |
| `OK_READ` | 读回时可接受的值 | 有些显示器读回值与写入值不同（例：写 15 读回 16） |

参考配置（作者环境）：QSN-CBB 显示器，DP1=15（读回 16）→ Windows，HDMI2=18 → Mac mini；KVM Hub `1a40:0801`。

## 安装 / 卸载

```bash
brew install m1ddc
./install.sh     # 安装并启动
./uninstall.sh   # 卸载
```

## 已知问题

- 切换瞬间显示器 scaler 在切通道，VCP 60 可能短暂读回 0 或空，会触发重试；偶尔 3 次都没读到，会弹「失败」通知，但画面实际已切换。
- 与 MonitorControl 等同时访问 DDC 的软件可能偶发抢总线，靠重试兜底。
- 只支持 Apple Silicon（`m1ddc`）。
