// tablegis._xlsx2csv — 极限性能 XLSX -> CSV 转换扩展模块
// 策略: ZIP中央目录定位 -> libdeflate 整流解压 -> 多线程字节扫描 XML -> 返回 CSV bytes
// 核心逻辑与 xlsx2csv.exe (main.cpp) 完全一致，包装为 pybind11 模块
#include <pybind11/pybind11.h>
#include <pybind11/stl/filesystem.h>

#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <cstdint>
#include <string>
#include <vector>
#include <thread>
#include <chrono>
#include <algorithm>
#include <filesystem>
#include <fstream>
#include <stdexcept>

#include "libdeflate.h"

namespace py = pybind11;

// ---------- ZIP ----------
struct ZipEntry {
    const uint8_t* data;   // 压缩数据指针(指向文件映像内)
    uint64_t usize, csize;
    uint16_t method;
    bool found = false;
};

static uint16_t rd16(const uint8_t* p) { return p[0] | (p[1] << 8); }
static uint32_t rd32(const uint8_t* p) { return p[0] | (p[1] << 8) | (p[2] << 16) | ((uint32_t)p[3] << 24); }

static ZipEntry find_entry(const uint8_t* file, size_t fsize, const char* name) {
    ZipEntry e{};
    // 找 EOCD
    size_t lo = fsize > 70000 ? fsize - 70000 : 0;
    const uint8_t* eocd = nullptr;
    for (size_t i = fsize - 22; ; i--) {
        if (file[i] == 'P' && file[i+1] == 'K' && file[i+2] == 5 && file[i+3] == 6) { eocd = file + i; break; }
        if (i == lo) break;
    }
    if (!eocd) return e;
    uint32_t cd_off = rd32(eocd + 16);
    uint16_t count = rd16(eocd + 10);
    size_t name_len = strlen(name);
    const uint8_t* p = file + cd_off;
    for (uint16_t i = 0; i < count; i++) {
        if (rd32(p) != 0x02014b50) break;
        uint16_t method = rd16(p + 10);
        uint32_t csize = rd32(p + 20), usize = rd32(p + 24);
        uint16_t nl = rd16(p + 28), el = rd16(p + 30), cl = rd16(p + 32);
        uint32_t lho = rd32(p + 42);
        if (nl == name_len && memcmp(p + 46, name, nl) == 0) {
            // 解析本地文件头拿数据偏移
            const uint8_t* lh = file + lho;
            uint16_t lnl = rd16(lh + 26), lel = rd16(lh + 28);
            e.data = lh + 30 + lnl + lel;
            e.csize = csize; e.usize = usize; e.method = method; e.found = true;
            return e;
        }
        p += 46 + nl + el + cl;
    }
    return e;
}

// ---------- 解压 ----------
static std::vector<char> inflate_entry(const ZipEntry& e) {
    std::vector<char> out;
    if (!e.found) return out;
    if (e.method == 0) { // stored
        out.assign((const char*)e.data, (const char*)e.data + e.usize);
        return out;
    }
    out.resize(e.usize);
    libdeflate_decompressor* d = libdeflate_alloc_decompressor();
    size_t actual = 0;
    int rc = libdeflate_deflate_decompress(d, e.data, e.csize, out.data(), e.usize, &actual);
    libdeflate_free_decompressor(d);
    if (rc != LIBDEFLATE_SUCCESS) { out.clear(); return out; }
    out.resize(actual);
    return out;
}

// ---------- sharedStrings ----------
struct SsTable {
    std::vector<char> buf;                    // 所有字符串字节池
    std::vector<std::pair<uint32_t,uint32_t>> items; // (offset,len)
    bool empty() const { return items.empty(); }
    const char* get(uint32_t i, uint32_t& len) const {
        len = items[i].second; return buf.data() + items[i].first;
    }
};

static SsTable parse_shared_strings(const char* x, size_t n) {
    SsTable t;
    t.buf.reserve(n / 4);
    const char* p = x; const char* end = x + n;
    while (p < end) {
        const char* si = (const char*)memchr(p, '<', end - p);
        if (!si || si + 3 >= end) break;
        if (si[1] == 's' && si[2] == 'i' && (si[3] == '>' || si[3] == ' ')) {
            // 收集本 <si> 内所有 <t...>...</t>
            const char* siend = strstr(si, "</si>");
            if (!siend) break;
            uint32_t base = (uint32_t)t.buf.size();
            const char* q = si;
            while (q < siend) {
                const char* tt = (const char*)memchr(q, '<', siend - q);
                if (!tt) break;
                if (tt[1] == 't' && (tt[2] == '>' || tt[2] == ' ')) {
                    const char* gt = (const char*)memchr(tt, '>', siend - tt);
                    const char* vs = gt + 1;
                    const char* ve = (const char*)memchr(vs, '<', siend - vs);
                    if (!ve) ve = siend;
                    t.buf.insert(t.buf.end(), vs, ve);
                    q = ve;
                } else q = tt + 1;
            }
            t.items.push_back({base, (uint32_t)t.buf.size() - base});
            p = siend + 5;
        } else p = si + 1;
    }
    return t;
}

