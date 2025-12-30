import os
import asyncio
import hashlib
import json
import sys
import time
import signal
from datetime import datetime
from telethon import TelegramClient, events
from telethon.tl.types import (
    MessageMediaPhoto,
    DocumentAttributeFilename,
    DocumentAttributeVideo,
    InputMessagesFilterPhotos,
    InputMessagesFilterVideo,
    InputMessagesFilterDocument,
    InputMessagesFilterPhotoVideo
)

def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)

def load_config():
    try:
        with open('config.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        log("CRITICAL ERROR: cannot load config.json")
        sys.exit(1)

CFG = load_config()

API_ID = CFG['api_credentials']['api_id']
API_HASH = CFG['api_credentials']['api_hash']
SESSION_NAME = CFG['api_credentials']['session_name']

CHANNEL_TARGET = CFG['target']['channel_id']
DOWNLOAD_PATH = CFG['target']['download_path']

DOWNLOAD_FILTER = CFG['settings']['download_filter']
DOWNLOAD_HISTORY = CFG['settings']['download_history']
MAX_QUEUE_SIZE = CFG['settings']['max_queue_size']
SKIP_SAME_SIZE = CFG['settings'].get('skip_same_size', False)

client = TelegramClient(
    SESSION_NAME,
    API_ID,
    API_HASH,
    device_model=CFG['system_spoofing']['device_model'],
    system_version=CFG['system_spoofing']['system_version'],
    app_version=CFG['system_spoofing']['app_version']
)

download_queue = asyncio.Queue(maxsize=MAX_QUEUE_SIZE)

total_downloaded = 0
skipped_size = 0
skipped_md5 = 0
skipped_filter = 0

channel_md5 = {}
channel_sizes = {}

shutdown_event = asyncio.Event()

def load_md5_index(path):
    f = os.path.join(path, "historial_md5.json")
    if os.path.exists(f):
        try:
            with open(f, "r") as h:
                return set(json.load(h))
        except:
            return set()
    return set()

def save_md5_index(path, md5_set):
    f = os.path.join(path, "historial_md5.json")
    with open(f, "w") as h:
        json.dump(list(md5_set), h)

def load_size_index(path):
    sizes = set()
    if os.path.isdir(path):
        for name in os.listdir(path):
            p = os.path.join(path, name)
            if os.path.isfile(p):
                try:
                    sizes.add(os.path.getsize(p))
                except:
                    pass
    return sizes

def get_md5(file_path):
    h = hashlib.md5()
    try:
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                h.update(chunk)
        return h.hexdigest()
    except:
        return None

def should_download(message):
    global skipped_filter
    if not message.media:
        skipped_filter += 1
        return False

    is_video = False
    is_photo = isinstance(message.media, MessageMediaPhoto)

    if getattr(message, "document", None):
        for attr in message.document.attributes:
            if isinstance(attr, DocumentAttributeVideo):
                is_video = True
                break
        if not is_video and message.document.mime_type and message.document.mime_type.startswith("video/"):
            is_video = True

    if DOWNLOAD_FILTER == "all":
        return True
    if DOWNLOAD_FILTER == "photo" and is_photo:
        return True
    if DOWNLOAD_FILTER == "video" and is_video:
        return True

    skipped_filter += 1
    return False

def get_remote_size(message):
    if getattr(message, "document", None):
        return getattr(message.document, "size", None)
    if getattr(message, "photo", None) and getattr(message.photo, "sizes", None):
        sizes = [s.size for s in message.photo.sizes if hasattr(s, "size")]
        if sizes:
            return max(sizes)
    return None

async def heartbeat():
    while not shutdown_event.is_set():
        await asyncio.sleep(60)
        log(f"Heartbeat: worker alive | scanner alive | queue: {download_queue.qsize()} | downloaded: {total_downloaded} | skipped_size: {skipped_size} | skipped_md5: {skipped_md5} | skipped_filter: {skipped_filter}")

async def download_worker():
    global total_downloaded, skipped_size, skipped_md5

    log("Download worker started (waiting for tasks)...")

    while not shutdown_event.is_set():
        try:
            message, channel_title = await asyncio.wait_for(download_queue.get(), timeout=1)
        except asyncio.TimeoutError:
            continue

        safe = "".join([c for c in channel_title if c.isalnum() or c == " "]).strip()
        folder = os.path.join(DOWNLOAD_PATH, safe)

        md5_set = channel_md5[safe]
        size_set = channel_sizes[safe]

        original_filename = None
        if getattr(message, "document", None):
            for attr in message.document.attributes:
                if isinstance(attr, DocumentAttributeFilename):
                    original_filename = attr.file_name
                    break

        if original_filename:
            final_path = os.path.join(folder, original_filename)
        else:
            ext = ""
            if message.photo:
                ext = ".jpg"
            elif getattr(message, "document", None) and message.document.mime_type:
                ext = "." + message.document.mime_type.split("/")[-1]
            final_path = os.path.join(folder, f"{message.id}{ext}")

        remote_size = get_remote_size(message)
        if remote_size is None:
            log("Skipping file: remote size unavailable")
            download_queue.task_done()
            continue

        if SKIP_SAME_SIZE and remote_size in size_set:
            skipped_size += 1
            log(f"Skipping file: same size already exists ({remote_size} bytes)")
            download_queue.task_done()
            continue

        if os.path.exists(final_path):
            local_size = os.path.getsize(final_path)
            if local_size == remote_size:
                skipped_size += 1
                log(f"Skipping file: already exists with same size ({local_size} bytes)")
                download_queue.task_done()
                continue

        q = download_queue.qsize()
        name = original_filename if original_filename else f"Media {message.id}"
        log(f"[Queue: {q}] Downloading: {name[:40]}...")

        start = time.time()

        def progress_callback(current, total):
            if total == 0:
                return
            elapsed = time.time() - start
            if elapsed <= 0:
                elapsed = 0.001
            percent = current * 100 / total
            speed = current / elapsed
            log(f"Progress {percent:5.1f}% ({current/1048576:.2f}MB / {total/1048576:.2f}MB) {speed/1048576:.2f}MB/s")

        try:
            path = await client.download_media(message, file=final_path, progress_callback=progress_callback)

            if path:
                try:
                    final_size = os.path.getsize(path)
                    size_set.add(final_size)
                except:
                    final_size = None

                file_md5 = get_md5(path)
                if file_md5 and file_md5 in md5_set:
                    skipped_md5 += 1
                    log(f"Skipping file: MD5 duplicate detected ({os.path.basename(path)})")
                    try:
                        os.remove(path)
                    except:
                        pass
                else:
                    if file_md5:
                        md5_set.add(file_md5)
                        save_md5_index(folder, md5_set)
                    total_downloaded += 1
                    log(f"[OK] Saved. Session total: {total_downloaded}")

        except Exception as e:
            log(f"Error downloading: {e}")

        download_queue.task_done()

async def history_scanner(entity):
    log(f"Starting fast media scan: {entity.title}")

    if DOWNLOAD_FILTER == "photo":
        filters = [InputMessagesFilterPhotos]
    elif DOWNLOAD_FILTER == "video":
        filters = [InputMessagesFilterVideo, InputMessagesFilterDocument]
    else:
        filters = [InputMessagesFilterPhotoVideo, InputMessagesFilterDocument]

    count = 0

    for flt in filters:
        async for message in client.iter_messages(entity, reverse=True, filter=flt()):
            if shutdown_event.is_set():
                return
            await asyncio.sleep(0)
            if should_download(message):
                await download_queue.put((message, entity.title))
                count += 1
                if count % 20 == 0:
                    log(f"Scanner: {count} found. Current queue: {download_queue.qsize()}")

    log("Fast media scan completed.")

@client.on(events.NewMessage(chats=CHANNEL_TARGET))
async def new_message_handler(event):
    if should_download(event.message):
        channel = await event.get_chat()
        log("New file detected in real time.")
        await download_queue.put((event.message, channel.title))

async def shutdown():
    log("Shutdown signal received. Cleaning up...")
    shutdown_event.set()
    await client.disconnect()
    log("Client disconnected. Exiting.")

async def main():
    loop = asyncio.get_running_loop()
    loop.add_signal_handler(signal.SIGTERM, lambda: asyncio.create_task(shutdown()))
    loop.add_signal_handler(signal.SIGINT, lambda: asyncio.create_task(shutdown()))

    log("Starting connection...")
    await client.start()

    try:
        entity = await client.get_entity(CHANNEL_TARGET)
        log(f"Pro Monitor active for: {entity.title}")
        log("Configuration loaded from JSON")

        safe = "".join([c for c in entity.title if c.isalnum() or c == " "]).strip()
        folder = os.path.join(DOWNLOAD_PATH, safe)
        os.makedirs(folder, exist_ok=True)

        channel_md5[safe] = load_md5_index(folder)
        channel_sizes[safe] = load_size_index(folder)

        asyncio.create_task(download_worker())
        asyncio.create_task(heartbeat())

        if DOWNLOAD_HISTORY:
            asyncio.create_task(history_scanner(entity))
        else:
            log("History skip enabled (real-time only).")

        log("System idle. Press Ctrl+C to exit.")
        await shutdown_event.wait()

    except Exception as e:
        log(f"Unexpected error: {e}")

if __name__ == "__main__":
    asyncio.run(main())