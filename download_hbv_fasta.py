#!/usr/bin/env python3
"""
从 NCBI Nucleotide 数据库按指定搜索条件批量下载 FASTA 序列。

搜索条件（对应网页端）：
"Hepatitis B virus"[Organism] AND (viruses[filter] AND biomol_genomic[PROP]
AND is_nuccore[filter] AND ("3000"[SLEN] : "3400"[SLEN]))

仅使用 Python 标准库，无需安装第三方包。
用法：
    python3 download_hbv_fasta.py                  # 使用默认参数
    python3 download_hbv_fasta.py -o my.fasta      # 指定输出文件
    python3 download_hbv_fasta.py -q "自定义搜索式"  # 自定义搜索式
    python3 download_hbv_fasta.py --api ABCDEF123456  # 使用 NCBI API key
    python3 download_hbv_fasta.py --api @ncbi_cfg   # 从指定文件读取 key

--api 参数支持三种形式：
  1. 直接传 key 字符串
  2. @文件名：从文件中读取第一行非空内容作为 key
  3. 不传时，自动读取环境变量 NCBI_API_KEY / NCBI_APIKEY
"""

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

ESearch_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
EFetch_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"

DEFAULT_QUERY = (
    '"Hepatitis B virus"[Organism] AND (viruses[filter] '
    'AND biomol_genomic[PROP] AND is_nuccore[filter] '
    'AND ("3000"[SLEN] : "3400"[SLEN]))'
)

PAGE_SIZE = 10000         # esearch 每次最多返回 10000 个 id
BATCH_SIZE = 500          # 每次 efetch 请求取多少条 FASTA
REQUEST_SLEEP = 0.5       # 每次请求间隔秒数（NCBI 建议 <3 req/s）
DEFAULT_RETRY_BASE = 2.0  # 重试退避基数
MAX_RETRIES = 5
MAX_URL_LEN = 3000        # URL（含查询串）超过此长度时改用 POST，避免 414

USER_AGENT = "hbv-fasta-downloader/1.0.1 (Python urllib)"

API_KEY = None  # 在 main() 中初始化


