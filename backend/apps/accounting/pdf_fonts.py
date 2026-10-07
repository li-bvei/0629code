"""PDF の埋め込み字体を、実際に使っている文字だけに絞る（P6・ファイルサイズの最適化）。

PyMuPDF（MuPDF）組み込みのサブセット化を使う（追加の依存なし）。文字の内容・座標・ページ構成は変えない。
最適化の前後で各ページの文字列とページ数・ページ寸法が一致することを確かめ、違えば例外にする
（呼び出し側が業務エラーとして返す。黙って未最適化の大きな PDF に切り替えない）。
"""
import fitz


class FontSubsetError(Exception):
    pass


def _signature(doc):
    return [(round(page.rect.width, 2), round(page.rect.height, 2), page.get_text()) for page in doc]


def subset_pdf_fonts(content):
    try:
        doc = fitz.open(stream=content, filetype='pdf')
    except Exception as exc:  # noqa: BLE001
        raise FontSubsetError('PDF を開けません。') from exc
    try:
        before = _signature(doc)
        doc.subset_fonts()
        optimized = doc.tobytes(garbage=4, deflate=True)
    except Exception as exc:  # noqa: BLE001
        raise FontSubsetError('字体の最適化に失敗しました。') from exc
    finally:
        doc.close()
    try:
        check = fitz.open(stream=optimized, filetype='pdf')
        try:
            after = _signature(check)
        finally:
            check.close()
    except Exception as exc:  # noqa: BLE001
        raise FontSubsetError('最適化後の PDF を開けません。') from exc
    if after != before:
        raise FontSubsetError('最適化の前後で PDF の内容が一致しません。')
    return optimized
