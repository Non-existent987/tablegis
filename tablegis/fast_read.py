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
from pathlib import Path
from typing import Optional, Union, List

import pandas as pd
import polars as pl

CACHE_DIR = ".parquet_cache"


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
