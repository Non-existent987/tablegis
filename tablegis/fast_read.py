#!/usr/bin/env python
# coding: utf-8
"""
fast_read.py — 大型表格文件快速读取模块

核心思路：
  Excel (.xlsx) 文件用 Polars + Calamine (Rust引擎) 读取，比 openpyxl 快 10-50 倍
  首次读取后自动缓存为 Parquet 列式格式，后续加载仅需 0.02-1 秒
  指定 sheet 时只转换这一个 sheet，不会把所有 sheet 都转换
  CSV 文件用 Polars 原生读取，本身就够快，不需要缓存
"""

import time
import json
import hashlib
import io
import os
import uuid
import subprocess
import tempfile
from pathlib import Path
from typing import Optional, Union, List

import pandas as pd
import polars as pl

CACHE_DIR = ".parquet_cache"

# 视为"缺失"的字符串（空串、Excel 错误值、常见 NA 记号）
_NA_TOKENS = [
    "", "#N/A", "#NA", "#DIV/0!", "#VALUE!", "#REF!", "#NAME?", "#NULL!",
    "#NUM!", "#SPILL!", "#GETTING_DATA", "#CALC!",
    "N/A", "NA", "NULL", "NAN", "NONE", "<NA>", "-", "--",
]

# 支持的文件类型
EXCEL_SUFFIXES = {".xlsx", ".xlsb", ".xls", ".ods"}
TEXT_SUFFIXES = {".csv", ".txt", ".tsv", ".dat", ".psv"}

# ---- 原生 C++ 扩展后端（pybind11 编译，全平台，最快）----
try:
    from tablegis._xlsx2csv import convert as _native_convert
except ImportError:
    _native_convert = None


def _convert_first_sheet(path, csv_out):
    """第一个 sheet 快速转换：优先原生扩展模块 → 内置 exe；成功返回 True"""
    if _native_convert is not None:
        try:
            data = _native_convert(str(path))
            Path(csv_out).write_bytes(data)
            return True
        except Exception:
            pass  # 转换失败 → 回退 exe / calamine
    return _run_exe(path, csv_out)


def _exe_path():
    """内置 xlsx2csv.exe（C++ 极速后端，仅 Windows 可用），未打包时返回 None"""
    if os.name != "nt":
        return None
    p = Path(__file__).parent / "bin" / "xlsx2csv.exe"
    return p if p.exists() else None


def _run_exe(xlsx_path, csv_out):
    """调用内置 exe 转换第一个 sheet，成功返回 True"""
    exe = _exe_path()
    if exe is None:
        return False
    csv_out = Path(csv_out)
    csv_out.parent.mkdir(parents=True, exist_ok=True)
    try:
        r = subprocess.run([str(exe), str(xlsx_path), str(csv_out)],
                           capture_output=True, timeout=1800)
    except (subprocess.TimeoutExpired, OSError):
        return False
    return r.returncode == 0 and csv_out.exists()


def _md5(filepath):
    """计算文件 MD5，用于缓存校验"""
    h = hashlib.md5()
    with open(filepath, "rb") as f:
        while c := f.read(8 * 1024 * 1024):
            h.update(c)
    return h.hexdigest()


def _read_csv_robust(source, sep=","):
    """健壮的 CSV 读取：数字列里混有 #N/A 等错误串时自动降级

    先按常规推断读；失败（如 ComputeError: could not parse `#N/A` as f64）
    则全列按 String 读入，交给 _cast_types 智能转换——
    错误串占比低(<5%)的列转数值、错误值变 null；占比高的列保持文本。
    """
    try:
        return pl.read_csv(source, separator=sep, infer_schema_length=10000,
                           truncate_ragged_lines=True)
    except Exception:
        return _cast_types(pl.read_csv(source, separator=sep, infer_schema_length=0,
                                       truncate_ragged_lines=True))


def _detect_encoding(path):
    """探测文本编码：utf-8 优先，失败退 gbk（中文 CSV 常态）"""
    head = Path(path).read_bytes()[:1 << 18]
    for enc in ("utf-8", "gbk"):
        try:
            head.decode(enc)
            return enc
        except UnicodeDecodeError:
            continue
    return "utf-8"


