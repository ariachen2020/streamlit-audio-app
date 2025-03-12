# app.py
import streamlit as st
import os
from openai import OpenAI
from docx import Document
from datetime import datetime

# 添加頁面配置
st.set_page_config(page_title="音頻轉錄工具", layout="wide")

# 側邊欄添加 API Key 輸入
with st.sidebar:
    st.title("設置")
    api_key = st.text_input("輸入 OpenAI API Key", type="password")

def get_openai_client():
    """創建 OpenAI 客戶端"""
    return OpenAI(api_key=api_key)

def format_time(seconds):
    """將秒數轉換為 HH:MM:SS 格式"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"

def transcribe_audio(file_path):
    """音頻轉錄：將音頻轉換為文字，包含時間戳記"""
    try:
        client = get_openai_client()
        
        with open(file_path, "rb") as audio_file:
            response = client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                response_format="verbose_json",
                timestamp_granularities=["word", "segment"]
            )
            
            # 返回帶有時間戳記的段落
            segments = []
            for segment in response.segments:
                start_time = format_time(segment.start)
                end_time = format_time(segment.end)
                segments.append({
                    'start': start_time,
                    'end': end_time,
                    'text': segment.text
                })
            return segments
            
    except Exception as e:
        raise Exception(f"轉錄錯誤: {str(e)}")

def save_transcript(segments, output_path, format='txt'):
    """保存轉錄結果為指定格式"""
    try:
        if format == 'txt':
            with open(output_path, 'w', encoding='utf-8') as f:
                for segment in segments:
                    f.write(f"[{segment['start']} - {segment['end']}] {segment['text']}\n")
        
        elif format == 'docx':
            doc = Document()
            for segment in segments:
                doc.add_paragraph(f"[{segment['start']} - {segment['end']}] {segment['text']}")
            doc.save(output_path)
        
        return True
    except Exception as e:
        print(f"保存文件失敗: {str(e)}")
        return False

def process_audio(file_path, output_format='txt'):
    """處理音頻文件並保存為指定格式"""
    try:
        # 獲取轉錄結果
        segments = transcribe_audio(file_path)
        
        if segments:
            # 生成輸出文件名
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            base_name = os.path.splitext(os.path.basename(file_path))[0]
            output_path = f"{base_name}_{timestamp}.{output_format}"
            
            # 保存文件
            if save_transcript(segments, output_path, output_format):
                return output_path
        
        return None
        
    except Exception as e:
        st.error(f"處理失敗: {str(e)}")
        return None

def main():
    st.title("音頻轉錄工具")
    
    # 檢查是否設置了 API Key
    if not api_key:
        st.warning("請在側邊欄輸入 OpenAI API Key")
        return
    
    # 文件上傳
    uploaded_file = st.file_uploader("上傳音頻文件", type=['mp3', 'mp4', 'mpeg', 'mpga', 'm4a', 'wav', 'webm'])
    
    # 選擇輸出格式
    output_format = st.radio("選擇輸出格式", ["txt", "docx"])
    
    if uploaded_file and st.button("開始轉錄"):
        with st.spinner("正在處理音頻文件..."):
            # 保存上傳的文件
            temp_path = f"temp_{uploaded_file.name}"
            with open(temp_path, "wb") as f:
                f.write(uploaded_file.getbuffer())
            
            try:
                # 處理音頻
                output_path = process_audio(temp_path, output_format)
                
                if output_path and os.path.exists(output_path):
                    # 讀取生成的文件以供下載
                    with open(output_path, "rb") as f:
                        file_contents = f.read()
                    
                    # 添加下載按鈕
                    st.download_button(
                        label=f"下載 {output_format.upper()} 文件",
                        data=file_contents,
                        file_name=os.path.basename(output_path),
                        mime="application/octet-stream"
                    )
                    
                    # 如果是 txt 格式，直接顯示內容
                    if output_format == "txt":
                        with open(output_path, "r", encoding="utf-8") as f:
                            st.text_area("轉錄結果", f.read(), height=300)
                else:
                    st.error("轉錄失敗，請重試")
                
            except Exception as e:
                st.error(f"處理失敗: {str(e)}")
            
            finally:
                # 清理臨時文件
                if os.path.exists(temp_path):
                    os.remove(temp_path)
                if 'output_path' in locals() and output_path and os.path.exists(output_path):
                    os.remove(output_path)

if __name__ == "__main__":
    main()