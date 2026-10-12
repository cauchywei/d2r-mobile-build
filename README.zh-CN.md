# D2R Mobile · GitHub Actions 构建模板

[English](README.md) | **简体中文**

基于 [jhaizhou-ops/d2r-mobile](https://github.com/jhaizhou-ops/d2r-mobile) 的 **NO_XCODE** 方案，在自己的 GitHub 私有仓库中构建未签名 IPA 和配套 Data 资源。

流程使用下方配置中的 BT 种子下载本体与更新，从 ZIP 归档读取解包密钥，生成 IPA 并导出 18 个 `.data` 文件。使用前请确保有权使用这些游戏文件与密钥。

## 1. 创建私有仓库

点击 **Use this template → Create a new repository**，填写自己的账号和仓库名，选择 **Private**，创建仓库。默认分支即可，无需勾选 **Include all branches**。创建模板仓库需要来源仓库已启用 Template 设置。

后续操作均在**自己的新仓库**中进行。打开 **Actions**，如有启用提示，按提示启用。新仓库不继承 Secrets、Release、构建附件或缓存。私有构建会使用自己账号的 Actions 额度或计费设置。

## 2. 配置一个 Secret

进入 **Settings → Secrets and variables → Actions → New repository secret**，名称填写 **`GAME_INPUT_MANIFEST`**，完整粘贴以下 JSON。下载地址与 SHA256 已填好，无需替换：

```json
{
  "kind": "packages",
  "files": [
    {
      "name": "game.torrent",
      "url": "https://gamegula.com/index.php?do=download&id=405",
      "sha256": "016f7c907deb1f4cd6098a7cd06823907a589ff2502aa2c8b341a89ccf984266",
      "select": [
        1,
        2
      ]
    }
  ],
  "key_archive": {
    "url": "https://drive.google.com/uc?export=download&id=147IsDRRJNF_VMT6Fj50glrnqAeb7oR_1",
    "sha256": "b73573af5eae6c9f7739ca9931cebf04774cf2ba9d6ee98f2f04c2dc88fca71c"
  }
}
```

种子从 GameGula 下载，密钥 ZIP 从 Google Drive 下载。两个地址均已实际下载并核对固定 SHA256，ZIP 内包含一个 `prod.keys` 文件。

种子内**第 1 项必须是本体 NSP，第 2 项是 `1.0.34.0`（`v2228224`）更新 NSP**，对应 `select: [1, 2]`，只下载这两项。合并后游戏内部版本需为 **`3.3.94012`**。上游要求包含「术士君临」资料片。

将这份配置保存在 Secret 中，不要把游戏文件或密钥提交到 Git。密钥 ZIP 临时读取后删除，不进入缓存或产物。

## 3. 依次运行两个工作流

1. 进入 **Actions → Build D2R Mobile IPA → Run workflow**，选择 `main`，**不勾选 `prepare_only`**，保留 **`input_revision=game-3.3.94012-v1`**。
2. 等待成功后，运行 **Export D2R Mobile resources**，选择 `main`，使用**相同的 `input_revision`**。
3. 两个工作流成功后，在**自己仓库的 Releases** 下载 IPA 和 Data 资源。发布自动完成，无需填写标签或配置个人访问令牌。

IPA 工作流会先缓存完整下载，再解包。解包失败时修正密钥输入或解包问题，保留修订号重跑即可复用下载。修改种子下载项或更换游戏文件时，两个工作流都更换 `input_revision`。资源导出需要原始下载和工具缓存，缺失时先重新运行完整 IPA 构建。

## 配套版本

| 项目 | 版本 |
| --- | --- |
| 上游源码与壳包 | v1.0.1 |
| Switch 更新 | `1.0.34.0` / `v2228224` |
| 游戏内部版本 | `3.3.94012` |

源码、壳包和工具版本固定在 [build-config.json](build-config.json) 与工作流中，会自动下载，按本教程构建无需修改。

## 安装自己的构建产物

两个工作流成功后，进入**你自己仓库的 Releases**，在 Assets 中下载：

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

## 产物与存储

配套版本和 `input_revision` 相同的两个工作流更新同一份 Release。IPA、三个资源分卷和配套文件齐全后自动发布，此前保持草稿。私有仓库的 Release 需要仓库访问权限。每个资源分卷最多 1,900,000,000 字节。

Actions 附件保留 **3 天**。资源附件内是**完整资源 ZIP**，无需合并分卷；Release 不受附件保留期影响。原始下载和生成内容会缓存复用，缓存有容量与淘汰限制，不是永久备份。密钥不进入缓存或产物。

构建仓库请保持私有，仅处理自己有权使用的输入。私有构建不授予游戏内容的使用权，未经授权不要分发产物。启用模板也不会移除本公开仓库已有的 Release 附件或缓存。
