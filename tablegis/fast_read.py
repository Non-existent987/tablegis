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


def _cast_types(df):
    """智能类型转换：纯数字的字符串列转数值，纯文本列保持不变

    Parameters
    ----------
    df : polars.DataFrame
        原始DataFrame，可能有很多String列

    Returns
    -------
    polars.DataFrame
        类型转换后的DataFrame

    Notes
    -----
    Calamine 读取混合类型列时 fallback 为 String，
    这里尝试将看起来像数字的字符串列转回 Float64/Int64，
    只有当转换失败率 < 5% 时才转换（避免把"城市"这种纯文本列误转）
    """
    exprs, skip = [], set()
    for c in df.columns:
        if df[c].dtype != pl.String:
            continue
        test = df[c].cast(pl.Float64, strict=False)
        orig_null, new_null = df[c].null_count(), test.null_count()
        non_null = len(df) - orig_null
        if non_null > 0 and (new_null - orig_null) / non_null < 0.05:
            exprs.append(pl.col(c).cast(pl.Float64, strict=False).alias(c))
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
    """转换单个 sheet 为 Parquet"""
    ts = time.time()
    print(f"   ⏳ {sheet_name}...", end=" ", flush=True)
    try:
        df = pl.read_excel(str(xlsx_path), sheet_name=sheet_name,
                           engine="calamine", infer_schema_length=10000)
        if len(df) == 0:
            print("跳过(空)")
            return None
        df = _cast_types(df)
        df.write_parquet(str(cache / f"{sheet_name}.parquet"), compression="zstd")
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

    file_changed = meta.get("md5") != _md5(xlsx_path)
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
            meta = {"md5": _md5(xlsx_path), "sheets": {}}
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
    from python_calamine import CalamineWorkbook
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


def read_xlsx(file, sheet=0, columns=None):
    """快速读取 xlsx 为 pandas DataFrame（calamine 引擎，无缓存，一次性读取）

    比 pandas.read_excel (openpyxl) 快 10-50 倍，适合大文件。
    直接返回 pandas，不落任何中间文件。

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
    path = Path(file)
    if not path.exists():
        raise FileNotFoundError(f"文件不存在: {path}")
    names, sel = _pick_sheets(path, sheet)
    name = sel[0]

    # ---- 第一个 sheet 走原生扩展/exe（快 10-30 倍）----
    if name == names[0]:
        # 原生扩展：CSV 直接在内存里流转，不落盘
        if _native_convert is not None:
            try:
                data = _native_convert(str(path))
                df = pl.read_csv(io.BytesIO(data), infer_schema_length=10000)
                df = _cast_types(df)
                if columns:
                    df = df.select(columns)
                return df.to_pandas()
            except Exception:
                pass  # 转换失败 → 回退 exe / calamine
        # exe 后端：经临时文件
        if _run_exe(path, tmp := Path(tempfile.gettempdir()) / f"tablegis_{uuid.uuid4().hex}.csv"):
            try:
                df = pl.read_csv(str(tmp), infer_schema_length=10000)
                df = _cast_types(df)
                if columns:
                    df = df.select(columns)
                return df.to_pandas()
            finally:
                tmp.unlink(missing_ok=True)

    # ---- calamine 后端 ----
    df = pl.read_excel(str(path), sheet_name=name,
                       engine="calamine", infer_schema_length=10000)
    df = _cast_types(df)
    if columns:
        df = df.select(columns)
    return df.to_pandas()


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


def fast_read(file, sheet=None, columns=None, refresh=False, to_pandas=False):
    """快速读取任意表格文件，按需 Parquet 缓存加速

    支持读取 Excel (.xlsx/.xlsb) 和 CSV (.csv) 文件。
    Excel 文件首次读取后自动缓存为 Parquet 格式，后续加载速度提升 200-20000 倍。
    指定 sheet 时只转换这一个 sheet，不会转换其他 sheet。

    Parameters
    ----------
    file : str or Path
        文件路径，支持 .xlsx, .xlsb, .csv 格式
    sheet : str, optional
        指定 Excel sheet 名称。None 表示读取全部 sheet。
        指定 sheet 时只转换这一个，速度最快。
    columns : list of str, optional
        只加载指定列，减少内存占用和加载时间。
        例如 columns=["城市", "经度", "纬度"]
    refresh : bool, default False
        True = 强制重新转换（源文件更新后使用）
    to_pandas : bool, default False
        True = 返回 pandas DataFrame（方便与 tablegis 其他函数衔接）
        False = 返回 polars DataFrame（更快更省内存）

    Returns
    -------
    polars.DataFrame or pandas.DataFrame
        当指定 sheet 时，返回单个 DataFrame
        当 sheet=None 时，返回 dict: {sheet名: DataFrame}

    Raises
    ------
    FileNotFoundError
        文件不存在或 sheet 不存在

    Examples
    --------
    >>> import tablegis as tg
    >>> # 读取指定sheet（只转换这一个，首次约5秒）
    >>> df = tg.fast_read("data.xlsx", sheet="站点信息")
    >>> # 再次读取同一sheet（缓存加载，0.02秒）
    >>> df = tg.fast_read("data.xlsx", sheet="站点信息")
    >>> # 只加载几列（更快更省内存）
    >>> df = tg.fast_read("data.xlsx", sheet="站点信息", columns=["城市","经度","纬度"])
    >>> # 返回 pandas DataFrame（与 tablegis 其他函数衔接）
    >>> pd_df = tg.fast_read("data.xlsx", sheet="站点信息", to_pandas=True)
    >>> # 读取全部sheet
    >>> data = tg.fast_read("data.xlsx")
    >>> # 读取CSV
    >>> df = tg.fast_read("data.csv")
    >>> # 源文件更新了，强制刷新缓存
    >>> df = tg.fast_read("data.xlsx", sheet="站点信息", refresh=True)

    Notes
    -----
    性能对比（290万行10个sheet的Excel文件）：
    - pandas + openpyxl: 单sheet 244秒，全量 ~40分钟
    - 本函数首次（含转换）: 单sheet ~5秒，全量 ~2.5分钟
    - 本函数缓存加载: 单sheet 0.02秒，全量 0.12秒
    - 内存占用: pandas 238MB(单sheet) → Parquet缓存 82MB(全量)
    """
    path = Path(file)

    if not path.exists():
        raise FileNotFoundError(f"文件不存在: {path}")

    # ---- CSV: 直接读 ----
    if path.suffix.lower() == ".csv":
        result = pl.read_csv(str(path), columns=columns, ignore_errors=True)
        return result.to_pandas() if to_pandas else result

    # ---- Excel + 指定sheet: 只转换这一个 ----
    if sheet:
        cache = _ensure_sheet(path, sheet, force=refresh)
        p = cache / f"{sheet}.parquet"
        if not p.exists():
            raise FileNotFoundError(f"sheet '{sheet}' 转换失败或不存在")
        result = pl.read_parquet(str(p), columns=columns)
        return result.to_pandas() if to_pandas else result

    # ---- Excel + 全部sheet ----
    cache = _ensure_all(path, force=refresh)
    meta = _load_meta(cache)
    raw = {
        name: pl.read_parquet(str(cache / f"{name}.parquet"), columns=columns)
        for name in meta.get("sheets", {})
        if (cache / f"{name}.parquet").exists()
    }
    if to_pandas:
        return {name: df.to_pandas() for name, df in raw.items()}
    return raw
