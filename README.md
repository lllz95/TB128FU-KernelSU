# TB128FU-KernelSU

联想小新 Pad 2022（TB128FU / P89990JA1 / grass / SM6225）的内核构建工作流。

- 内核基线：Linux 4.19.157
- Root：**RKSU**（默认，当前可用版本 `v1.0.5-83-legacy`）；可选 ReSukiSU / BakaSU
- 隐藏：ReSukiSU 路线带 SuSFS；RKSU 1.0.5 暂未适配 SuSFS
- 工具链：优先源码自带 prebuilts，其次在线 AOSP clang + GNU binutils，也支持自定义 tar.gz

<details>
<summary><b>当前状态</b></summary>

- ReSukiSU
  - 无 SuSFS：可用
  - SuSFS v2.3.0：可用
- RKSU
  - 当前仅 `v1.0.5-83-legacy`（无 SuSFS）可用

</details>

<details>
<summary><b>仓库结构</b></summary>

```
.github/workflows/build-kernel.yml   # 构建工作流
patches/
  legacy_ksu_hooks.sh                 # 老式手动 hook（RKSU 1.0.5 默认）
  ksu_manual_hooks_4.19_grass.patch   # 联想专用手动 hook（ReSukiSU）
  susfs_v2.0.0_4.19_rksu.patch        # RKSU 3.x 用 SuSFS v2.0.0
  susfs_v2.3.0_4.19_resukisu.patch    # ReSukiSU 用 SuSFS v2.3.0
  debug_syslog.patch                  # 允许 adb shell 读 dmesg（调试用）
susfs/
  rksu_vfs_read_hook.py               # 精确插入 vfs_read hook
  rksu_sys_read_hook.py               # 插入 ksys_read hook
  rksu_initrc_extend.py               # 扩展 ksud.rc 注入条件
  rksu_debug_proc.py                  # /proc/ksu_dbg（仅 debug_syslog=true）
  rksu_v200_fdinfo.py                 # RKSU 3.x fdinfo 重建
  rksu_v200_try_umount.py             # RKSU 3.x try_umount
  lenovo_4_19_adapt.py                # ReSukiSU SuSFS 的联想适配
scripts/
  detect_kernel_root.py               # 自动识别内核所在目录
  path_umount_backport.sh             # 回移 path_umount()（4.19 没有）
ak3/
  anykernel.sh                        # AnyKernel3 模板
```

</details>

<details>
<summary><b>使用前准备</b></summary>

本仓库需要的“直链”，可以先上传至 Releases 或其他地方，之后复制分享链接粘贴到对应输入框。

<details>
<summary><b>内核源码</b></summary>

自备内核源码（或设备完整源码，工作流会自动定位内核源码，见 `kernel_subdir`），GitHub 公开仓库或压缩包皆可（压缩包需要上传直链）。

</details>

<details>
<summary><b>Root 方案（RKSU / ReSukiSU）</b></summary>

默认使用 **RKSU 1.0.5**：

- 克隆 `rksuorg/KernelSU` 的 `v1.0.5-83-legacy`
- 链接到 `drivers/kernelsu`
- 通过 `legacy_ksu_hooks.sh` 打老式手动 hook
- 写入配置：
  ```
  CONFIG_KSU=y
  CONFIG_THREAD_INFO_IN_TASK=y
  ```

也可以切回 ReSukiSU：

```
ksu_impl = resukisu
```

ReSukiSU 路径会使用 BakaSU 的 `setup.sh`，并支持 SuSFS 与 hide_stuff。

`enable_susfs=true` 对两种方案都生效：

- RKSU：自动改用 `rksu_susfs_ref`（默认 `susfs-rksu-master`），仅适用于 3.x
- ReSukiSU：使用内置 SuSFS v2.3.0 补丁

RKSU 需要配套的 RKSU 管理器；ReSukiSU 路径使用其自带管理器。

管理器配对：

| 内核 KSU 版本 | 管理器 |
|---|---|
| 12340（RKSU 1.0.5） | `v1.0.5-83-legacy` 12340 |
| 11838（KernelSU 0.9.x） | `v0.9.5` 11872 |
| 32359 | `v3.0.0-30-legacy` 32334 |
| 32447 | `v3.2.2-10-legacy` 32490 |

管理器版本低于内核通常可用；高于内核会出现“内核版本过低”或“获取 root 失败”。

</details>

<details>
<summary><b>内核配置</b></summary>

**推荐：读取当前系统的配置并上传，除非你确认源码内置的配置匹配当前系统**

用 adb 读取当前系统正在使用的内核配置：

```bash
adb shell "zcat /proc/config.gz" > stock_config.txt
```

如果 shell 没有权限，用 root：

```bash
adb shell su -c "zcat /proc/config.gz" > stock_config.txt
```

然后把 stock_config.txt（或 config.gz）上传至可用处，将直链填至：

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

</details>

</details>

<details>
<summary><b>输入参数说明</b></summary>

共 25 个输入。

<details>
<summary><b>内核源码</b></summary>

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

</details>

<details>
<summary><b>工具链</b></summary>

| 输入 | 默认 | 作用 | 建议 |
|---|---|---|---|
| `toolchain_repo` | AOSP clang prebuilts | 工具链仓库 | 一般不用改 |
| `toolchain_branch` | 空 | 工具链仓库分支 | 留空自动匹配；也可填 tag 或提交哈希 |
| `toolchain_ref` | `r370808` | clang 版本目录名 | 默认与 GNU binutils 2.27 兼容 |
| `toolchain_url` | 空 | 自定义 clang 工具链 tar.gz 直链 | 可选；填写后优先于仓库下载 |
| `gcc_repo` | AOSP gcc 4.9 | aarch64 gcc 仓库 | |
| `gcc_ref` | `android-11.0.0_r1` | gcc 仓库 tag | 该仓库 main 分支不含工具链，必须用 tag |