def _sniff_sep(path, encoding="utf-8"):
    """从首几行推断分隔符（tab / 逗号 / 分号 / 竖线）"""
    try:
        with open(path, "r", encoding=encoding, errors="replace") as f:
            for _ in range(5):
                line = f.readline()
                if not line:
                    break
                line = line.rstrip("\r\n")
                if not line.strip():
                    continue
                counts = {s: line.count(s) for s in ("\t", ",", ";", "|")}
                best = max(counts, key=counts.get)
                if counts[best] > 0:
                    return best
    except OSError:
        pass
    return ","


def _read_text_table(path, sep=None, columns=None):
    """读取文本表格（csv/txt/tsv/dat），自动识别编码和分隔符"""
    enc = _detect_encoding(path)
    sep = sep or _sniff_sep(path, enc)
    src = str(path) if enc == "utf-8" else io.StringIO(path.read_text(encoding=enc))
    df = _read_csv_robust(src, sep=sep)
    df = _cast_types(df)
    if columns:
        df = df.select(columns)
    return df


def _first_sheet(path):
    """第一个 sheet 名（纯标准库，毫秒级）；xlsb 等二进制格式返回 None"""
    try:
        names = read_xlsx_sheetnames(path)
        return names[0] if names else None
    except Exception:
        return None


def _read_sheet_once(path, name, columns=None):
    """一次性读取单个 sheet（不落盘）

    第一个 sheet：原生 C++ 扩展（内存 CSV）→ exe 兜底 → calamine
    其他 sheet：calamine
    """
    is_first = name == _first_sheet(path)
    if is_first:
        if _native_convert is not None:
            try:
                df = _cast_types(_read_csv_robust(io.BytesIO(_native_convert(str(path)))))
                return df.select(columns) if columns else df
            except Exception:
                pass  # → exe / calamine
        tmp = Path(tempfile.gettempdir()) / f"tablegis_{uuid.uuid4().hex}.csv"
        if _run_exe(path, tmp):
            try:
                df = _cast_types(_read_csv_robust(str(tmp)))
                return df.select(columns) if columns else df
            finally:
                tmp.unlink(missing_ok=True)
    df = _read_excel_robust(path, name)
    return df.select(columns) if columns else df


def _read_excel_robust(path, sheet_name):
    """健壮的 excel 读取（calamine）：同样防 #N/A 等错误串炸列"""
    try:
        return pl.read_excel(str(path), sheet_name=sheet_name,
                             engine="calamine", infer_schema_length=10000)
    except Exception:
        return _cast_types(pl.read_excel(str(path), sheet_name=sheet_name,
                                         engine="calamine", infer_schema_length=0))


def _cast_types(df):
    """智能类型转换：数值列转 Float64/Int64，文本列保持 String

    空串、纯空白和 Excel 错误值（#N/A、#DIV/0! 等）都按"缺失"处理，
    不参与失败率统计——否则一个带空单元格的角度列会被误判成纯文本。
    失败率 <5% 才转换，避免把"城市"这类文本列误转。
    """
    exprs, skip = [], set()
    for c in df.columns:
        if df[c].dtype != pl.String:
            continue
        s = df[c]
        upper = s.str.strip_chars().str.to_uppercase()
        valid = ~(s.is_null() | upper.is_in(_NA_TOKENS))
        n_valid = int(valid.sum())
        test = upper.cast(pl.Float64, strict=False)
        n_fail = int((test.is_null() & valid).sum())
        if n_valid > 0 and n_fail / n_valid < 0.05:
            exprs.append(test.alias(c))
        else:
            skip.add(c)
    if exprs:
        df = df.with_columns(exprs)
        ints = []
        for c in df.columns:
            if c in skip or df[c].dtype != pl.Float64:
                continue
            nn = df[c].drop_nulls()
            if len(nn) > 0 and (nn % 1 == 0).all():
                ints.append(pl.col(c).cast(pl.Int64, strict=False).alias(c))
        if ints:
            df = df.with_columns(ints)
    return df


def _load_meta(cache):
    """加载缓存元数据"""
    p = cache / "_meta.json"
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    return {"md5": None, "sheets": {}}


def _save_meta(cache, meta):
    """保存缓存元数据"""
    (cache / "_meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")


