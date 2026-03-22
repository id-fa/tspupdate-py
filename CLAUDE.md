# TSPUPDATE (id-fa私家版)

参照ファイルのタイムスタンプ（更新日時・作成日時）をターゲットファイルにコピーするWindows用GUIツール。

## 技術スタック
- Python 3 + tkinter (GUI)
- tkinterdnd2 (ドラッグ＆ドロップ)
- ctypes (Windows API `SetFileTime` で作成日時を設定、pywin32不要)

## ファイル構成
- `tspupdate.py` — メインアプリケーション
- `TSPUPDATE.txt` — オリジナル版の仕様経緯（2006年の2ch依頼スレ）
- `TSPUPDATE.png` — オリジナル版のスクリーンショット

## 実行
```
python tspupdate.py
```

## 依存パッケージ
```
pip install tkinterdnd2
```
