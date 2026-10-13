# D2R Mobile · GitHub Actions 构建与自动发布

[English](README.md) | **简体中文**

[![Build IPA](https://github.com/jiayx/d2r-mobile-build/actions/workflows/pack.yml/badge.svg)](https://github.com/jiayx/d2r-mobile-build/actions/workflows/pack.yml)
[![Export resources](https://github.com/jiayx/d2r-mobile-build/actions/workflows/resources.yml/badge.svg)](https://github.com/jiayx/d2r-mobile-build/actions/workflows/resources.yml)

基于 [jhaizhou-ops/d2r-mobile](https://github.com/jhaizhou-ops/d2r-mobile) 的 **NO_XCODE** 方案，在 GitHub Actions 的 Ubuntu runner 上生成未签名 IPA、导出配套游戏资源，并在成功后自动发布 Release。

本仓库保存构建脚本和固定版本配置。IPA 和资源文件作为 Release / Actions 附件保存，主机密钥和下载输入放在 Actions Secrets 中，不提交到 Git。

## 下载与安装

进入 **[最新 Release](https://github.com/jiayx/d2r-mobile-build/releases/latest)**，在 Assets 中下载：

| 附件 | 用途 |
| --- | --- |
| `D2RMobile-unsigned.ipa` | 约 126MB，用 Sideloadly 签名并安装 |
| `D2R-Mobile-Resources.zip.001`、`.002`、`.003` | 配套资源 ZIP 的三个分卷，必须全部下载，总计约 5.42GB |
| `Resources-Parts-SHA256SUMS.txt` | 检查三个分卷是否完整 |
| `Resources-SHA256SUMS.txt` | 检查合并后的 ZIP |
| `RESOURCE-INSTALL.txt` | 分卷合并和资源导入说明 |
| `build-report.json`、`resources-report.json`、`SHA256SUMS.txt` | 版本、逐文件大小与 SHA256 等校验信息 |

GitHub 自动附带的 `Source code` 压缩包是构建脚本源码。

### 1. 安装 IPA

手机需要 **iOS 26 或以上**。用 Sideloadly 签名并安装 IPA，按系统提示完成信任设置。

**IPA 内包含游戏程序和转换后的着色器等生成内容，地图、模型、音频等大资源需要另外导入。** 只有 IPA 还不能直接游玩。

### 2. 合并资源分卷

将三个分卷和两个 `Resources-…SHA256SUMS.txt` 文件放在同一目录。

macOS：在该目录打开终端，执行：

```sh
shasum -a 256 -c Resources-Parts-SHA256SUMS.txt
cat D2R-Mobile-Resources.zip.001 D2R-Mobile-Resources.zip.002 D2R-Mobile-Resources.zip.003 > D2R-Mobile-Resources.zip
shasum -a 256 -c Resources-SHA256SUMS.txt
```

Linux 可使用 `sha256sum -c` 替代上面的 `shasum -a 256 -c`。

Windows：在分卷所在目录打开**命令提示符（cmd）**，执行：

```bat
copy /b D2R-Mobile-Resources.zip.001+D2R-Mobile-Resources.zip.002+D2R-Mobile-Resources.zip.003 D2R-Mobile-Resources.zip
```

合并后的完整 ZIP 约 5.42GB，解压后得到 `D2R Mobile Resources` 文件夹，里面有 18 个 `.data` 文件，合计 **5,561,224,037 字节（约 5.56GB）**。保留分卷、合并 ZIP 和解压文件时，需要分别为它们留出空间。

### 3. 导入手机

用数据线连接 iPhone，在 **Finder → iPhone → 文件 → D2R Mobile** 中拖入整个 `D2R Mobile Resources` 文件夹；也可以放进手机的 **文件 → 我的 iPhone → D2R Mobile**。

回到应用点击“重试”。首次启动会在手机上编译着色器，等待进度完成，耗时取决于机型。正常覆盖安装且应用标识不变时通常保留资源；卸载应用会删除资源和存档。

**本仓库产物已在 iPhone 17 Pro Max 上通过真机运行验证**，首次着色器编译约 **6 分钟**，其他机型耗时取决于设备。

## 可选：iCloud 存档同步（需要付费开发者账号）

普通构建默认**不配置 iCloud 权限**，继续使用本地存档，免费 Apple ID 仍可按上面的方式签名安装。付费 Apple Developer Program 账号可在 **Build D2R Mobile IPA → Run workflow** 中选择：

| 参数 | 设置 |
| --- | --- |
| `icloud_sync` | 开启；默认 `false` |
| `icloud_bundle_id` | 你的签名团队拥有的明确 App ID，例如 `com.example.d2rmobile`；不接受通配符 |
| `icloud_container_id` | 已分配给该 App ID 的 iCloud 容器；留空时使用 `iCloud.<icloud_bundle_id>` |

同步代码已在固定版本的上游壳中。这一选项生成一份单独的未签名 IPA、iCloud 权限文件和本机签名工具，并不代替 Apple 授权或自动开通账号。构建成功后下载 **`D2RMobile-icloud-<run number>` Actions artifact**（保留 3 天）；该模式不更新普通 Release，两种模式使用相同的游戏资源和生成缓存。App ID 和容器 ID 会写进产物，属于公开构建参数；不要填写凭据。

签名前在 Apple Developer 的 **Certificates, Identifiers & Profiles** 中为这个明确 App ID 开启 iCloud Drive / CloudDocuments、分配容器，并重新生成包含你签名证书及目标设备的 development 或 ad-hoc 描述文件。将证书及私钥安装到 Mac 钥匙串；**无需也不要把 Apple 登录信息、私钥或描述文件上传到 Actions**。[Apple 配置说明](https://developer.apple.com/help/account/identifiers/enable-app-capabilities/)

在安装了 Xcode 的 Mac 上，解压 artifact，在其目录执行：

```sh
shasum -a 256 -c SHA256SUMS.txt
security find-identity -v -p codesigning
python3 icloud.py sign --ipa D2RMobile-icloud-unsigned.ipa \
  --profile /path/to/your.mobileprovision \
  --identity YOUR_CERTIFICATE_SHA1 --output D2RMobile-icloud-signed.ipa
```

工具会核对描述文件的有效期、设备列表、证书、明确 App ID 和三项 iCloud 权限，然后从内到外签名并验证；免费账号或通配符描述文件会被拒绝。按既有方式安装签好的 IPA，再导入游戏资源。其他签名工具可能改掉权限或 App ID，这类路径尚未验证。

两台设备须登录同一 iCloud 账号、打开 iCloud Drive，并使用相同团队、App ID、容器和应用版本。游戏「自定义」页的 iCloud 开关默认开启；启动时下载存档，保存退出一局或切到后台时上传。同步角色和共享仓库，画面与按键设置跟设备走；5.56GB 游戏资源不会同步。同一个角色轮流在两台设备上玩，等上传完成后再启动另一台。

先备份 `Documents/save`。**更换 App ID 会安装成另一个应用**，需要迁移存档和资源；不要先卸载旧应用。CI 仅验证产物和签名配置，`build-report.json` 的 `icloud_sync_verified` 为 `false`；真实上传、另一台下载及冲突处理仍需真机验证。此选项也不会生成旧款 GPU 所需的 ASTC 补充包。

## 固定配套版本

| 项目 | 当前配置 |
| --- | --- |
| 上游 | v1.0.1，提交 `ea86e79688f9339319de3e2c52c69b8b13e30e9e` |
| iOS 壳包 | 上游 v1.0.1 `D2RMobile-shell.ipa` |
| Switch 更新 | `1.0.34.0` / `v2228224` |
| 游戏内部版本 | `3.3.94012` |
| 所需版本 | 《暗黑破坏神 II：狱火重生》含「术士君临」资料片 |
| SPIRV-Cross | `1.4.357.0` |

哈希和工具提交固定在 [build-config.json](build-config.json)。不要混用其他游戏版本或其他上游壳包。导出的 18 个资源档案直接来自合并本体与更新后的 RomFS，打包时不修改内容；文件名和大小按上游清单检查，压缩前后逐文件核对 SHA256。

## 自己运行构建

Fork 后需自行配置输入；Fork 不继承本仓库的 Actions Secrets。请使用自己合法持有并有权使用的游戏输入和主机密钥。上游要求包含「术士君临」资料片，不含资料片的版本不支持、也未验证。

在 **Settings → Secrets and variables → Actions** 配置：

| Secret | 说明 |
| --- | --- |
| `GAME_INPUT_MANIFEST` | 必需，JSON 格式的下载输入清单 |
| `PROD_KEYS` | NSP/XCI 解包时使用的 `prod.keys` 全文；已解密输入无需配置 |

方案 A：已经解密、合并更新后的 ExeFS / RomFS 压缩包：

```json
{
  "kind": "prepared",
  "files": [
    {"name": "game.zip", "url": "https://example.com/your-game.zip", "sha256": "替换为文件的64位SHA256"}
  ]
}
```

压缩包里需要唯一一组 `ExeFS/` 与 `RomFS/`。程序与资源必须对应上表版本。

方案 B：本体与指定更新的 NSP/XCI，同时配置 `PROD_KEYS`：

```json
{
  "kind": "packages",
  "files": [
    {"name": "base.nsp", "url": "https://example.com/your-base.nsp"},
    {"name": "update.nsp", "url": "https://example.com/your-update.nsp"}
  ]
}
```

URL 必须能直接返回文件，验证码页面和网盘展示页不能用于无人值守下载。普通文件的 `sha256` 可省略；填写时必须是实际哈希。支持 zip/rar/7z 包装和 RAR 分卷；NSZ 不支持。DLC 包不参与此脚本的提取。

也支持 `.torrent` 输入：必须提供元数据文件的 `sha256`，并以 `select: [1, 2]` 明确指定要下载的包序号。高级输入可配置带 URL 和 SHA256 的 `key_archive`，该配置也应放入 Secret；归档读取后立即删除，不进入缓存。

### 工作流

| 工作流 | 作用 |
| --- | --- |
| **Build D2R Mobile IPA** | 准备游戏输入，生成并验证 IPA，自动上传 Release |
| **Export D2R Mobile resources** | 从已有原始下载缓存重新解包，导出 18 个资源档案，自动上传资源分卷到 Release |
| **Probe remote game source** | 从 Secret 读取种子输入，短暂测试指定包的连通性，不生成完整游戏文件 |
| **Check PNG encoder compatibility** | 检查尚未过期的 PNG 诊断 artifact，仅用于排错 |

先运行 **Build D2R Mobile IPA**，再运行 **Export D2R Mobile resources**。资源导出工作流要求原始下载和解包工具缓存存在，缓存缺失时停止，不会自行重新下载游戏。

构建参数：

- `prepare_only=false`：完整构建 IPA。
- `prepare_only=true`：只验证工具链和预热缓存，不生成 IPA、不发布 Release。
- `input_revision`：两个工作流使用相同值；更换输入文件时修改它，区分缓存和 Release。

构建通过 Actions 的 **Run workflow** 启动；**普通模式的 Release 发布是成功构建后的自动步骤，不需要另外运行发布任务或填写标签**。iCloud 模式只上传独立 Actions artifact。

## 自动发布与产物

Release 标签由游戏版本、上游提交和 `input_revision` 自动生成。同一配套版本的两个工作流更新同一个 Release；首次只有一种产物时暂存草稿，IPA、三个资源分卷及配套文件齐全后自动发布。后续同版本构建更新相应附件，版本或输入修订号变化时创建另一份 Release。

GitHub 每个 Release 附件必须小于 2GiB，因此资源 ZIP 按每卷最多 1,900,000,000 字节拆分。上传前检查本地产物 SHA256，上传后检查附件大小及 GitHub 返回的 SHA256。

Actions artifact 保留 **3 天**：IPA artifact 内有 IPA 和构建报告，资源 artifact 内是**完整资源 ZIP**和报告，不需要合并分卷。Release 附件不受 Actions artifact 的保留期影响。

## 公开仓库与输入可见性

这个仓库已公开，**Release、Actions 日志和构建产物可被其他人访问**；下载 Actions artifact 需要登录 GitHub 并有仓库读取权限。[GitHub 说明](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/download-workflow-artifacts)

Actions Secrets 的值不会因为仓库公开而展示给访客，Fork 的 PR 工作流默认也拿不到原仓库 Secrets。不要把实际下载凭据、密钥内容写进 README、提交、日志或 artifact。[GitHub Secrets 说明](https://docs.github.com/en/code-security/reference/secret-security/secret-types)

**Actions 缓存不能视为私有文件存储。** GitHub 明确说明，能向仓库发起 PR 的人可能读取基础分支的缓存；本项目的缓存包含原始游戏包和生成内容，不包含主机密钥或输入 Secret 原文。若输入文件需要保密，应在独立私有仓库或受控存储中构建，不使用此公开仓库的缓存。[GitHub 缓存说明](https://docs.github.com/en/actions/reference/workflows-and-actions/dependency-caching)

当前工作流只通过手动构建入口运行，没有给外部 PR 执行带 Secrets 或写入 Release 的构建步骤。

## 缓存与校验

- **工具缓存**：SPIRV-Cross、hactool 和上游壳包。
- **原始下载缓存**：完整游戏输入和大小 / SHA256 清单，下载成功后立即保存，再读取密钥并解包。后续解包或编译失败仍可复用。
- **生成缓存**：改写后的游戏程序、着色器转换工具与结果、界面素材。
- **PNG 压缩后端和 Python 依赖缓存**：固定版本，避免生成内容变化。

原始下载缓存独立于密钥与解包脚本；修改解包流程或更换密钥不会使其失效。生成缓存按工具、配置和输入修订号区分。密钥仅写入临时目录，提取结束后删除，不进入缓存或附件。

GitHub 缓存有容量和淘汰机制，不是永久备份。云端解包前会清理临时 runner 上无关的预装 SDK，并检查至少 28GiB 空闲空间；不修改本地电脑。

公开上游源码缺少录制的启动预取表 `bootlist.tsv`。官方 v1.0.1 壳不要求该文件，改写步骤会清理构建产物中的预取文件残留。本流程逐字节复制已校验的官方壳；若清单要求预取文件，或最终 IPA 残留旧预取文件，则停止构建。构建报告记录 `startup_prefetch: false` 和壳的着色器链标识，未启用这项启动加速优化。