def _convert_sheet(xlsx_path, cache, sheet_name):
    """转换单个 sheet 为 Parquet（第一个 sheet 走原生 C++ 后端，比 calamine 快 3-4 倍）"""
    ts = time.time()
    print(f"   ⏳ {sheet_name}...", end=" ", flush=True)
    try:
        df = _read_sheet_once(xlsx_path, sheet_name)
        if len(df) == 0:
            print("跳过(空)")
            return None
        df = _cast_types(df)
        df.write_parquet(str(cache / f"{sheet_name}.parquet"), compression="lz4")
        print(f"✅ {len(df):,}行 {time.time()-ts:.1f}s")
        return len(df)
    except Exception as e:
        print(f"❌ {e}")
        return None


def _ensure_sheet(xlsx_path, sheet_name, force=False):
    """确保单个 sheet 的 Parquet 缓存存在

    只转换这一个 sheet，不会碰其他 sheet
    """
    xlsx_path = Path(xlsx_path)
    cache = Path(CACHE_DIR) / xlsx_path.stem
    cache.mkdir(parents=True, exist_ok=True)
    meta = _load_meta(cache)
    parquet_path = cache / f"{sheet_name}.parquet"

    cur_md5 = _md5(xlsx_path)          # 全文只算一次（大文件 ~0.3s）
    file_changed = meta.get("md5") != cur_md5
    sheet_cached = parquet_path.exists() and not file_changed

    if not force and sheet_cached:
        return cache

    if file_changed:
        print(f"🔄 源文件已更新，重新转换: {sheet_name}")
    else:
        print(f"🔄 缓存中无此sheet，转换: {sheet_name}")

    t0 = time.time()
    rows = _convert_sheet(xlsx_path, cache, sheet_name)

    if rows is not None:
        if file_changed:
            meta = {"md5": cur_md5, "sheets": {}}
        meta["sheets"][sheet_name] = rows
        _save_meta(cache, meta)

    print(f"   转换耗时: {time.time()-t0:.1f}s")
    return cache


def _ensure_all(xlsx_path, force=False):
    """转换所有 sheet（仅在读取全部 sheet 时调用）

    已缓存的 sheet 自动跳过
    """
    xlsx_path = Path(xlsx_path)
    cache = Path(CACHE_DIR) / xlsx_path.stem
    meta = _load_meta(cache)

    if not force and meta.get("md5") == _md5(xlsx_path):
        from python_calamine import CalamineWorkbook
        all_names = set(CalamineWorkbook.from_path(str(xlsx_path)).sheet_names)
        already = {n for n in meta.get("sheets", {}) if (cache / f"{n}.parquet").exists()}
        if already >= all_names:
            return cache

    print(f"🔄 转换: {xlsx_path.name} → Parquet缓存")
    t0 = time.time()
    cache.mkdir(parents=True, exist_ok=True)

    from python_calamine import CalamineWorkbook
    wb = CalamineWorkbook.from_path(str(xlsx_path))
    names = wb.sheet_names
    del wb

    results = {}
    for name in names:
        if not force and (cache / f"{name}.parquet").exists() and meta.get("md5") == _md5(xlsx_path):
            results[name] = meta["sheets"].get(name, 0)
            print(f"   {name}: 已缓存，跳过")
            continue
        rows = _convert_sheet(xlsx_path, cache, name)
        if rows is not None:
            results[name] = rows

    meta = {"md5": _md5(xlsx_path), "sheets": {**meta.get("sheets", {}), **results}}
    _save_meta(cache, meta)
    print(f"✅ 转换完成 {time.time()-t0:.1f}s")
    return cache


def _pick_sheets(xlsx_path, sheet):
    """根据 sheet 参数（int/str/None）解析出要处理的 sheet 名列表，返回 (全部名, 选中名)"""
    try:
        names = read_xlsx_sheetnames(xlsx_path)   # xlsx: 毫秒级，不解压整个工作簿
    except Exception:
        from python_calamine import CalamineWorkbook   # xlsb/xls: 回退 calamine
        names = CalamineWorkbook.from_path(str(xlsx_path)).sheet_names
    if sheet is None:
        return names, names
    if isinstance(sheet, int):
        if not -len(names) <= sheet < len(names):
            raise IndexError(f"sheet 序号越界: {sheet}，共 {len(names)} 个 sheet")
        return names, [names[sheet]]
    if sheet not in names:
        raise ValueError(f"sheet '{sheet}' 不存在，可选: {names}")
    return names, [sheet]


