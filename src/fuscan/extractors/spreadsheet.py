"""电子表格提取器：XLSX 与 ODS。

XLSX/XLSM 使用 calamine（Rust + PyO3）提取所有工作表单元格文本，相比
openpyxl 的纯 Python 逐单元格遍历有 5-10 倍提速，且 Rust 侧执行期间释放
GIL，避免阻塞 Qt 主线程。ODS 因 calamine 0.3.x 对 odfpy 生成的标准 ODS
解析不完整，暂保留 odfpy 实现（Python 3.10+ 虽使用 calamine 0.8.2，但
ODS 提取器未切换以保持行为一致）。
"""

from __future__ import annotations

import io
import logging
from pathlib import Path

from typing_extensions import override

from fuscan.extractors.base import Extractor, ExtractorError, SpeedTier

__all__ = ["OdsExtractor", "XlsxExtractor"]

logger = logging.getLogger(__name__)

_MAX_ROWS = 10000
_MAX_COLS = 256


def _extract_calamine_workbook(
    data: bytes,
    max_rows: int = _MAX_ROWS,
    max_cols: int = _MAX_COLS,
    error_label: str = "工作簿",
) -> str:
    """使用 calamine (Rust + PyO3) 提取工作簿所有工作表文本。

    支持 XLSX/XLSM/XLSB/XLS 等 Excel 格式（calamine 0.3.x 对 ODS 解析不
    完整，OdsExtractor 仍走 odfpy 后端）。calamine 在 Rust 侧完成全部解析
    与单元格遍历，PyO3 边界仅一次性返回二维列表，避免 Python 层逐单元格
    调用带来的 GIL 长期占用。

    :param data: 工作簿字节内容
    :param max_rows: 单工作表最大行数（超出截断）
    :param max_cols: 单工作表最大列数（超出截断）
    :param error_label: 错误信息前缀（如 ``"XLSX"`` / ``"XLS"`` /
        ``"WPS 表格"``），用于生成可定位的 ExtractorError 消息
    :return: 各工作表文本拼接，工作表名以 ``--- 工作表: 名称 ---`` 分隔，
        行内单元格以 ``\\t`` 分隔，行间以 ``\\n`` 分隔
    :raises ExtractorError: calamine 未安装或解析失败（含加密文件）
    """
    try:
        from python_calamine import CalamineError, CalamineWorkbook
    except ImportError as exc:
        raise ExtractorError(f"python-calamine 未安装，无法提取{error_label}") from exc

    try:
        workbook = CalamineWorkbook.from_filelike(io.BytesIO(data))
    except (CalamineError, OSError, ValueError) as exc:
        raise ExtractorError(f"{error_label} 解析失败: {exc}") from exc

    parts: list[str] = []
    for sheet_idx, sheet_name in enumerate(workbook.sheet_names):
        sheet = workbook.get_sheet_by_index(sheet_idx)
        # calamine 0.3.x 的 iter_rows() 在空 sheet 上会 panic，改用 to_python()
        rows = sheet.to_python()
        sheet_texts: list[str] = []
        for row_count, row in enumerate(rows, 1):
            if row_count > max_rows:
                logger.debug("工作表 %s 行数超过上限 %d，截断", sheet_name, max_rows)
                break
            cell_texts: list[str] = []
            for col_idx, cell in enumerate(row):
                if col_idx >= max_cols:
                    break
                if cell is None:
                    continue
                cell_str = str(cell).strip()
                if cell_str:
                    cell_texts.append(cell_str)
            if cell_texts:
                sheet_texts.append("\t".join(cell_texts))
        if sheet_texts:
            parts.append(f"--- 工作表: {sheet_name} ---")
            parts.extend(sheet_texts)

    return "\n".join(parts)


class XlsxExtractor(Extractor):
    """XLSX 电子表格文本提取器。

    iter-92 起切换到 calamine (Rust + PyO3) 后端，从 T4 慢速降至 T2 快速。
    """

    def __init__(self, max_rows: int = _MAX_ROWS, max_cols: int = _MAX_COLS) -> None:
        self._max_rows = max_rows
        self._max_cols = max_cols

    @property
    @override
    def supported_extensions(self) -> tuple[str, ...]:
        """返回 XLSX 提取器支持的扩展名。"""
        return ("xlsx", "xlsm")

    @property
    @override
    def speed_tier(self) -> SpeedTier:
        """calamine (Rust + PyO3) 释放 GIL，T2 快速。"""
        return SpeedTier.FAST

    @override
    @property
    def display_name(self) -> str:
        """返回提取器的中文显示名称。"""
        return "Excel（XLSX）"

    @override
    def extract(self, path: Path) -> str:
        """提取 XLSX 工作簿所有工作表的单元格文本。"""
        try:
            data = path.read_bytes()
        except OSError as exc:
            raise ExtractorError(f"文件读取失败: {path}: {exc}") from exc
        return self.extract_from_bytes(data)

    @override
    def extract_from_bytes(self, data: bytes) -> str:
        """从内存字节提取 XLSX 工作簿文本。"""
        return _extract_calamine_workbook(
            data,
            max_rows=self._max_rows,
            max_cols=self._max_cols,
            error_label="XLSX",
        )


class OdsExtractor(Extractor):
    """ODS 电子表格文本提取器（OpenDocument Spreadsheet）。

    使用 odfpy 解析 ODS 表格。calamine 0.3.x 对 odfpy 生成的标准 ODS 单元格
    解析不完整（0.4+ 已修复但要求 Python 3.9+，fuscan 仍支持 Python 3.8），
    故 ODS 暂保留 odfpy 实现，speed_tier 维持 T4 慢速。
    """

    @property
    @override
    def supported_extensions(self) -> tuple[str, ...]:
        """返回 ODS 提取器支持的扩展名。"""
        return ("ods",)

    @property
    @override
    def speed_tier(self) -> SpeedTier:
        """ODS XML 解析 + TableRow/Cell 遍历为 T4 慢速。"""
        return SpeedTier.SLOW

    @override
    @property
    def display_name(self) -> str:
        """返回提取器的中文显示名称。"""
        return "ODS 表格"

    @override
    def extract(self, path: Path) -> str:
        """提取 ODS 表格所有行的单元格文本。"""
        try:
            data = path.read_bytes()
        except OSError as exc:
            raise ExtractorError(f"文件读取失败: {path}: {exc}") from exc
        return self.extract_from_bytes(data)

    @override
    def extract_from_bytes(self, data: bytes) -> str:
        """从内存字节提取 ODS 表格文本。"""
        try:
            from odf.opendocument import load
            from odf.table import TableCell, TableRow
        except ImportError as exc:
            raise ExtractorError("odfpy 未安装，无法提取 ODS") from exc

        try:
            doc = load(io.BytesIO(data))
        except Exception as exc:
            raise ExtractorError(f"ODS 解析失败: {exc}") from exc

        parts: list[str] = []
        for row in doc.getElementsByType(TableRow):
            row_texts = []
            for cell in row.getElementsByType(TableCell):
                text = self._extract_cell_text(cell)
                if text:
                    row_texts.append(text)
            if row_texts:
                parts.append("\t".join(row_texts))

        return "\n".join(parts)

    def _extract_cell_text(self, cell: object) -> str:
        """提取单元格内所有文本节点。"""
        try:
            return str(cell).strip()
        except Exception:
            return ""