// ---------- CSV 输出 ----------
static inline void append_escaped(std::string& out, const char* v, size_t n) {
    bool need_quote = false, has_amp = false;
    for (size_t i = 0; i < n; i++) {
        char c = v[i];
        if (c == '"' || c == ',' || c == '\n' || c == '\r') need_quote = true;
        else if (c == '&') has_amp = true;
    }
    if (!need_quote && !has_amp) { out.append(v, n); return; }
    std::string tmp;
    tmp.reserve(n + 8);
    const char* src = v; size_t len = n;
    if (has_amp) { // 解码 XML 实体
        for (size_t i = 0; i < n; i++) {
            if (v[i] == '&') {
                if (i + 5 <= n && !memcmp(v + i, "&amp;", 5))  { tmp += '&';  i += 4; continue; }
                if (i + 4 <= n && !memcmp(v + i, "&lt;", 4))   { tmp += '<';  i += 3; continue; }
                if (i + 4 <= n && !memcmp(v + i, "&gt;", 4))   { tmp += '>';  i += 3; continue; }
                if (i + 6 <= n && !memcmp(v + i, "&quot;", 6)) { tmp += '"';  i += 5; continue; }
                if (i + 6 <= n && !memcmp(v + i, "&apos;", 6)) { tmp += '\''; i += 5; continue; }
                if (i + 2 < n && v[i+1] == '#') { // &#NN; / &#xNN;
                    size_t j = i + 2; uint32_t cp = 0; bool hex = false;
                    if (j < n && (v[j] == 'x' || v[j] == 'X')) { hex = true; j++; }
                    while (j < n && v[j] != ';') {
                        char c = v[j++];
                        cp = cp * (hex ? 16 : 10) + (c <= '9' ? c - '0' : (c | 32) - 'a' + 10);
                    }
                    if (cp < 0x80) tmp += (char)cp;
                    else if (cp < 0x800) { tmp += (char)(0xC0 | cp >> 6); tmp += (char)(0x80 | (cp & 63)); }
                    else { tmp += (char)(0xE0 | cp >> 12); tmp += (char)(0x80 | (cp >> 6 & 63)); tmp += (char)(0x80 | (cp & 63)); }
                    i = j; continue;
                }
            }
            tmp += v[i];
        }
        src = tmp.data(); len = tmp.size();
    }
    if (need_quote) {
        out.push_back('"');
        for (size_t i = 0; i < len; i++) {
            if (src[i] == '"') out.push_back('"');
            out.push_back(src[i]);
        }
        out.push_back('"');
    } else {
        out.append(src, len);
    }
}

// ---------- 行块扫描 ----------
struct Ctx {
    const char* xml;
    const SsTable* sst;
};

// 找 pos 之后下一个 "<row" 起点
static const char* next_row(const char* p, const char* end) {
    while (p < end) {
        const char* lt = (const char*)memchr(p, '<', end - p);
        if (!lt || lt + 5 >= end) return end;
        if (lt[1] == 'r' && lt[2] == 'o' && lt[3] == 'w' && (lt[4] == ' ' || lt[4] == '>' || lt[4] == '/'))
            return lt;
        p = lt + 1;
    }
    return end;
}

