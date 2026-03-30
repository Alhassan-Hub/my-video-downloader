from flask import Flask, render_template, request, redirect, url_for, send_file
import yt_dlp
import os
import uuid
import threading
import requests

app = Flask(__name__)
DOWNLOAD_FOLDER = 'downloads'
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

active_tasks = {}

def background_download(url, task_id):
    active_tasks[task_id] = {"url": url, "status": "Starting...", "progress": "0%"}
    file_id = task_id
    
    try:
        if "twitter.com" in url or "x.com" in url:
            active_tasks[task_id]["status"] = "Connecting to Twitter..."
            api_url = url.replace("twitter.com", "api.vxtwitter.com").replace("x.com", "api.vxtwitter.com").split("?")[0]
            response = requests.get(api_url).json()
            
            if 'media_extended' in response and len(response['media_extended']) > 0:
                direct_mp4_url = response['media_extended'][0]['url']
                active_tasks[task_id]["status"] = "Downloading"
                
                video_response = requests.get(direct_mp4_url, stream=True)
                total_size = int(video_response.headers.get('content-length', 0))
                
                downloaded = 0
                with open(f"{DOWNLOAD_FOLDER}/{file_id}.mp4", 'wb') as f:
                    for chunk in video_response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)
                            if total_size > 0:
                                percent = int((downloaded / total_size) * 100)
                                active_tasks[task_id]["progress"] = f"{percent}%"
                
                active_tasks[task_id]["status"] = "Finished"
            else:
                active_tasks[task_id]["status"] = "Failed: No video found"
                return
        else:
            active_tasks[task_id]["status"] = "Downloading"
            def my_hook(d):
                if d['status'] == 'downloading':
                    active_tasks[task_id]["progress"] = d.get('_percent_str', '...').strip()

            ydl_opts = {
                'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
                'outtmpl': f'{DOWNLOAD_FOLDER}/{file_id}.%(ext)s',
                'quiet': True,
                'no_warnings': True,
                'progress_hooks': [my_hook]
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.extract_info(url, download=True)
            active_tasks[task_id]["status"] = "Finished"
            
    except Exception as e:
        print(f"Error: {e}")
        active_tasks[task_id]["status"] = "Failed"

@app.route('/')
def home():
    files = os.listdir(DOWNLOAD_FOLDER)
    finished_videos = [f for f in files if not f.endswith('.part')]
    return render_template('index.html', videos=finished_videos, tasks=active_tasks)

@app.route('/start_download', methods=['POST'])
def start_download():
    url = request.form['video_url']
    task_id = str(uuid.uuid4())[:8]
    thread = threading.Thread(target=background_download, args=(url, task_id))
    thread.start()
    return redirect(url_for('home'))

@app.route('/download_to_safari/<filename>')
def download_to_safari(filename):
    return send_file(f"{DOWNLOAD_FOLDER}/{filename}", as_attachment=True, mimetype='video/mp4')

# --- NEW FEATURE: DELETE A SINGLE VIDEO ---
@app.route('/delete/<filename>')
def delete_file(filename):
    try:
        os.remove(os.path.join(DOWNLOAD_FOLDER, filename))
    except:
        pass
    return redirect(url_for('home'))

# --- NEW FEATURE: CLEAR ALL VIDEOS ---
@app.route('/clear_all')
def clear_all():
    files = os.listdir(DOWNLOAD_FOLDER)
    for f in files:
        if not f.endswith('.part'):
            try:
                os.remove(os.path.join(DOWNLOAD_FOLDER, f))
            except:
                pass
    # Also clear the active tasks log so the screen is completely clean
    global active_tasks
    active_tasks = {}
    return redirect(url_for('home'))

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)