`toolchain_branch` 留空时，会依次尝试 `master-kernel-build-2022`、`android-12.0.0_r1`、`android-11.0.0_r1`、`master`、`main` 查找对应版本目录。

常用组合：

| clang 版本 | 所在分支 |
|---|---|
| `r370808`（默认，clang 10） | `android-11.0.0_r1` |
| `r450784e`（clang 14，需要更新 binutils） | `master-kernel-build-2022` |

优先级：

```
toolchain_url（tar.gz）
  > 源码仓库自带的 prebuilts
    > 在线 clang 仓库 + gcc 仓库
```

`toolchain_url` 必须是 **tar.gz**（保留可执行权限和符号链接），不要用 zip。

自定义工具链如果使用 clang 14，需要配套更新的 binutils（≥ 2.35），否则 vdso 汇编会失败；本仓库默认使用 binutils 2.27。

GNU binutils 默认来自 gcc tag `android-11.0.0_r1`（GNU ld 2.27），与 `r370808` 或 Snapdragon LLVM 10.0.7 兼容。

</details>

<details>
<summary><b>内核配置</b></summary>

| 输入 | 默认 | 作用 | 建议 |
|---|---|---|---|
| `config_url` | 空 | 原系统配置直链（`.config` / `config.gz`） | 推荐填写，见上文 |
| `defconfig` | 空 | 源码树中的 defconfig 名称 | 只填文件名，不要带路径 |

优先级：`config_url` > `defconfig` > 默认 `P89990JA1-perf_defconfig`。

</details>

<details>
<summary><b>techpack</b></summary>

| 输入 | 默认 | 作用 | 建议 |
|---|---|---|---|
| `stub_techpack` | `true` | 编译时短路内核树自带的 `techpack/wlan`、`techpack/audio` | 保持 true |

设备源码树有 `techpack` 就短路，避免出现兼容问题；没有则自动跳过。

</details>

<details>
<summary><b>Root / 隐藏</b></summary>

| 输入 | 默认 | 作用 | 建议 |
|---|---|---|---|
| `enable_ksu` | `true` | 是否集成 Root | 关闭可构建纯内核，用于对照测试 |
| `ksu_impl` | `rksu` | Root 方案 | 默认 RKSU，可切 `resukisu` |
| `rksu_ref` | `v1.0.5-83-legacy` | RKSU 版本（tag 或分支） | `ksu_impl=rksu` 且关闭 SuSFS 时使用 |
| `rksu_susfs_ref` | `susfs-rksu-master` | RKSU 的 SuSFS 分支 | `ksu_impl=rksu` 且开启 SuSFS 时使用 |
| `rksu_hook_mode` | `legacy` | RKSU hook 方式 | `legacy`（KernelSU_Action 同款）/ `legacy_extra`（含额外 hook）/ `official` |
| `ksu_ref` | `v4.2.0-rc3` | ReSukiSU 版本 | 可自行选择适合版本 |
| `enable_susfs` | `false` | 是否添加 SuSFS | ReSukiSU 支持；RKSU 3.x 支持；RKSU 1.0.5 暂不支持 |
| `susfs_version` | `default` | `default` = 内置补丁；`custom` 用自定义补丁 | 优先用 `default` |
| `susfs_patch_url` | 空 | 自定义 SuSFS 补丁直链 | 仅 `custom` 时使用 |
| `enable_hide_stuff` | `true` | 打 hide_stuff 清理痕迹 | 在所有补丁之后执行 |
| `debug_syslog` | `false` | 允许 `adb shell dmesg`，并注入 `/proc/ksu_dbg` | 仅调试时开启 |

`path_umount()` 回移固定开启（4.19 必需）。

</details>

</details>

<details>
<summary><b>产物</b></summary>

| 文件 | 说明 |
|---|---|
| `Image.gz` | 内核镜像 |
| `AnyKernel3.zip` | AK3 内核包，使用 REC 或相关工具刷入 |
| `SHA256SUMS.txt` | 校验值 |

跨 ROM 使用 AK3 时，内核版本与目标系统 vendor 模块必须匹配；非原厂内核出现 VINTF 提示属正常现象。

</details>

**许可**

- KernelSU / RKSU 内核部分：GPL-2.0-only；管理器部分：GPL-3.0-or-later
- RKSU 手动 hook 补丁：[rksuorg/kernel_patches](https://github.com/rksuorg/kernel_patches)（GPL-2.0）
- SuSFS 内核补丁与 hook 脚本：
  - [simonpunk/susfs4ksu](https://gitlab.com/simonpunk/susfs4ksu)（GPL-2.0）
  - [JackA1ltman/NonGKI_Kernel_Build_2nd](https://github.com/JackA1ltman/NonGKI_Kernel_Build_2nd)（GPL-3.0）
  - 新版接口参考：[ananjaser1211/Apollo](https://github.com/ananjaser1211/Apollo)、[ProtonKernel/Proton](https://github.com/ProtonKernel/Proton)、[sidex15/android_kernel_lge_sm8150](https://github.com/sidex15/android_kernel_lge_sm8150)（GPL-2.0）
- hide_stuff：[ShirkNeko/SukiSU_patch](https://github.com/ShirkNeko/SukiSU_patch)，遵循上游许可
- AnyKernel3 模板：[osm0sis/AnyKernel3](https://github.com/osm0sis/AnyKernel3)，遵循上游许可
- 本仓库的工作流与脚本：GPL-2.0
- 第三方文件保留其原始许可

