# app.py
import streamlit as st
import openai
import os
import tempfile
import requests

# 設定頁面標題
st.set_page_config(page_title="音頻轉字幕工具", layout="centered")

# 設定 OpenAI API 金鑰
openai.api_key = st.secrets["OPENAI_API_KEY"]

def create_txt(transcription):
    """將轉錄結果轉換為 TXT 格式"""
    return transcription['text']

def main():
    st.title("音頻轉字幕工具")
    st.write("上傳 M4A 檔案，自動轉換為 TXT 字幕檔")

    uploaded_file = st.file_uploader("選擇音頻檔案", type=['m4a'])

    if uploaded_file is not None:
        with st.spinner('處理中...'):
            # 創建臨時檔案
            with tempfile.NamedTemporaryFile(delete=False, suffix='.m4a') as tmp_file:
                tmp_file.write(uploaded_file.getvalue())
                tmp_file_path = tmp_file.name

            try:
                # 使用 HTTP 請求調用 OpenAI Whisper API 進行轉錄
                with open(tmp_file_path, 'rb') as audio_file:
                    response = requests.post(
                        "https://api.openai.com/v1/audio/transcriptions",
                        headers={
                            "Authorization": f"Bearer {openai.api_key}"
                        },
                        files={
                            "file": audio_file
                        },
                        data={
                            "model": "whisper-1"
                        }
                    )
                    response.raise_for_status()
                    transcript = response.json()

                # 轉換為 TXT 格式
                txt_content = create_txt(transcript)

                # 提供下載按鈕
                st.download_button(
                    label="下載 TXT 檔案",
                    data=txt_content.encode('utf-8'),
                    file_name=f"{uploaded_file.name.replace('.m4a', '.txt')}",
                    mime="text/plain"
                )

                # 顯示轉換後的文字
                st.text_area("轉換結果預覽", txt_content, height=300)

            except Exception as e:
                st.error(f"轉換過程發生錯誤: {str(e)}")

            finally:
                # 刪除臨時檔案
                os.unlink(tmp_file_path)

if __name__ == "__main__":
    main()