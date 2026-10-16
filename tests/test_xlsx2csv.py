# -*- coding: utf-8 -*-
"""xlsx2csv / read_xlsx 功能验证"""
import time
import os
import sys

import pandas as pd

import importlib.util

# 直接加载 fast_read 模块，绕开 tablegis/__init__（其 core.py 依赖 geopandas，与本测试无关）
_spec = importlib.util.spec_from_file_location(
    "fast_read", r"D:\codetools\tablegis\tablegis\fast_read.py")
_fast = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_fast)


class _TG:
    fast_read = staticmethod(_fast.fast_read)
    xlsx2csv = staticmethod(_fast.xlsx2csv)
    read_xlsx = staticmethod(_fast.read_xlsx)

tg = _TG()

# 造测试数据：10万行 x 5列（含中文、数字混合列）
n = 100_000
src = pd.DataFrame({
    "城市": ["北京", "上海", "广州", "深圳"] * (n // 4),
    "经度": [116.407, 121.473, 113.264, 114.057] * (n // 4),
    "纬度": [39.904, 31.230, 23.129, 22.543] * (n // 4),
    "编号": range(n),
    "备注": [f"备注{i}" for i in range(n)],
})
xlsx = r"D:\codetools\tablegis\tests\_tmp_big.xlsx"
csv_out = r"D:\codetools\tablegis\tests\_tmp_big.csv"

src.to_excel(xlsx, index=False, sheet_name="站点")
print(f"测试文件: {n:,} 行 x 5 列, {os.path.getsize(xlsx)/1024/1024:.1f} MB")

# 1) read_xlsx → pandas
t0 = time.time()
df = tg.read_xlsx(xlsx)
t_fast = time.time() - t0
print(f"\n[read_xlsx] {len(df):,} 行, {t_fast:.2f}s, dtypes:\n{df.dtypes.to_dict()}")

# 正确性：与源数据逐列对比
assert list(df.columns) == list(src.columns), "列名不一致"
assert len(df) == n
assert abs(df["经度"].iloc[1] - 121.473) < 1e-9, "数值列有误差"
assert df["备注"].iloc[99999] == "备注99999", "文本列不一致"
print("[read_xlsx] 数据校验通过 ✓")

# 2) xlsx2csv 单 sheet
t0 = time.time()
out = tg.xlsx2csv(xlsx)
t_conv = time.time() - t0
assert out == csv_out, out
size = os.path.getsize(csv_out) / 1024 / 1024
print(f"\n[xlsx2csv] {out}, {t_conv:.2f}s, {size:.1f} MB")

# csv 内容正确性
back = pd.read_csv(csv_out)
assert list(back.columns) == list(src.columns) and len(back) == n
assert back["编号"].iloc[n-1] == n - 1
print("[xlsx2csv] csv 内容校验通过 ✓")

# 3) sheet 名称 + 指定输出路径
out2 = tg.xlsx2csv(xlsx, sheet="站点", csv=r"D:\codetools\tablegis\tests\_tmp_named.csv")
assert out2.endswith("_tmp_named.csv")
print(f"[xlsx2csv] 指定路径/sheet: {out2} ✓")

# 4) sheet=None 全部 sheet
with pd.ExcelWriter(r"D:\codetools\tablegis\tests\_tmp_multi.xlsx") as w:
    src.head(10).to_excel(w, index=False, sheet_name="甲")
    src.head(20).to_excel(w, index=False, sheet_name="乙")
outs = tg.xlsx2csv(r"D:\codetools\tablegis\tests\_tmp_multi.xlsx", sheet=None)
print(f"[xlsx2csv] 全部sheet: {outs}")
assert len(outs) == 2 and all(os.path.exists(p) for p in outs)

# 清理临时文件
for p in [xlsx, csv_out, r"D:\codetools\tablegis\tests\_tmp_named.csv",
          r"D:\codetools\tablegis\tests\_tmp_multi.xlsx",
          r"D:\codetools\tablegis\tests\_tmp_multi_甲.csv",
          r"D:\codetools\tablegis\tests\_tmp_multi_乙.csv"]:
    if os.path.exists(p):
        os.remove(p)

print("\n全部通过 ✅")