static void scan_chunk(const Ctx& ctx, const char* p, const char* end, std::string& out) {
    out.reserve((size_t)(end - p) / 2 + 64);
    int last_col = -1;
    while (p < end) {
        const char* lt = (const char*)memchr(p, '<', end - p);
        if (!lt || lt + 2 >= end) break;
        char c1 = lt[1];
        if (c1 == 'c' && (lt[2] == ' ' || lt[2] == '>')) {
            // ---- <c ...> ----
            const char* gt = (const char*)memchr(lt + 2, '>', end - lt - 2);
            if (!gt) break;
            bool selfclose = gt[-1] == '/';
            int col = -1; char t = 0;
            const char* a = lt + 2;
            while (a < gt) {
                if (a + 1 < gt && a[0] == 'r' && a[1] == '=') {
                    a += 2; char q = *a++;
                    int v = 0;
                    while (a < gt && *a >= 'A' && *a <= 'Z') { v = v * 26 + (*a - 'A' + 1); a++; }
                    col = v - 1;
                    while (a < gt && *a != q) a++;
                    if (a < gt) a++;
                } else if (a + 1 < gt && a[0] == 't' && a[1] == '=') {
                    a += 2; char q = *a++;
                    if (a < gt) t = *a;
                    while (a < gt && *a != q) a++;
                    if (a < gt) a++;
                } else a++;
            }
            if (col < 0) col = last_col + 1;
            // 分隔符: 行首补 col 个逗号(前导空列), 否则补 col-last_col 个(含本列分隔符)
            if (last_col < 0) {
                for (int k = 0; k < col; k++) out.push_back(',');
            } else {
                for (int k = last_col; k < col; k++) out.push_back(',');
            }

            if (!selfclose) {
                const char* p2 = gt + 1;
                if (p2 + 2 < end && p2[0] == '<' && p2[1] == 'v' && p2[2] == '>') {
                    const char* vs = p2 + 3;
                    const char* ve = (const char*)memchr(vs, '<', end - vs);
                    if (!ve) break;
                    if (t == 's' && ctx.sst && !ctx.sst->empty()) {
                        uint32_t idx = (uint32_t)strtoul(vs, nullptr, 10);
                        if (idx < ctx.sst->items.size()) {
                            uint32_t len; const char* sv = ctx.sst->get(idx, len);
                            append_escaped(out, sv, len);
                        }
                    } else if (t == 'b') {
                        out.append(*vs == '1' ? "TRUE" : "FALSE");
                    } else {
                        append_escaped(out, vs, (size_t)(ve - vs));
                    }
                    p = ve;
                } else if (p2 + 3 < end && p2[0] == '<' && p2[1] == 'i' && p2[2] == 's') {
                    // inlineStr: <is><t...>text</t></is>
                    const char* tt = (const char*)memchr(p2 + 3, '<', end - p2 - 3);
                    if (tt && tt + 2 < end && tt[1] == 't') {
                        const char* tgt = (const char*)memchr(tt, '>', end - tt);
                        const char* vs = tgt + 1;
                        const char* ve = (const char*)memchr(vs, '<', end - vs);
                        if (!ve) break;
                        append_escaped(out, vs, (size_t)(ve - vs));
                        p = ve;
                    } else p = gt + 1;
                } else {
                    p = gt + 1;
                }
            } else {
                p = gt + 1;
            }
            last_col = col;
        } else if (c1 == '/' && lt[2] == 'r') {
            out.push_back('\n');
            last_col = -1;
            p = lt + 6;
        } else if (c1 == 'r' && lt + 4 < end && lt[2] == 'o' && lt[3] == 'w') {
            // <row ...> 或空行 <row .../>
            const char* gt = (const char*)memchr(lt, '>', end - lt);
            if (!gt) break;
            if (gt[-1] == '/') { out.push_back('\n'); last_col = -1; }
            p = gt + 1;
        } else {
            p = lt + 1;
        }
    }
}

// ---------- 对外接口: convert(path) -> CSV bytes ----------
static py::bytes convert(const std::filesystem::path& path) {
    // 读文件（fs::path 支持 Windows 中文路径）
    std::ifstream f(path, std::ios::binary);
    if (!f) throw std::runtime_error("cannot open " + path.string());
    f.seekg(0, std::ios::end);
    long fsz = (long)f.tellg();
    f.seekg(0, std::ios::beg);
    std::vector<uint8_t> file(fsz);
    if (!f.read((char*)file.data(), fsz)) throw std::runtime_error("read error");
    f.close();

    std::string out;
    {
        // 重活全程释放 GIL，多线程扫描不被 Python 阻塞
        py::gil_scoped_release release;

        // sharedStrings(可选)
        SsTable sst;
        ZipEntry sse = find_entry(file.data(), fsz, "xl/sharedStrings.xml");
        if (sse.found && sse.usize > 64) {
            std::vector<char> ssx = inflate_entry(sse);
            sst = parse_shared_strings(ssx.data(), ssx.size());
        }

        // sheet1
        ZipEntry se = find_entry(file.data(), fsz, "xl/worksheets/sheet1.xml");
        if (!se.found) throw std::runtime_error("sheet1.xml not found");
        std::vector<char> xml = inflate_entry(se);
        if (xml.empty()) throw std::runtime_error("decompress failed");

        const char* xb = xml.data();
        const char* xe = xb + xml.size();
        const char* first = next_row(xb, xe);

        unsigned nth = std::thread::hardware_concurrency();
        if (nth == 0) nth = 4;
        if (nth > 16) nth = 16;

        std::vector<const char*> bounds(nth + 1);
        bounds[0] = first;
        size_t span = xe - first;
        for (unsigned i = 1; i < nth; i++)
            bounds[i] = next_row(xb + span * i / nth, xe);
        bounds[nth] = xe;

        Ctx ctx{xb, &sst};
        std::vector<std::string> outs(nth);
        std::vector<std::thread> threads;
        for (unsigned i = 0; i < nth; i++)
            threads.emplace_back([&, i] { scan_chunk(ctx, bounds[i], bounds[i + 1], outs[i]); });
        for (auto& th : threads) th.join();

        // 拼接（串行拷贝一次，~300MB 内存带宽约 0.1s）
        size_t total = 0;
        for (auto& s : outs) total += s.size();
        out.reserve(total + 1);
        for (auto& s : outs) out.append(s);
    }

    return py::bytes(out.data(), out.size());
}

PYBIND11_MODULE(_xlsx2csv, m) {
    m.doc() = "tablegis ultra-fast xlsx -> csv converter (libdeflate + multithreaded XML scan)";
    m.def("convert", &convert, py::arg("path"),
          "Convert the first worksheet of an xlsx file to CSV bytes.\n"
          "Throws RuntimeError on failure.");
}
