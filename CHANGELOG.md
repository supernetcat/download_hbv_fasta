# v1.0.1 (2026-09-05)

## 修复
- 修复下载超过约 250 条序列时 NCBI 代理返回 `HTTP 414 (Request-URI Too Long)`
  的问题：id 过多导致 efetch GET 请求的 URL 过长，现改为当 URL 超过
  `MAX_URL_LEN`(3000) 时自动改用 POST（参数放入请求体），单批 500/1000 条均可正常下载
- 修复重构 http 请求函数时丢失 GET 参数拼接、导致 esearch 收到空请求的问题
- 验证：`-n 100`(GET) / `-n 500`(POST) / `-n 501`(GET+POST) / `-n 600` / `-n 1000`
  均成功且 FASTA 记录数正确

## 补充（2026-09-05）
- 新增 GitHub Actions 工作流 `.github/workflows/build.yml`：打 `v*` tag 或手动触发时，
  在 Linux (x64/arm64)、Windows (x64)、macOS (Intel/Apple Silicon) 上分别编译并发布
  PyInstaller one-file 二进制到对应 tag 的 Release（`overwrite: true` 可补发既有版本资产）
- 为 v1.0.1 Release 补发 `linux-arm64` / `windows-x64.exe` / `macos-x64` /
  `macos-arm64` 官方二进制
- 修复 Windows 控制台/管道默认非 UTF-8 编码导致打印中文（帮助/进度）时抛
  `UnicodeEncodeError` 的问题：启动时强制 stdout/stderr 使用 UTF-8 输出

# v1.0.0 (2026-09-04)

首个公开版本。

## 新增
- 默认搜索式: HBV 3000–3400 bp 基因组 (viruses + biomol_genomic + is_nuccore)
- `-q/--query` 自定义搜索式
- `-o/--output` 输出文件
- `-n/--limit` 下载条数上限
- `--api` NCBI API key (直传 / @文件 / env:VAR, 自动读 NCBI_API_KEY)
- 分页 esearch + 分批 efetch + 指数退避重试 + 限速
- 独立二进制 (Linux x86_64, PyInstaller one-file)

## 已知限制
- 未提供 Windows / macOS 预编译二进制 (源码可在任意平台运行)
- 结果集 > 10 万条未验证 (当前搜索式约 1.7 万条)
