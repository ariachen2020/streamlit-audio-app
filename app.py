# app.py
import streamlit as st
import os
from openai import OpenAI
from docx import Document
from datetime import datetime
from pydub import AudioSegment
import math
import warnings

# 忽略 pydub 的警告
warnings.filterwarnings("ignore", category=SyntaxWarning)

# 設置 AudioSegment 的臨時目錄
if not os.path.exists('temp'):
    os.makedirs('temp')
AudioSegment.converter = 'ffmpeg'

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
    if isinstance(seconds, str):
        seconds = float(seconds)
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
                segments.append({
                    'start': str(segment.start),  # 轉換為字符串
                    'end': str(segment.end),      # 轉換為字符串
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

def split_audio(file_path, chunk_size_mb=20):
    """將音頻文件分割成小於25MB的片段"""
    try:
        # 確保臨時目錄存在
        temp_dir = "temp"
        if not os.path.exists(temp_dir):
            os.makedirs(temp_dir)
        
        # 載入音頻文件
        audio = AudioSegment.from_file(file_path)
        
        # 計算每個片段的持續時間（毫秒）
        duration_ms = len(audio)
        chunk_duration_ms = 5 * 60 * 1000  # 5分鐘為一個片段
        
        chunks = []
        total_chunks = math.ceil(duration_ms / chunk_duration_ms)
        
        for i in range(0, total_chunks):
            start_time = i * chunk_duration_ms
            end_time = min((i + 1) * chunk_duration_ms, duration_ms)
            
            chunk = audio[start_time:end_time]
            chunk_path = os.path.join(temp_dir, f"temp_chunk_{i}.mp3")
            
            # 使用較低的比特率來減小文件大小
            chunk.export(chunk_path, format="mp3", parameters=["-q:a", "9"])
            
            # 檢查導出的文件大小
            if os.path.getsize(chunk_path) > 25 * 1024 * 1024:
                # 如果還是太大，使用更低的比特率重新導出
                chunk.export(chunk_path, format="mp3", parameters=["-q:a", "10"])
            
            chunks.append(chunk_path)
            
        return chunks
    except Exception as e:
        st.error(f"音頻分割失敗: {str(e)}")
        st.error("請確保已安裝 ffmpeg")
        raise Exception(f"音頻分割失敗: {str(e)}")

def merge_transcripts(segments_list):
    """合併多個轉錄結果，並調整時間戳記"""
    merged_segments = []
    current_offset = 0.0
    
    for segments in segments_list:
        for segment in segments:
            # 確保時間值是浮點數
            start_time = float(segment['start']) + current_offset
            end_time = float(segment['end']) + current_offset
            
            merged_segments.append({
                'start': format_time(start_time),
                'end': format_time(end_time),
                'text': segment['text']
            })
        
        # 更新時間偏移
        if segments:
            current_offset += float(segments[-1]['end'])
    
    return merged_segments

def process_audio(file_path, output_format='txt'):
    """處理音頻文件並保存為指定格式"""
    try:
        # 確保臨時目錄存在
        if not os.path.exists('temp'):
            os.makedirs('temp')
        
        file_size = os.path.getsize(file_path) / (1024 * 1024)  # 轉換為 MB
        chunks = []
        
        try:
            if file_size > 20:  # 如果文件大於 20MB
                # 分割音頻
                st.info(f"文件大小為 {file_size:.1f}MB，正在分割處理...")
                chunks = split_audio(file_path)
                
                # 處理每個分割
                all_segments = []
                progress_bar = st.progress(0)
                
                for i, chunk_path in enumerate(chunks):
                    chunk_size = os.path.getsize(chunk_path) / (1024 * 1024)
                    st.info(f"正在處理第 {i+1}/{len(chunks)} 部分 (大小: {chunk_size:.1f}MB)...")
                    
                    segments = transcribe_audio(chunk_path)
                    all_segments.append(segments)
                    progress_bar.progress((i + 1) / len(chunks))
                
                # 合併所有轉錄結果
                merged_segments = merge_transcripts(all_segments)
            else:
                # 直接處理小文件
                merged_segments = transcribe_audio(file_path)
            
            if merged_segments:
                # 生成輸出文件名
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                base_name = os.path.splitext(os.path.basename(file_path))[0]
                output_path = os.path.join('temp', f"{base_name}_{timestamp}.{output_format}")
                
                # 保存文件
                if save_transcript(merged_segments, output_path, output_format):
                    return output_path
            
            return None
            
        finally:
            # 清理所有臨時分割文件
            for chunk_path in chunks:
                if os.path.exists(chunk_path):
                    try:
                        os.remove(chunk_path)
                    except Exception:
                        pass
                        
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