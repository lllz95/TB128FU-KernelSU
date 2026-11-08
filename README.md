# TB128FU-KernelSU

联想小新 Pad 2022（TB128FU / P89990JA1 / grass / SM6225）的通用内核构建工作流。

- 内核基线：Linux 4.19.157（联想官方源码）
- Root：ReSukiSU（现已改名 **BakaSU**）
- 隐藏：可选 SuSFS v2.3.0 + `path_umount` 回移 + `hide_stuff`
- 工具链：在线下载 AOSP clang + aarch64 gcc 4.9

> 本仓库只包含**构建流程**（工作流、补丁、脚本）。内核源码与工具链由输入参数指定，可在 Actions 页面按需选择。

---

## 相关仓库

| 仓库 | 用途 |
|---|---|
| `lllz95/TB128FU-KernelSU` | 本仓库：构建工作流 |
| `lllz95/TB128FU-Kernel` | 官方内核源码（内核树位于根目录） |
| `lllz95/android_kernel_tb128fu_from_Eddie07` | 第三方内核源码（可作为 techpack 来源） |

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
  extract_ikconfig.py                # 从 boot.img 提取内嵌 .config
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

内核在压缩包里的位置不需要手动指定——工作流会自动识别（见下文 `kernel_subdir`）。

### 2. 内核配置（二选一）

**方式 A：源码树里的 defconfig**

到内核源码的 `arch/arm64/configs/` 目录找对应文件，例如：

```
defconfig = P89990JA1-perf_defconfig
```

**方式 B：从 boot.img 提取**

```
boot_img_url = <boot.img 直链>
```

工作流会从 boot 镜像中提取内核内嵌的 `.config`（依赖 `CONFIG_IKCONFIG`）。

> 该 boot 镜像应与要构建的内核属于同一系统：构建当前系统内核就用当前系统的 boot。

---

## 输入参数说明

### 内核源码

| 输入 | 默认 | 作用 | 建议 |
|---|---|---|---|
| `kernel_repo` | 空 | 内核源码仓库链接 | 与 `kernel_pkg` 二选一 |
| `kernel_branch` | `main` | 源码分支 / tag | 固定版本时填 tag |
| `kernel_pkg` | 空 | 源码包直链 | 大文件建议先传 Release |
| `kernel_subdir` | 空 | 内核所在子目录 | **留空自动识别**；识别失败时手动填 |

`kernel_subdir` 留空时，工作流会在源码树里寻找同时满足以下条件的目录：

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

### 内核配置

| 输入 | 默认 | 作用 | 建议 |
|---|---|---|---|
| `defconfig` | 空 | 源码树中的 defconfig 名称 | 只填文件名，不要带路径 |
| `boot_img_url` | 空 | boot 镜像直链 | `defconfig` 为空时使用 |

`defconfig` 优先；两者都为空会直接报错。

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
| `ksu_variant` | `resukisu` | `resukisu` = ReSukiSU（现名 BakaSU） | 保持默认 |
| `ksu_ref` | `v4.2.0-rc3` | ReSukiSU 版本 | 固定版本便于复现 |
| `enable_susfs` | `false` | 是否添加 SuSFS | 需要隐藏时开启 |
| `susfs_version` | `latest` | `latest` = 内置 v2.3.0；`custom` 用自定义补丁 | 优先用 `latest` |
| `susfs_patch_url` | 空 | 自定义 SuSFS 补丁直链 | 仅 `custom` 时使用 |
| `susfs_hook_url` | 空 | 自定义 inline hook 脚本直链 | 仅 `custom` 时可选 |
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

## 构建流程

1. 拉取内核源码（仓库或源码包）
2. 自动识别内核根目录
3. 在线下载工具链（clang + gcc 4.9）
4. 按需从附加仓库复制 techpack
5. 短路 techpack in-tree 入口（`stub_techpack`）
6. 集成 ReSukiSU
7. 回移 `path_umount`（`enable_path_umount`）
8. SuSFS（`enable_susfs`）：
   - 内置 v2.3.0：打补丁 → 回移 inotify helper → 4.19 适配 → inline hook
   - `custom`：使用自定义补丁与 hook 脚本
   - 不开启时：打手动 hook 补丁
9. `hide_stuff`（`enable_hide_stuff`，最后执行）
10. 生成配置（`defconfig` 或从 boot.img 提取），追加 KSU / SuSFS / `LOCALVERSION` 等配置
11. 编译 `Image.gz`、内置模块、外部模块（可选）
12. 打包 `Image.gz` / `config.txt` / `modules.tar.gz` / `AnyKernel3.zip`
13. 发布到 Release

---

## 产物

Release 中包含：

| 文件 | 说明 |
|---|---|
| `Image.gz` | 内核镜像 |
| `config.txt` | 本次使用的完整配置 |
| `modules.tar.gz` | 内核内置模块 |
| `ext_modules.tar.gz` | 外部模块（`ext_modules=true` 时） |
| `AnyKernel3.zip` | 可用于 Recovery / 管理器刷入 |
| `SHA256SUMS.txt` | 校验值 |

---

## 刷机

### 方式 A：AnyKernel3

在支持 AnyKernel3 的 Recovery 或管理器中刷入 `AnyKernel3.zip`。

### 方式 B：重打包 boot.img

用原厂 boot 做底包，只替换 kernel 段（保留 ramdisk 与 DTB），然后：

```bash
fastboot flash boot_a boot.img
fastboot flash boot_b boot.img
fastboot reboot
```

> 重打包时必须保留原厂 DTB，否则无法开机。

## 恢复原厂

```bash
fastboot flash boot_a boot_a.img
fastboot flash boot_b boot_a.img
fastboot flash vbmeta_a vbmeta_a.img
fastboot flash vbmeta_b vbmeta_a.img
fastboot reboot
```

## 验证

```bash
adb shell uname -r                                   # 4.19.157-perf+
adb shell "grep -c . /proc/modules"                  # 模块数量
adb shell "cmd wifi status | grep 'Wifi is'"         # 已连接
adb shell "dumpsys bluetooth_manager | grep state"   # ON
adb shell "su -c id"                                 # uid=0
adb logcat -b all -d | grep -i incompatible          # 无输出
```

---

## 许可

- SuSFS 内核补丁与 hook 脚本来自 [simonpunk/susfs4ksu](https://gitlab.com/simonpunk/susfs4ksu)（GPL-2.0）与
  [JackA1ltman/NonGKI_Kernel_Build_2nd](https://github.com/JackA1ltman/NonGKI_Kernel_Build_2nd)（GPL-3.0）
- ReSukiSU / BakaSU 内核部分 GPL-2.0