def read_xlsx_sheetnames(file_path):
    """仅适用于 .xlsx 文件，快速提取 sheet 名称列表（毫秒级，纯标准库）

    直接解压读 xl/workbook.xml，不解析任何单元格数据，
    不依赖 calamine/polars，适合超大文件的 sheet 探测。

    Parameters
    ----------
    file_path : str or Path
        .xlsx 文件路径。

    Returns
    -------
    list[str]
        按工作簿顺序排列的 sheet 名称列表。
    """
    import zipfile
    import re
    import html

    with zipfile.ZipFile(file_path, 'r') as z:
        xml_content = z.read('xl/workbook.xml').decode('utf-8')
    names = re.findall(r'<sheet[^>]*?name="([^"]+)"', xml_content)
    return [html.unescape(name) for name in names]


def read_xlsx(file, sheet=0, columns=None):
    """一次性读取 xlsx 为 pandas DataFrame（不落缓存）

    等价于 fast_read(file, sheet=sheet, columns=columns, cache=False)。
    Excel 第一个 sheet 走原生 C++ 后端，比 pandas.read_excel 快 1-2 个数量级。

    Parameters
    ----------
    file : str or Path
        xlsx/xlsb 文件路径
    sheet : int or str, default 0
        sheet 序号或名称
    columns : list of str, optional
        只取指定列

    Returns
    -------
    pandas.DataFrame

    Examples
    --------
    >>> import tablegis as tg
    >>> df = tg.read_xlsx("data.xlsx")            # 第一个 sheet
    >>> df = tg.read_xlsx("data.xlsx", sheet="站点信息")
    """
    return fast_read(file, sheet=sheet, columns=columns, cache=False)


def xlsx2csv(xlsx, csv=None, sheet=0):
    """xlsx 快速转 csv（calamine 引擎读取 + polars 写出，无缓存）

    Parameters
    ----------
    xlsx : str or Path
        xlsx/xlsb 文件路径
    csv : str or Path, optional
        输出 csv 路径。默认与源文件同名（data.xlsx → data.csv）。
        sheet=None 转全部 sheet 时，每个 sheet 一个 csv：
        data.xlsx → data_表名.csv
    sheet : int or str or None, default 0
        sheet 序号或名称；None 表示全部 sheet

    Returns
    -------
    str or list of str
        生成的 csv 路径（全部 sheet 时返回列表）

    Examples
    --------
    >>> import tablegis as tg
    >>> tg.xlsx2csv("data.xlsx")                    # data.xlsx → data.csv
    >>> tg.xlsx2csv("data.xlsx", sheet="站点信息")   # 指定 sheet
    >>> tg.xlsx2csv("data.xlsx", "out/全量.csv")     # 指定输出路径
    >>> tg.xlsx2csv("data.xlsx", sheet=None)        # 全部 sheet → data_表名.csv
    """
    path = Path(xlsx)
    if not path.exists():
        raise FileNotFoundError(f"文件不存在: {path}")

    names, sel = _pick_sheets(path, sheet)
    out_paths = []
    for idx, name in enumerate(sel):
        df = None
        if len(sel) == 1:
            out = Path(csv) if csv else path.with_suffix(".csv")
        else:
            out = Path(csv) if csv else path.with_suffix("")
            out = out.with_name(f"{out.stem}_{name}{out.suffix if out.suffix else '.csv'}")
        out.parent.mkdir(parents=True, exist_ok=True)

        # ---- 第一个 sheet 走原生扩展/exe ----
        if name == names[0] and _convert_first_sheet(path, out):
            out_paths.append(str(out))
            continue

        # ---- calamine 后端 ----
        df = pl.read_excel(str(path), sheet_name=name,
                           engine="calamine", infer_schema_length=10000)
        df = _cast_types(df)
        df.write_csv(str(out))
        out_paths.append(str(out))
    return out_paths[0] if len(out_paths) == 1 else out_paths




