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
