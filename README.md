# TB128FU-KernelSU

联想小新 Pad 2022（TB128FU / P89990JA1 / grass / SM6225）的内核构建工作流。

- 内核基线：Linux 4.19.157
- Root：ReSukiSU（现已改名 **BakaSU**）
- 隐藏：可选 SuSFS v2.3.0 + `path_umount` 回移 + `hide_stuff`
- 工具链：优先使用源码仓库自带的 prebuilts，否则在线下载 AOSP clang + gcc

---

## 仓库结构

```
.github/workflows/build-kernel.yml   # 构建工作流
patches/
  ksu_manual_hooks_4.19_grass.patch  # 不使用 SuSFS 时的手动 hook
  susfs_v2.3.0_4.19_grass.patch      # SuSFS v2.3.0 内核补丁（内置）
  susfs_inline_hook_patches.sh       # SuSFS inline hook 脚本
  module_force_load.patch            # 跳过模块 vermagic/CRC 校验（调试用）
  debug_syslog.patch                 # 允许 adb shell 读 dmesg（调试用）
susfs/
  inotify_mask_backport.py           # 回移 inotify_mark_user_mask()（4.19 没有）
  lenovo_4_19_adapt.py               # fdinfo.c / namespace.c 的 4.19 适配
scripts/
  detect_kernel_root.py              # 自动识别内核所在目录
  path_umount_backport.sh            # 回移 path_umount()（4.19 没有）
ak3/
  anykernel.sh                       # AnyKernel3 模板
```

---

## 使用前准备

本仓库需要的“直链”，可以先上传至 Releases，也可以上传至其他可分享直链的网盘，之后复制分享链接粘贴到对应输入框。

### 1. 内核源码（二选一）

**方式 A：源码仓库**

```
kernel_repo   = https://github.com/lllz95/TB128FU-Kernel
kernel_branch = main
```

**方式 B：源码包直链**

```
kernel_pkg = <tar.gz 直链>
```

两种方式都可以填**内核源码仓库/包**，也可以填**设备源码仓库/包**（厂商整包）。

内核在源码里的位置不需要手动指定——工作流会自动识别（见 `kernel_subdir`）。

### 2. 内核配置

**推荐：读取当前系统的配置并上传**

用 adb 读取当前系统正在使用的内核配置：

```bash
adb shell "zcat /proc/config.gz" > stock_config.txt
```

如果 shell 没有权限，用 root：

```bash
adb shell su -c "zcat /proc/config.gz" > stock_config.txt
```

然后把 `stock_config.txt`（或 `config.gz`）上传到 Releases / 网盘，把直链填到：

```
config_url = <配置直链>
```

工作流支持 `.config` 文本和 `config.gz` 压缩包，会自动识别。

**不填 `config_url` 时**：使用内核源码里的 defconfig。

```
defconfig = P89990JA1-perf_defconfig
```

如果 `defconfig` 也留空，默认使用源码树的 `P89990JA1-perf_defconfig`。

**风险提示**：源码仓库的配置可能与当前系统不匹配，可能导致 vendor 模块无法加载（CRC/vermagic 不一致）、VINTF 提示或外设异常。建议读取当前系统配置后上传，再构建。

---

## 输入参数说明

### 内核源码

| 输入 | 默认 | 作用 | 建议 |
|---|---|---|---|
| `kernel_repo` | 空 | 内核源码仓库链接 | 与 `kernel_pkg` 二选一 |
| `kernel_branch` | `main` | 源码分支 / tag | 固定版本时填 tag |
| `kernel_pkg` | 空 | 源码包直链 | 大文件建议先传 Release |
| `kernel_subdir` | 空 | 内核所在子目录 | **留空自动识别**；识别失败时手动填 |

`kernel_subdir` 留空时，工作流会寻找同时满足以下条件的目录：

1. 有 `Makefile`，且包含 `VERSION =` 与 `PATCHLEVEL =`
2. 有 `arch/arm64/`
3. 有 `include/linux/kconfig.h`

搜索顺序：根目录 → `kernel/`、`kernel-4.19.x/`、`src/kernel/`、`linux-4.19*` → 最多向下 3 层。

### 工具链

| 输入 | 默认 | 作用 | 建议 |
|---|---|---|---|
| `toolchain_repo` | AOSP clang prebuilts | 工具链仓库 | 一般不用改 |
| `toolchain_branch` | `main` | 工具链仓库分支 | 需要固定时填 tag 或提交哈希 |
| `toolchain_ref` | `r450784e` | clang 版本目录名 | **若编译报错，请更换其他版本**（如 `r383902b1`） |
| `gcc_repo` | AOSP gcc 4.9 | aarch64 gcc 仓库 | |
| `gcc_ref` | `main` | gcc 仓库分支 / tag | |

