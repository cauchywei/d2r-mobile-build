# D2R Mobile · GitHub Actions Build Template

**English** | [简体中文](README.zh-CN.md)

Build an unsigned IPA and matching Data resources in your own private GitHub repository, using the **NO_XCODE** approach from [jhaizhou-ops/d2r-mobile](https://github.com/jhaizhou-ops/d2r-mobile).

The build downloads the base game and update through the torrent configured below, reads extraction keys from a ZIP archive, builds the IPA, and exports 18 `.data` files. Use this configuration only if you are authorized to use the game files and keys.

## 1. Create a private repository

Click **Use this template → Create a new repository**, choose your account and a repository name, select **Private**, and create the repository. The default branch is sufficient; leave **Include all branches** unchecked. Template creation requires the source repository's Template setting to be enabled.

Continue in **your new repository**. Open **Actions** and enable workflows if prompted. Your new repository does not inherit Secrets, Releases, artifacts, or caches. Private builds use your account's Actions allowance or billing settings.

## 2. Add one Secret

Open **Settings → Secrets and variables → Actions → New repository secret**. Name it **`GAME_INPUT_MANIFEST`** and paste the complete JSON below. The download URLs and SHA256 values are already filled in; no replacements are needed:

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

The torrent is downloaded from GameGula; the key ZIP is downloaded from Google Drive. Both URLs have been checked by downloading the files and matching their pinned SHA256 values. The ZIP contains one `prod.keys` file.

The torrent's **file 1 must be the base NSP, and file 2 the `1.0.34.0` (`v2228224`) update NSP**, matching `select: [1, 2]`. Only those two entries are downloaded. The resulting internal game version must be **`3.3.94012`**. Upstream requires the Reign of the Warlock expansion.

Keep this configuration in the Secret. Do not commit game files or keys. The key ZIP is read temporarily and deleted; it is not cached or uploaded as an output.

## 3. Run the two workflows

1. Open **Actions → Build D2R Mobile IPA → Run workflow**, select `main`, leave **`prepare_only` unchecked**, and keep **`input_revision=game-3.3.94012-v1`**.
2. Wait for success. Then run **Export D2R Mobile resources** on `main`, with the **same `input_revision`**.
3. After both succeed, open **Releases in your own repository** to download the IPA and Data resources. Publishing is automatic; no tag or personal access token is needed.

The IPA workflow saves complete downloads before extraction. If extraction fails, fix the key input or extraction problem and rerun with the same revision to reuse downloads. If you change the torrent entry or game files, change `input_revision` in both workflows. Resource export requires the original download and tool caches; if either is missing, rerun the full IPA workflow first.

## Matching versions

| Component | Version |
| --- | --- |
| Upstream source and shell | v1.0.1 |
| Switch update | `1.0.34.0` / `v2228224` |
| Internal game version | `3.3.94012` |

Source, shell, and tool versions are pinned in [build-config.json](build-config.json) and the workflows. They are downloaded automatically; no edits are needed for the build described here.

## Install your build

In **your own repository**, open **Releases** after both workflows succeed and download these files from Assets:

| Asset | Purpose |
| --- | --- |
| `D2RMobile-unsigned.ipa` | About 126 MB; sign and install with Sideloadly |
| `D2R-Mobile-Resources.zip.001`, `.002`, `.003` | Three parts of the resource ZIP; download all three, totaling about 5.42 GB |
| `Resources-Parts-SHA256SUMS.txt` | Verify the three ZIP parts |
| `Resources-SHA256SUMS.txt` | Verify the combined ZIP |
| `RESOURCE-INSTALL.txt` | Instructions for combining the parts and importing resources |
| `build-report.json`, `resources-report.json`, `SHA256SUMS.txt` | Version information, file sizes, and SHA256 checksums |

The `Source code` archives that GitHub adds automatically contain the build scripts.

### 1. Install the IPA

Your phone needs **iOS 26 or later**. Sign and install the IPA with Sideloadly, then complete the trust setup prompted by iOS.

**The IPA contains the game program, converted shaders, and other generated content. Large resources such as maps, models, and audio must be imported separately.** Installing only the IPA is not enough to play.

### 2. Combine the resource parts

Place all three parts and both `Resources-…SHA256SUMS.txt` files in the same directory.

On macOS, open a terminal in that directory and run:

```sh
shasum -a 256 -c Resources-Parts-SHA256SUMS.txt
cat D2R-Mobile-Resources.zip.001 D2R-Mobile-Resources.zip.002 D2R-Mobile-Resources.zip.003 > D2R-Mobile-Resources.zip
shasum -a 256 -c Resources-SHA256SUMS.txt
```

On Linux, use `sha256sum -c` in place of `shasum -a 256 -c` above.

On Windows, open **Command Prompt (cmd)** in the directory containing the parts and run:

```bat
copy /b D2R-Mobile-Resources.zip.001+D2R-Mobile-Resources.zip.002+D2R-Mobile-Resources.zip.003 D2R-Mobile-Resources.zip
```

The combined ZIP is about 5.42 GB. Extract it to get a `D2R Mobile Resources` folder containing 18 `.data` files, totaling **5,561,224,037 bytes (about 5.56 GB)**. If you keep the parts, the combined ZIP, and the extracted files, allow disk space for each copy.

### 3. Import resources to your phone

Connect your iPhone by cable. In **Finder → iPhone → Files → D2R Mobile**, drag in the entire `D2R Mobile Resources` folder. Alternatively, place the folder in **Files → On My iPhone → D2R Mobile** on the phone.

Return to the app and tap **Retry**. On the first launch, the phone compiles shaders; wait for it to finish. The time required depends on the device. Installing over an existing installation with the same app identifier usually preserves resources. Uninstalling the app deletes its resources and saves.

**Tested on iPhone 17 Pro Max.** Initial shader compilation takes about **6 minutes** on this device. Compilation time varies by device.

## Outputs and storage

Both workflows update the same Release for matching versions and `input_revision`. It remains a draft until the IPA, all three resource parts, and accompanying files are present. Private repository Releases require repository access. Each resource part is at most 1,900,000,000 bytes.

Actions artifacts are retained for **3 days**. The resource artifact contains the **complete resource ZIP**, so it does not require part combining. Releases are independent of artifact retention. Raw downloads and generated content are cached for reuse; caches have capacity and eviction limits and are not permanent backups. Keys are not included in caches or outputs.

Keep your build repository private and use only inputs you are authorized to process. Private builds do not grant rights to game content; do not redistribute outputs without permission. Enabling template mode does not remove this public repository's existing Release assets or caches.