def fast_read(file, sheet=0, columns=None, sep=None, refresh=False,
              to_pandas=True, cache=True):
    """快速读取任意表格文件（Excel / CSV / TXT），返回 DataFrame

    统一入口，支持：
      - Excel: .xlsx / .xlsb / .xls / .ods
      - 文本: .csv / .txt / .tsv / .dat / .psv（自动识别编码与分隔符）

    Excel 第一个 sheet 走原生 C++ 后端（比 openpyxl 快 1-2 个数量级）；
    cache=True（默认）时首次读取落地 Parquet 缓存，之后同 sheet 读取约 0.1-1 秒。
    想要"不留任何缓存文件"的一次性读取，用 cache=False（等价于 read_xlsx）。

    Parameters
    ----------
    file : str or Path
        文件路径
    sheet : int or str or None, default 0
        sheet 序号或名称；None = 读取全部 sheet（返回 dict）
    columns : list of str, optional
        只加载指定列，减少内存占用和加载时间
    sep : str, optional
        文本文件分隔符。默认 None = 自动嗅探（tab / 逗号 / 分号 / 竖线）
    refresh : bool, default False
        True = 强制重新转换（源文件更新后使用）
    to_pandas : bool, default True
        True 返回 pandas DataFrame；False 返回 polars DataFrame（更快更省内存）
    cache : bool, default True
        True = 使用 Parquet 缓存（重复读取极快）
        False = 一次性读取，不在磁盘留任何缓存文件

    Returns
    -------
    pandas.DataFrame or polars.DataFrame
        sheet 指定时返回单个 DataFrame；sheet=None 时返回 dict {sheet名: DataFrame}

    Examples
    --------
    >>> import tablegis as tg
    >>> # Excel 指定 sheet（首次转换，之后走缓存）
    >>> df = tg.fast_read("工参.xlsx", sheet="小区明细")
    >>> # 一次性读取，不落缓存
    >>> df = tg.fast_read("工参.xlsx", sheet="小区明细", cache=False)
    >>> # CSV / TXT，自动识别分隔符和编码
    >>> df = tg.fast_read("data.csv")
    >>> df = tg.fast_read("data.txt", sep="\\t")
    >>> # 只取几列（更快更省内存）
    >>> df = tg.fast_read("工参.xlsx", columns=["城市", "经度", "纬度"])
    >>> # 读取全部 sheet
    >>> data = tg.fast_read("工参.xlsx", sheet=None)
    >>> # 源文件更新后强制刷新缓存
    >>> df = tg.fast_read("工参.xlsx", sheet="小区明细", refresh=True)
    """
    path = Path(file)
    if not path.exists():
        raise FileNotFoundError(f"文件不存在: {path}")

    suffix = path.suffix.lower()

    # ---- 文本表格：csv / txt / tsv / dat ----
    if suffix in TEXT_SUFFIXES:
        df = _read_text_table(path, sep=sep, columns=columns)
        return df.to_pandas() if to_pandas else df

    if suffix not in EXCEL_SUFFIXES:
        raise ValueError(
            f"不支持的文件类型: {suffix or '(无扩展名)'}，"
            f"支持 Excel {sorted(EXCEL_SUFFIXES)} 和文本 {sorted(TEXT_SUFFIXES)}")

    names, sel = _pick_sheets(path, sheet)

    # ---- 不缓存：一次性读取 ----
    if not cache:
        if sheet is None:
            out = {n: _read_sheet_once(path, n, columns) for n in sel}
            return {k: v.to_pandas() for k, v in out.items()} if to_pandas else out
        df = _read_sheet_once(path, sel[0], columns)
        return df.to_pandas() if to_pandas else df

    # ---- 走 Parquet 缓存 ----
    if sheet is None:
        cdir = _ensure_all(path, force=refresh)
        meta = _load_meta(cdir)
        raw = {
            n: pl.read_parquet(str(cdir / f"{n}.parquet"), columns=columns)
            for n in sel
            if (cdir / f"{n}.parquet").exists() and n in meta.get("sheets", {})
        }
        if to_pandas:
            return {n: d.to_pandas() for n, d in raw.items()}
        return raw

    name = sel[0]
    cdir = _ensure_sheet(path, name, force=refresh)
    p = cdir / f"{name}.parquet"
    if not p.exists():
        raise FileNotFoundError(f"sheet '{name}' 转换失败或不存在")
    result = pl.read_parquet(str(p), columns=columns)
    return result.to_pandas() if to_pandas else result
