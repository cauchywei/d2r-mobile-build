# D2R Mobile · GitHub Actions Builds and Automatic Releases

**English** | [简体中文](README.zh-CN.md)

[![Build IPA](https://github.com/jiayx/d2r-mobile-build/actions/workflows/pack.yml/badge.svg)](https://github.com/jiayx/d2r-mobile-build/actions/workflows/pack.yml)
[![Export resources](https://github.com/jiayx/d2r-mobile-build/actions/workflows/resources.yml/badge.svg)](https://github.com/jiayx/d2r-mobile-build/actions/workflows/resources.yml)

Build an unsigned IPA, export matching game resources, and publish them automatically to GitHub Releases using the **NO_XCODE** approach from [jhaizhou-ops/d2r-mobile](https://github.com/jhaizhou-ops/d2r-mobile). Builds run on Ubuntu runners in GitHub Actions.

This repository contains build scripts and pinned version settings. IPA and resource files are stored as Release assets and Actions artifacts. Console keys and download inputs are configured through Actions Secrets and are not committed to Git.

## Download and install

Open the **[latest Release](https://github.com/jiayx/d2r-mobile-build/releases/latest)** and download these files from Assets:

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

## Optional iCloud save sync (paid developer account required)

The default build does not provision iCloud. It keeps local saves and remains compatible with free Apple ID signing. For a paid Apple Developer Program account, select these inputs in **Build D2R Mobile IPA → Run workflow**:

| Input | Setting |
| --- | --- |
| `icloud_sync` | Enable; defaults to `false` |
| `icloud_bundle_id` | An explicit App ID owned by your signing team, such as `com.example.d2rmobile`; no wildcard |
| `icloud_container_id` | The container assigned to that App ID; blank uses `iCloud.<icloud_bundle_id>` |

The pinned upstream shell already contains the sync code. This option prepares a separate unsigned IPA, an entitlement file and a local signing tool; it does not grant Apple capabilities or enroll an account. Download the **`D2RMobile-icloud-<run number>` Actions artifact** after the build (retained for 3 days). This mode does not update the standard Release; both modes reuse the same game resources and generated caches. IDs are public build parameters recorded in the artifact, so never enter credentials there.

In Apple Developer **Certificates, Identifiers & Profiles**, enable iCloud Drive / CloudDocuments for that explicit App ID, assign its container, and regenerate a development or ad-hoc profile containing your signing certificate and target devices. Install the certificate and private key in your Mac's Keychain. **Do not upload Apple credentials, private keys or profiles to Actions.** [Apple setup instructions](https://developer.apple.com/help/account/identifiers/enable-app-capabilities/)

On a Mac with Xcode, extract the artifact and run from its directory:

```sh
shasum -a 256 -c SHA256SUMS.txt
security find-identity -v -p codesigning
python3 icloud.py sign --ipa D2RMobile-icloud-unsigned.ipa \
  --profile /path/to/your.mobileprovision \
  --identity YOUR_CERTIFICATE_SHA1 --output D2RMobile-icloud-signed.ipa
```

The tool checks profile expiration, devices, certificate, explicit App ID and all three iCloud permissions before signing nested code and the app, then verifies the signature. Free-account and wildcard profiles are rejected. Install the signed IPA and import game resources as usual. Other signing tools may strip permissions or change the App ID; those paths have not been verified.

Use the same iCloud account with iCloud Drive enabled, signing team, App ID, container and app version on both devices. The in-game Custom → iCloud setting defaults to on. Saves download at startup and upload when leaving a game or entering the background. Characters and shared stash sync; display/control settings stay per device and the 5.56 GB game resources do not sync. Play a character on one device at a time and allow upload to finish before opening it on the other.

Back up `Documents/save` first. **Changing App ID installs a separate app**: migrate saves and resources, rather than uninstalling the old app first. CI verifies packaging and signing configuration; `icloud_sync_verified` remains `false` in the report. Upload, download and conflicts still need device validation. This option does not generate the ASTC supplement needed by older GPUs.

## Pinned versions

| Component | Current setting |
| --- | --- |
| Upstream | v1.0.1, commit `ea86e79688f9339319de3e2c52c69b8b13e30e9e` |
| iOS shell | Upstream v1.0.1 `D2RMobile-shell.ipa` |
| Switch update | `1.0.34.0` / `v2228224` |
| Internal game version | `3.3.94012` |
| Required edition | Diablo II: Resurrected with Reign of the Warlock |
| SPIRV-Cross | `1.4.357.0` |

Hashes and tool commits are pinned in [build-config.json](build-config.json). Do not mix other game versions or upstream shell packages. The 18 exported resource archives come directly from the RomFS after merging the base game and update; packaging does not modify their contents. File names and sizes are checked against the upstream list, and each file's SHA256 is verified before and after ZIP compression.

## Run your own build

Configure your own inputs after forking; forks do not inherit this repository's Actions Secrets. Use game inputs and console keys that you legally possess and are authorized to use. Upstream requires the Reign of the Warlock expansion; the edition without it is not supported or verified.

Configure these secrets under **Settings → Secrets and variables → Actions**:

| Secret | Description |
| --- | --- |
| `GAME_INPUT_MANIFEST` | Required: a JSON manifest describing download inputs |
| `PROD_KEYS` | Full contents of `prod.keys` for NSP/XCI extraction; not needed for already decrypted inputs |

Option A: an archive containing decrypted ExeFS / RomFS with the update already merged:

```json
{
  "kind": "prepared",
  "files": [
    {"name": "game.zip", "url": "https://example.com/your-game.zip", "sha256": "REPLACE_WITH_THE_FILES_64_HEX_CHARACTER_SHA256"}
  ]
}
```

The archive must contain exactly one pair of `ExeFS/` and `RomFS/` directories. The program and resources must match the versions in the table above.

Option B: NSP/XCI packages for the base game and specified update, with `PROD_KEYS` also configured:

```json
{
  "kind": "packages",
  "files": [
    {"name": "base.nsp", "url": "https://example.com/your-base.nsp"},
    {"name": "update.nsp", "url": "https://example.com/your-update.nsp"}
  ]
}
```

URLs must return files directly. CAPTCHA pages and file-hosting landing pages cannot be used for unattended downloads. The `sha256` field is optional for ordinary files; when provided, it must contain the actual hash. ZIP/RAR/7z wrappers and multipart RAR archives are supported. NSZ is not supported. DLC packages are not extracted by this script.

`.torrent` inputs are also supported: provide the metadata file's `sha256` and explicitly select package indices with `select: [1, 2]`. Advanced inputs may include a `key_archive` with a URL and SHA256; keep that configuration in the Secret as well. The key archive is deleted immediately after reading and is not cached.

### Workflows

| Workflow | Purpose |
| --- | --- |
| **Build D2R Mobile IPA** | Prepare game inputs, generate and validate an IPA, and automatically upload it to the Release |
| **Export D2R Mobile resources** | Extract again from the existing raw download cache, export 18 resource archives, and automatically upload resource parts to the Release |
| **Probe remote game source** | Read torrent inputs from the Secret and briefly test connectivity for a selected package; does not produce complete game files |
| **Check PNG encoder compatibility** | Inspect an unexpired PNG diagnostic artifact for troubleshooting |

Run **Build D2R Mobile IPA** first, then **Export D2R Mobile resources**. Resource export requires the raw download and extraction tool caches to exist. If a required cache is missing, it stops rather than downloading the game again.

Build inputs:

- `prepare_only=false`: build the complete IPA.
- `prepare_only=true`: validate the toolchain and warm caches only; no IPA or Release is produced.
- `input_revision`: use the same value in both workflows. Change it when replacing input files to distinguish caches and Releases.

Start builds with **Run workflow** in Actions. **Standard-mode Release publishing happens automatically after successful builds; no separate publishing task or manually entered tag is needed.** The optional iCloud mode uploads an independent Actions artifact instead.

## Automatic releases and outputs

Release tags are generated from the game version, upstream commit, and `input_revision`. Both workflows update the same Release for matching versions. When only one type of output is available initially, the Release remains a draft. It is published automatically once the IPA, all three resource parts, and accompanying files are present. Later builds of the same version update the corresponding assets; changing the version or input revision creates a separate Release.

Each GitHub Release asset must be smaller than 2 GiB, so the resource ZIP is split into parts of at most 1,900,000,000 bytes. Local SHA256 checks run before upload; asset sizes and the SHA256 returned by GitHub are checked afterward.

Actions artifacts are retained for **3 days**. The IPA artifact contains the IPA and build report. The resource artifact contains the **complete resource ZIP** and report, so no part combining is required. Release assets are independent of the Actions artifact retention period.

## Public repository and input visibility

This repository is public. **Other people can access Releases, Actions logs, and build outputs.** Downloading Actions artifacts requires a GitHub login and read access to the repository. [GitHub documentation](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/download-workflow-artifacts)

Making the repository public does not expose Actions Secret values to visitors. Pull request workflows from forks also do not receive the original repository's Secrets by default. Do not put actual download credentials or key contents in the README, commits, logs, or artifacts. [GitHub Secrets documentation](https://docs.github.com/en/code-security/reference/secret-security/secret-types)

**Actions caches are not private file storage.** GitHub states that people who can open pull requests may be able to read caches from the base branch. This project's caches include raw game packages and generated content, but not console keys or the original input Secret text. If input files must remain private, build in a separate private repository or controlled storage environment instead of using this public repository's caches. [GitHub caching documentation](https://docs.github.com/en/actions/reference/workflows-and-actions/dependency-caching)

The current workflows are started manually. They do not run build steps with Secrets or Release write access for external pull requests.

## Caching and validation

- **Tool cache:** SPIRV-Cross, hactool, and the upstream shell package.
- **Raw download cache:** complete game inputs and a size / SHA256 manifest. It is saved immediately after successful downloads, before reading keys and extracting files, so later extraction or compilation failures do not require another download.
- **Generated cache:** the rewritten game program, shader conversion tools and results, and UI assets.
- **PNG compression backend and Python dependency caches:** pinned versions to keep generated content consistent.

The raw download cache is independent of keys and extraction scripts. Changing the extraction process or replacing keys does not invalidate it. Generated caches are distinguished by tools, configuration, and input revision. Keys are written only to a temporary directory and deleted after extraction; they are not included in caches or assets.

GitHub caches have storage limits and eviction rules; they are not permanent backups. Before cloud extraction, the workflow removes unrelated preinstalled SDKs from the temporary runner and checks for at least 28 GiB of free space. It does not modify your local computer.

The public upstream source does not include the recorded startup prefetch table `bootlist.tsv`. The official v1.0.1 shell does not require it. The rewriting step removes stale prefetch files from build outputs. This workflow copies the verified shell byte for byte and rejects an unexpected prefetch requirement or stale prefetch files in the final IPA. Build reports record `startup_prefetch: false` and the shell's shader chain identifier; this startup optimization is not enabled.
