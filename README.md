# streamlit-audio-app
# 音頻轉錄工具

這是一個使用 OpenAI Whisper API 的音頻轉錄工具，可以將音頻文件轉換為帶時間戳記的文字。

## 功能特點

- 支持多種音頻格式（mp3, mp4, mpeg, mpga, m4a, wav, webm）
- 自動生成時間戳記
- 支持輸出為 TXT 或 DOCX 格式
- 簡潔的 Streamlit 網頁界面
- 即時預覽轉錄結果
- 支持文件下載

## 安裝需求

1. Python 3.7 或更高版本
2. 必要的 Python 套件：


bash
pip install streamlit openai python-docx


## 使用方法

1. 克隆此倉庫：

bash
git clone https://github.com/您的用戶名/您的倉庫名.git
cd 您的倉庫名
bash
pip install -r requirements.txt

4. 在瀏覽器中打開顯示的地址（通常是 http://localhost:8501）

## 使用步驟

1. 在側邊欄輸入您的 OpenAI API Key
2. 上傳音頻文件
3. 選擇輸出格式（TXT 或 DOCX）
4. 點擊"開始轉錄"按鈕
5. 等待處理完成後下載結果文件

## 輸出格式

轉錄結果將包含時間戳記，格式如下：
[00:00:00 - 00:00:05] 第一段文字
[00:00:05 - 00:00:10] 第二段文字

## 注意事項

- 需要有效的 OpenAI API Key
- 音頻文件大小限制為 25MB
- 支持的音頻格式：mp3, mp4, mpeg, mpga, m4a, wav, webm
- 轉錄過程中請保持網絡連接
- 處理時間取決於音頻文件的長度

## 隱私說明

- 音頻文件僅用於轉錄，不會永久儲存
- API Key 僅在會話期間保存在記憶體中
- 轉錄完成後臨時文件會自動刪除

## 授權

[您的授權類型] © [年份] [您的名字]

## 聯繫方式

如有問題或建議，請：
- 提交 Issue
- 發送 Pull Request
- 聯繫郵箱：[您的郵箱]
