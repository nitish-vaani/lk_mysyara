import subprocess
import psutil

active_processes = {}

def is_worker_running(room_id):
    for proc in psutil.process_iter(['pid', 'cmdline']):
        if proc.info['cmdline'] and "redis_worker.py" in proc.info['cmdline']:
            if room_id in proc.info['cmdline']:
                return True
    return False

def start_worker(room_id):
    if not is_worker_running(room_id):
        print(f"Starting worker for {room_id}")
        subprocess.Popen(["python3", "redis_worker.py", room_id])
    else:
        print(f"Worker for {room_id} is already running.")

def disconnect_worker(room_id):
    for proc in psutil.process_iter(['pid', 'cmdline']):
        try:
            if proc.info['cmdline'] and "redis_worker.py" in proc.info['cmdline']:
                if room_id in proc.info['cmdline']:
                    print(f"Terminating worker for {room_id} (PID {proc.pid})")
                    proc.terminate()  # or proc.kill() if terminate is not reliable
                    proc.wait(timeout=5)
                    return True
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass
    print(f"No running worker found for {room_id}")
    return False