def load_api_key(value: str) -> str:
    """解析 --api 参数：支持 key 字符串、@文件名、env:NCBI_API_KEY 等。"""
    if not value or value == "none":
        return os.environ.get("NCBI_API_KEY", "") or os.environ.get("NCBI_APIKEY", "")
    if value.startswith("@"):
        with open(value[1:], "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    return line
        raise FileNotFoundError(f"API 文件 {value[1:]} 中没有找到 key")
    if value.lower().startswith("env:"):
        return os.environ.get(value[4:], "")
    return value


def http_request(url: str, params: dict, use_post: bool = False) -> str:
    """对 NCBI eutils 发请求。

    - use_post=False: 标准 GET，参数拼在 URL 上
    - use_post=True:  参数放请求体（Content-Type: application/x-www-form-urlencoded）

    带指数退避重试（最多 MAX_RETRIES 次）；4xx（除 429）不重试。
    """
    if API_KEY:
        params = dict(params, api_key=API_KEY)
    last_err: Exception | None = None
    if use_post:
        target = url
        body = urllib.parse.urlencode(params).encode("utf-8")
        headers = {
            "User-Agent": USER_AGENT,
            "Content-Type": "application/x-www-form-urlencoded",
        }
    else:
        target = f"{url}?{urllib.parse.urlencode(params)}"
        body = None
        headers = {"User-Agent": USER_AGENT}
    for attempt in range(1, MAX_RETRIES + 1):
        req = urllib.request.Request(target, data=body, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                return resp.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as e:
            last_err = e
            # 4xx 且非 429：请求本身就有问题，重试无意义
            if 400 <= e.code < 500 and e.code != 429:
                raise
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            last_err = e
        wait = REQUEST_SLEEP * (2 ** attempt)
        print(f"  [警告] 请求失败（第 {attempt}/{MAX_RETRIES} 次）: {last_err}，"
              f"{wait:.1f}s 后重试...", file=sys.stderr)
        time.sleep(wait)
    raise RuntimeError("请求最终失败") from last_err


def efetch_fasta(ids: list) -> str:
    """下载一批 id 的 FASTA。
    id 多时 GET 的 URL 会过长触发 NCBI 代理 414 (Request-URI Too Long)，
    此时改用 POST（参数放请求体，无 URL 长度限制）。
    """
    params = {
        "db": "nucleotide",
        "rettype": "fasta",
        "retmode": "text",
        "id": ",".join(ids),
    }
    # 估算最终 URL 长度
    estimated = len(EFetch_URL) + len(urllib.parse.urlencode(params))
    use_post = estimated > MAX_URL_LEN
    return http_request(EFetch_URL, params, use_post=use_post)


def esearch(query: str, retmax: int, retstart: int = 0) -> dict:
    params = {
        "db": "nucleotide",
        "term": query,
        "retmax": retmax,
        "retstart": retstart,
        "retmode": "json",
    }
    data = json.loads(http_request(ESearch_URL, params))
    if "error" in data:
        raise RuntimeError(f"esearch 报错: {data['error']}")
    return data.get("esearchresult", data)


def get_all_ids(query: str, limit: int = 0) -> list:
    """分页获取 id 列表（esearch 单次上限 10000）；limit>0 时只取前 limit 个。"""
    result = esearch(query, retmax=0)
    total = int(result.get("count", 0))
    if limit:
        total = min(total, limit)
    if total == 0:
        return []
    ids = []
    offset = 0
    while offset < total:
        retmax = min(PAGE_SIZE, total - offset)
        page = esearch(query, retmax=retmax, retstart=offset)
        page_ids = page.get("idlist", [])
        if not page_ids:
            break
        ids.extend(page_ids)
        print(f"  esearch 取 id: {len(ids)}/{total}", flush=True)
        offset += len(page_ids)
        time.sleep(REQUEST_SLEEP)
    return ids


def download(query: str, output: str, limit: int = 0) -> None:
    print(f"搜索式: {query}")
    print("正在执行 esearch ...", flush=True)
    all_ids = get_all_ids(query, limit=limit)
    total = len(all_ids)
    if total == 0:
        print("未检索到任何序列。", file=sys.stderr)
        sys.exit(1)
    if limit:
        print(f"  已通过 -n 限制为前 {limit} 条")

    print(f"共 {total} 条序列，开始下载 -> {output}")
    written = 0
    with open(output, "w", encoding="utf-8") as f:
        for i in range(0, total, BATCH_SIZE):
            batch = all_ids[i:i + BATCH_SIZE]
            text = efetch_fasta(batch)
            if text and not text.endswith("\n"):
                text += "\n"
            f.write(text)
            f.flush()
            seqs = sum(1 for line in text.splitlines() if line.startswith(">"))
            written += seqs
            print(f"  进度: {min(i + BATCH_SIZE, total)}/{total}  "
                  f"（本批 {len(batch)} 条，累计 FASTA 记录 {written}）", flush=True)
            time.sleep(REQUEST_SLEEP)

    print(f"完成：共写入 {written} 条 FASTA 记录 -> {output}")


def main() -> None:
    global API_KEY
    parser = argparse.ArgumentParser(
        description="按搜索条件从 NCBI Nucleotide 下载 FASTA 序列")
    parser.add_argument("-q", "--query", default=DEFAULT_QUERY,
                        help="NCBI 搜索式（默认：HBV 3000-3400bp 基因组）")
    parser.add_argument("-o", "--output", default="hbv_genomic.fasta",
                        help="输出的 FASTA 文件（默认 hbv_genomic.fasta）")
    parser.add_argument("-n", "--limit", type=int, default=0,
                        help="最多下载多少条（0 表示全部，默认 0）")
    parser.add_argument("--api", default=None,
                        help="NCBI API key：直接传 key、@文件名从文件读取、"
                             "或 env:VAR 从环境变量读取（默认自动读 NCBI_API_KEY）")
    args = parser.parse_args()
    API_KEY = load_api_key(args.api)
    if API_KEY:
        print(f"已启用 NCBI API key（{API_KEY[:3]}***）")
    else:
        print("未提供 API key（可加 --api 参数，请求速率可能受限）", file=sys.stderr)
    download(args.query, args.output, limit=args.limit)


if __name__ == "__main__":
    main()
