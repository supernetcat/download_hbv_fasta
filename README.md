# HBV FASTA 批量下载工具

从 NCBI Nucleotide 数据库按指定搜索条件，**一键批量下载 FASTA 序列**的命令行工具。
默认搜索条件对应肝细胞癌 / 乙肝研究中常用的 HBV 全基因组标准：

```
"Hepatitis B virus"[Organism] AND (viruses[filter] AND biomol_genomic[PROP]
AND is_nuccore[filter] AND ("3000"[SLEN] : "3400"[SLEN]))
```

- 纯 Python 标准库实现，**无需安装任何第三方依赖**
- 自动分页检索（esearch）+ 分批抓取（efetch），带重试、限速、断点进度
- 支持自定义搜索式、输出文件、下载条数上限、NCBI API key
- 已打包多平台独立二进制（Linux x64/arm64、Windows x64、macOS x64/arm64），免安装 Python

---

## 目录结构

```
hbv_fasta_download/
├── download_hbv_fasta.py      # 源码（Python 3.8+）
├── build.sh                   # 一键打包脚本
├── .github/workflows/build.yml # CI：多平台编译并发布 Release
├── .gitignore
├── README.md
└── releases/                  # 本机编译的二进制（Linux x64）
    └── linux-x64/
        └── download_hbv_fasta # 免 Python 环境
```

---

## 快速开始（免安装）

在 [GitHub Releases](https://github.com/supernetcat/download_hbv_fasta/releases) 下载
对应平台的二进制（当前 v1.0.1，无需 Python 环境）：

| 平台 | 资产名 |
|------|--------|
| Linux x86_64 | `download_hbv_fasta-linux-x64` |
| Linux arm64 | `download_hbv_fasta-linux-arm64` |
| Windows x86_64 | `download_hbv_fasta-windows-x64.exe` |
| macOS (Intel) | `download_hbv_fasta-macos-x64` |
| macOS (Apple Silicon) | `download_hbv_fasta-macos-arm64` |

**Linux / macOS**：

```bash
# 1. 赋予执行权限（Windows 跳过）
chmod +x download_hbv_fasta

# 2. 试运行：只下载前 10 条，确认网络与功能正常
./download_hbv_fasta -n 10 -o sample.fasta

# 3. 全量下载（当前检索约 1.7 万条，耗时约 5–15 分钟，视网络而定）
./download_hbv_fasta
# 输出文件默认: hbv_genomic.fasta
```

**Windows**（PowerShell）：运行 `download_hbv_fasta-windows-x64.exe -n 10 -o sample.fasta`

想从源码运行（需 Python 3.8+，无需 pyinstaller）：
```bash
python3 download_hbv_fasta.py
```

---

## 命令行参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `-q, --query` | NCBI 搜索式（支持所有 Entrez 语法） | HBV 3000–3400 bp 基因组 |
| `-o, --output` | 输出 FASTA 文件路径 | `hbv_genomic.fasta` |
| `-n, --limit` | 最多下载多少条（`0` = 全部） | `0` |
| `--api` | NCBI API key（见下节） | 自动读环境变量 |
| `-h, --help` | 显示帮助 | — |

示例：

```bash
# 下载前 100 条
download_hbv_fasta -n 100 -o sample.fasta

# 只下载特定血清型
download_hbv_fasta -q "\"Hepatitis B virus\"[Organism] AND gene[PROP] AND 3000[SLEN]:3400[SLEN] AND genotype_C"

# 换个物种试试
download_hbv_fasta -q "\"Hepatitis D virus\"[Organism]" -n 5
```

---

## NCBI API key（强烈推荐）

不传 API key 时 NCBI 限制约 **3 次请求/秒**；提供 key 后提升到 **10 次请求/秒**，
全量下载速度快 3 倍以上且更稳定，不会触发 429 限流。

### 获取 key（免费）
1. 注册/登录 [NCBI 账户](https://www.ncbi.nlm.nih.gov/account/settings/)
2. 进入 **API key** 一栏 → **Generate** → 复制生成的 20 位字符串

### 三种传法

```bash
# ① 命令行直接传
download_hbv_fasta --api ABCDEF1234567890ABC

# ② 从文件读取（取第一个非空非注释行，适合放进配置文件）
echo "ABCDEF1234567890ABC" > ncbi_key.txt
download_hbv_fasta --api @ncbi_key.txt

# ③ 环境变量（脚本优先读 NCBI_API_KEY，其次 NCBI_APIKEY）
export NCBI_API_KEY=ABCDEF1234567890ABC
download_hbv_fasta
```

脚本打印时**只显示前 3 位**（如 `ABC***`），不会在日志中泄露完整 key。

---

## 工作原理

```
┌────────────┐   分页(每页≤10000)   ┌────────────┐
│  esearch   │ ──────────────────▶ │  id 列表    │
│  检索      │                     │  (gi/accession)
└────────────┘                     └─────┬──────┘
        ▲                                ▼
        │                     ┌─────────────────────┐
        │   每批 500 条        │     efetch          │
        └──────────────────── │  拉取 FASTA 文本     │
                              └──────────┬──────────┘
                                         ▼
                              ┌─────────────────────┐
                              │  追加写入 .fasta 文件 │
                              └─────────────────────┘
```

- **重试策略**：请求失败时指数退避重试（5 次，1→2→4→8→16 秒），网络抖动不会中断任务
- **限速**：每次请求间隔 0.5 s，符合 NCBI 使用规范
- **增量写入**：每批下载后 `flush`，中途中断已完成部分仍在文件中

---

## 常见问题

**Q: 运行后卡在 `正在执行 esearch ...`？**
A: 网络问题或被限流。查看 `[警告]` 提示；若持续 403/429，请配置 `--api` 或稍后重试。

**Q: 想要某个特定字段（如只取基因组 CDS）？**
A: 用 `-q` 覆盖搜索式，Entrez 语法见 [NCBI Entrez 帮助](https://www.ncbi.nlm.nih.gov/help/glossary/?term=Entrez)

**Q: 下载的文件可以用什么工具打开？**
A: 标准 FASTA，可用 SnapGene、Sequencher、MEGA、AliView、ViralSeq 等，或直接 `head -5 hbv_genomic.fasta` 预览。

**Q: 能改搜索条件中的长度范围吗？**
A: 改 `-q` 参数即可，例如把 `"3000"[SLEN] : "3400"[SLEN]` 换成 `"3100"[SLEN] : "3600"[SLEN]`

---

## 自行编译二进制

仓库已配置 GitHub Actions workflow（`.github/workflows/build.yml`）：打 `v*` tag
或手动触发即自动在 Linux/Windows/macOS runner 上编译全部平台二进制并发布到 Release。

本地自行编译：

```bash
pip install pyinstaller
./build.sh
# 产物在 dist/download_hbv_fasta（仅当前平台）
```

或直接运行源码（无需 pyinstaller）：

```bash
python3 download_hbv_fasta.py
```

---

## 版本

当前：**v1.0.1**（2026-09-05）

| 版本 | 日期 | 变更 |
|------|------|------|
| 1.0.1 | 2026-09-05 | 修复大批量下载 (>250 条) 时 efetch URL 过长导致 HTTP 414；自动改用 POST。后补发布 Windows/macOS/Linux-arm64 官方二进制（GitHub Actions 编译） |
| 1.0.0 | 2026-09-04 | 首个公开版本；默认 HBV 搜索式；`-q/-o/-n/--api` 参数 |

---

## License

MIT
