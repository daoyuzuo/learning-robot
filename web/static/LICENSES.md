# 第三方素材与许可证

TestBridge 的前端样式与图标**全部内置于仓库**，运行时不请求任何外部资源
（CSP 为 `style-src 'self'; script-src 'self'`，`tb build` 产物必须离线可用）。

## 图标

来源：[Lucide Icons](https://github.com/lucide-icons/lucide)
使用范围：`src/testbridge/icons.py` 中 `ICONS` 列出的图形。
改动方式：仅保留 `path` / `circle` / `rect` / `polyline` 几何数据，
把 `stroke-width`、`stroke-linecap` 等表现属性移到统一的 `<svg>` 包装上，
以便通过 `currentColor` 继承 CSS 颜色（浅色/深色模式共用同一份图形）。

### ISC License

```
ISC License

Copyright (c) 2026 Lucide Icons and Contributors

Permission to use, copy, modify, and/or distribute this software for any
purpose with or without fee is hereby granted, provided that the above
copyright notice and this permission notice appear in all copies.

THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES
WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF
MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR
ANY SPECIAL, DIRECT, INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES
WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN AN
ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF
OR IN CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.
```

### 其中派生自 Feather 的图标（MIT）

Lucide 中以下图标源自 [Feather](https://github.com/feathericons/feather)。
本项目用到的：`check`、`circle`、`x`、`chevron-down`、`chevron-left`、
`chevron-right`、`external-link`、`send`、`target`、`clock`、`info`、
`refresh-cw`、`play`、`mic`、`file-text`、`book-open`。

```
The MIT License (MIT)

Copyright (c) 2013-present Cole Bemis

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

## 字体

**不使用任何下载字体。** 全部走系统字体栈：

- 无衬线：`system-ui` → `Segoe UI` → `Microsoft YaHei` → `Noto Sans SC` → `PingFang SC`
- 等宽：`ui-monospace` → `Cascadia Code` → `Consolas`
- 衬线（**仅用于拉丁字母与数字**，不用于中文）：`Charter` → `Georgia` → `Cambria`

中文字体在各地各平台授权差异大，且中文 Web 字体子集动辄数 MB，与本项目
"离线单文件"目标冲突，因此不打包中文字体。

## 未采用的候选

| 候选 | 原因 |
|---|---|
| Tabler Icons（MIT） | 许可证同样宽松，但与 Lucide 风格重复，无需两套 |
| Google Fonts / 任何 CDN | 违反 CSP 与离线约束 |
| 图标字体（iconfont） | 额外请求、字形锯齿、无法 `currentColor` 继承 |
| Tailwind / shadcn/ui 构建链 | 违反"无前端框架、无构建步骤"的既有决定 |