如果源码仓库自带 `prebuilts/`（例如设备源码包），会优先使用仓库内的 clang 与 gcc；仓库里没有对应版本时才在线下载。

### 内核配置

| 输入 | 默认 | 作用 | 建议 |
|---|---|---|---|
| `config_url` | 空 | 原系统配置直链（`.config` / `config.gz`） | 推荐填写，见上文 |
| `defconfig` | 空 | 源码树中的 defconfig 名称 | 只填文件名，不要带路径 |

优先级：`config_url` > `defconfig` > 默认 `P89990JA1-perf_defconfig`。

### techpack

| 输入 | 默认 | 作用 | 建议 |
|---|---|---|---|
| `use_techpack` | `false` | 主仓库 techpack 不全时，从附加仓库拉取 | 内核树里已有 `techpack/` 时不需要 |
| `techpack_repo` | 空 | 第三方内核源码仓库链接 | `use_techpack=true` 时必填 |
| `techpack_branch` | `main` | 附加仓库分支 | |
| `stub_techpack` | `true` | 编译内核时短路 techpack，避免驱动编进内核 | **保持 true**；内置厂商驱动会触发 TZ/RPM abort |

`use_techpack` 负责“把源码拿进来”，`stub_techpack` 负责“编译时不要编进去”，两者作用阶段不同。

### Root / 隐藏

| 输入 | 默认 | 作用 | 建议 |
|---|---|---|---|
| `ksu_ref` | `v4.2.0-rc3` | ReSukiSU（现名 BakaSU）版本 | 固定版本便于复现 |
| `enable_susfs` | `false` | 是否添加 SuSFS | 需要隐藏时开启 |
| `susfs_version` | `default` | `default` = 内置 v2.3.0；`custom` 用自定义补丁 | 优先用 `default` |
| `susfs_patch_url` | 空 | 自定义 SuSFS 补丁直链 | 仅 `custom` 时使用 |
| `enable_path_umount` | `true` | 回移 `path_umount()` | **4.19 必须保持开启** |
| `enable_hide_stuff` | `true` | 打 hide_stuff 清理痕迹 | 在所有补丁之后执行 |
| `debug_syslog` | `false` | 允许 `adb shell dmesg` | 仅调试时开启 |
| `force_modules` | `false` | 跳过模块 vermagic/CRC 校验 | 仅调试时开启 |

### 构建

| 输入 | 默认 | 作用 | 建议 |
|---|---|---|---|
| `ext_modules` | `false` | 是否额外编译外部模块（`.ko`） | 需要单独加载驱动时开启 |
| `ext_module_dirs` | `techpack/wlan` | 外编目录，空格分隔 | 如 `techpack/wlan/qcacld-3.0 techpack/audio` |

外部模块不会进入内核镜像，编译后单独输出，使用时 `insmod` 加载。

---

## 产物

| 文件 | 说明 |
|---|---|
| `Image.gz` | 内核镜像 |
| `config.txt` | 本次使用的内核 `.config` |
| `build-params.txt` | 本次构建填写的参数记录 |
| `modules.tar.gz` | 内核内置模块 |
| `ext_modules.tar.gz` | 外部模块（`ext_modules=true` 时） |
| `AnyKernel3.zip` | AK3 内核包，使用 REC 或相关工具刷入 |
| `SHA256SUMS.txt` | 校验值 |

---

## 刷机

### 方式 A：AnyKernel3

在支持 AnyKernel3 的 Recovery 或相关工具中刷入 `AnyKernel3.zip`。

### 方式 B：boot 镜像

本仓库不再生成修补后的 boot 镜像。需要自行用产物修补：

- 以当前系统的 boot.img 为底
- 用 `Image.gz` 替换 kernel 段
- 保留原 ramdisk 与 DTB

刷入：

```bash
fastboot flash boot_a boot.img
fastboot flash boot_b boot.img
fastboot reboot
```

> 自行修补时必须保留原厂 ramdisk 与 DTB，否则无法开机。

---

## 许可

- SuSFS 内核补丁与 hook 脚本来自 [simonpunk/susfs4ksu](https://gitlab.com/simonpunk/susfs4ksu)（GPL-2.0）与
  [JackA1ltman/NonGKI_Kernel_Build_2nd](https://github.com/JackA1ltman/NonGKI_Kernel_Build_2nd)（GPL-3.0）
- ReSukiSU / BakaSU 内核部分 GPL-2.0
