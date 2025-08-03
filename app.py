# app.py
import streamlit as st
import os
from openai import OpenAI
from docx import Document
from datetime import datetime
from pydub import AudioSegment
import math
import warnings
import logging
import sys
from typing import Optional
import tempfile
import subprocess
import shutil
import io
import time

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Suppress pydub warnings
warnings.filterwarnings("ignore", category=RuntimeWarning)

# Configure ffmpeg path if needed
# AudioSegment.converter = "/usr/bin/ffmpeg"  # Uncomment if ffmpeg path is different

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

def format_time_srt(seconds):
    """將秒數轉換為 SRT 格式時間戳 (HH:MM:SS,mmm)"""
    if isinstance(seconds, str):
        seconds = float(seconds)
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    milliseconds = int((seconds % 1) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{milliseconds:03d}"

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
            
        elif format == 'srt':
            with open(output_path, 'w', encoding='utf-8') as f:
                for i, segment in enumerate(segments, 1):
                    # 轉換時間格式為 SRT 格式
                    start_time = format_time_srt(float(segment['start']) if isinstance(segment['start'], str) else segment['start'])
                    end_time = format_time_srt(float(segment['end']) if isinstance(segment['end'], str) else segment['end'])
                    
                    # SRT 格式：序號、時間軸、文字、空行
                    f.write(f"{i}\n")
                    f.write(f"{start_time} --> {end_time}\n")
                    f.write(f"{segment['text'].strip()}\n\n")
        
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

@st.cache_data
def check_ffmpeg():
    """Check if ffmpeg is available and log its version"""
    try:
        result = subprocess.run(['ffmpeg', '-version'], 
                              capture_output=True, 
                              text=True,
                              timeout=10)
        first_line = result.stdout.split('\n')[0]
        logger.info(f"FFmpeg version info: {first_line}")
        return True
    except Exception as e:
        logger.error(f"FFmpeg check failed: {str(e)}")
        return False

@st.cache_data
def convert_m4a_to_wav(input_path: str) -> Optional[str]:
    """Convert m4a to wav using ffmpeg directly"""
    try:
        output_path = input_path.rsplit('.', 1)[0] + '.wav'
        cmd = ['ffmpeg', '-i', input_path, '-acodec', 'pcm_s16le', '-ar', '44100', output_path]
        
        logger.info(f"Running FFmpeg command: {' '.join(cmd)}")
        result = subprocess.run(cmd, 
                              capture_output=True, 
                              text=True,
                              timeout=30)  # Add timeout
        
        if result.returncode == 0 and os.path.exists(output_path):
            logger.info("Conversion successful")
            return output_path
        else:
            logger.error(f"Conversion failed: {result.stderr}")
            return None
    except Exception as e:
        logger.error(f"Error in conversion: {str(e)}")
        return None

def save_audio_segment(audio: AudioSegment, temp_dir: str) -> Optional[str]:
    """Save AudioSegment to a temporary WAV file"""
    try:
        temp_path = os.path.join(temp_dir, f'temp_output_{int(time.time())}.wav')
        audio.export(temp_path, format='wav')
        return temp_path
    except Exception as e:
        logger.error(f"Error saving audio segment: {str(e)}")
        return None

def process_audio_file(file_path: str, file_ext: str) -> Optional[AudioSegment]:
    """Process audio file based on extension"""
    try:
        if file_ext == '.m4a':
            logger.info("Processing m4a file...")
            wav_path = convert_m4a_to_wav(file_path)
            if wav_path and os.path.exists(wav_path):
                return AudioSegment.from_wav(wav_path)
            raise ValueError("Failed to convert m4a to wav")
        elif file_ext == '.mp3':
            logger.info("Loading mp3 file...")
            return AudioSegment.from_mp3(file_path)
        elif file_ext == '.wav':
            logger.info("Loading wav file...")
            return AudioSegment.from_wav(file_path)
        else:
            raise ValueError(f"Unsupported file format: {file_ext}")
    except Exception as e:
        logger.error(f"Error processing audio file: {str(e)}")
        raise

def process_uploaded_file(uploaded_file) -> Optional[tuple[str, float]]:
    """Process the uploaded audio file with detailed error handling"""
    temp_dir = None
    try:
        if uploaded_file is None:
            return None
            
        # Check ffmpeg availability
        if not check_ffmpeg():
            st.error("FFmpeg is not available. Please contact support.")
            return None
            
        # Create a temporary directory
        temp_dir = tempfile.mkdtemp()
        
        # Save uploaded file to temp directory
        temp_path = os.path.join(temp_dir, uploaded_file.name)
        with open(temp_path, 'wb') as f:
            f.write(uploaded_file.getbuffer())
        
        logger.info(f"File saved to temporary path: {temp_path}")
        
        # Get file extension
        file_ext = os.path.splitext(uploaded_file.name)[1].lower()
        logger.info(f"File extension: {file_ext}")
        
        # Process audio file
        audio = process_audio_file(temp_path, file_ext)
        
        if audio is None:
            raise ValueError("Audio failed to load")
        
        # Save processed audio
        output_path = save_audio_segment(audio, temp_dir)
        if output_path is None:
            raise ValueError("Failed to save processed audio")
        
        duration = len(audio) / 1000.0  # Convert to seconds
        logger.info(f"Audio file processed successfully: {duration:.2f} seconds")
        
        return output_path, duration
            
    except Exception as e:
        logger.error(f"Error processing file: {str(e)}", exc_info=True)
        st.error(f"Error processing file: {str(e)}")
        return None
    finally:
        # Cleanup if error occurred
        if temp_dir and 'output_path' not in locals():
            shutil.rmtree(temp_dir, ignore_errors=True)

def export_audio(audio: AudioSegment) -> bytes:
    """Export audio to bytes in WAV format"""
    try:
        buffer = io.BytesIO()
        audio.export(buffer, format="wav")
        return buffer.getvalue()
    except Exception as e:
        logger.error(f"Error exporting audio: {str(e)}")
        raise

def main():
    try:
        st.title("Audio Processing App")
        logger.info("App started successfully")
        
        # 檢查環境
        logger.info(f"Python version: {sys.version}")
        logger.info(f"Current working directory: {os.getcwd()}")
        logger.info(f"Directory contents: {os.listdir('.')}")
        
        # 檢查是否設置了 API Key
        if not api_key:
            st.warning("請在側邊欄輸入 OpenAI API Key")
            return
        
        # 文件上傳
        uploaded_file = st.file_uploader("上傳音頻文件", type=['mp3', 'mp4', 'mpeg', 'mpga', 'm4a', 'wav', 'webm'])
        
        # 選擇輸出格式
        output_format = st.radio("選擇輸出格式", ["txt", "docx", "srt"])
        
        if uploaded_file and st.button("開始轉錄"):
            with st.spinner("正在處理音頻文件..."):
                # 處理上傳的文件
                result = process_uploaded_file(uploaded_file)
                
                if result is not None:
                    audio_path, duration = result
                    st.success("文件處理成功！")
                    st.info(f"音頻長度: {duration:.2f} 秒")
                    
                    # 顯示音頻播放器
                    try:
                        audio_bytes = export_audio(AudioSegment.from_file(audio_path))
                        st.audio(audio_bytes, format="audio/wav")
                    except Exception as e:
                        logger.error(f"Error playing audio: {str(e)}")
                        st.error("Unable to play audio file")
                    
                    # 處理音頻
                    output_path = process_audio(audio_path, output_format)
                    
                    if output_path and os.path.exists(output_path):
                        # 讀取生成的文件以供下載
                        with open(output_path, "rb") as f:
                            file_contents = f.read()
                        
                        # 設置正確的 MIME 類型和文件名
                        if output_format == "srt":
                            mime_type = "text/plain"
                            download_filename = os.path.splitext(os.path.basename(output_path))[0] + ".srt"
                        elif output_format == "docx":
                            mime_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                            download_filename = os.path.splitext(os.path.basename(output_path))[0] + ".docx"
                        else:  # txt
                            mime_type = "text/plain"
                            download_filename = os.path.splitext(os.path.basename(output_path))[0] + ".txt"
                        
                        # 添加下載按鈕
                        st.download_button(
                            label=f"下載 {output_format.upper()} 文件",
                            data=file_contents,
                            file_name=download_filename,
                            mime=mime_type
                        )
                        
                        # 如果是 txt 或 srt 格式，直接顯示內容和複製功能
                        if output_format in ["txt", "srt"]:
                            with open(output_path, "r", encoding="utf-8") as f:
                                content = f.read()
                                label = "轉錄結果" if output_format == "txt" else "SRT 字幕內容"
                                
                                # 顯示主要內容
                                st.text_area(label, content, height=300)
                                
                                # 添加複製功能區域
                                st.markdown("---")
                                st.markdown("### 📋 複製文字內容")
                                
                                # 簡化的複製功能
                                show_copy = st.checkbox("顯示可複製文字", key=f"show_copy_{output_format}")
                                
                                if show_copy:
                                    st.info("💡 提示: 在下方文字框中全選 (Ctrl+A/Cmd+A) 然後複製 (Ctrl+C/Cmd+C)")
                                    
                                    # 提供純文字複製框
                                    st.text_area(
                                        "選取並複製此內容",
                                        content,
                                        height=200,
                                        key=f"copyable_{output_format}",
                                        help="全選此文字框內容然後複製"
                                    )
                    else:
                        st.error("轉錄失敗，請重試")
                    
                else:
                    st.error("文件處理失敗，請重試")

    except Exception as e:
        logger.error(f"Error in main app: {str(e)}", exc_info=True)
        st.error(f"An error occurred: {str(e)}")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logger.error(f"Critical error: {str(e)}", exc_info=True)
        st.error("A critical error occurred. Please check the logs.")