# -------------------------------------------------------------------------------
# License: Creative Commons Attribution-NonCommercial-ShareAlike 4.0 (CC BY-NC-SA 4.0)
# Author: dperez-sct
#
# TERMS AND CONDITIONS:
# - COMMERCIAL USE AND SALE OF THIS SOFTWARE IS STRICTLY PROHIBITED.
# - Attribution to the original author is mandatory.
# - If you use or modify this code, you must inform the author at: dperez@santaclaratech.es
#
# For more details, visit: https://creativecommons.org/licenses/by-nc-sa/4.0/
# -------------------------------------------------------------------------------

import os
import asyncio
import hashlib
import json
import sys
from telethon import TelegramClient, events
from telethon.tl.types import MessageMediaPhoto, DocumentAttributeFilename, DocumentAttributeVideo

def load_config():
    try:
        with open('config.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print("CRITICAL ERROR: 'config.json' not found.")
        print("Please create the configuration file before running.")
        sys.exit(1)
    except json.JSONDecodeError:
        print("ERROR: 'config.json' format is invalid.")
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

def get_md5(file_path):
    hash_md5 = hashlib.md5()
    try:
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()
    except FileNotFoundError: return None

class IndexManager:
    def __init__(self, folder_path):
        self.folder_path = folder_path
        self.index_file = os.path.join(folder_path, 'history_md5.json')
        self.hashes = set()
        self.load_index()

    def load_index(self):
        if os.path.exists(self.index_file):
            try:
                with open(self.index_file, 'r') as f: self.hashes = set(json.load(f))
            except: self.hashes = set()

    def save_index(self):
        with open(self.index_file, 'w') as f: json.dump(list(self.hashes), f)

    def exists(self, md5_hash): return md5_hash in self.hashes
    def add(self, md5_hash): self.hashes.add(md5_hash); self.save_index()

def should_download(message):
    if not message.media: return False
    is_video = False
    is_photo = isinstance(message.media, MessageMediaPhoto)
    if hasattr(message, 'document') and message.document:
        for attr in message.document.attributes:
            if isinstance(attr, DocumentAttributeVideo): is_video = True; break
        if not is_video and message.document.mime_type.startswith('video/'): is_video = True

    if DOWNLOAD_FILTER == 'all': return True
    if DOWNLOAD_FILTER == 'photo' and is_photo: return True
    if DOWNLOAD_FILTER == 'video' and is_video: return True
    return False

def get_target_info(channel_title):
    safe_name = "".join([c for c in channel_title if c.isalpha() or c.isdigit() or c==' ']).strip()
    save_dir = os.path.join(DOWNLOAD_PATH, safe_name)
    os.makedirs(save_dir, exist_ok=True)
    return save_dir, IndexManager(save_dir)

async def download_worker():
    global total_downloaded
    print("Download worker started (Waiting for tasks)...")
    
    while True:
        pack = await download_queue.get()
        message, channel_title = pack
        
        save_dir, indexer = get_target_info(channel_title)
        
        original_filename = None
        if hasattr(message, 'document') and message.document:
            for attr in message.document.attributes:
                if isinstance(attr, DocumentAttributeFilename):
                    original_filename = attr.file_name; break
        
        final_path = os.path.join(save_dir, original_filename) if original_filename else save_dir
        
        if original_filename and os.path.exists(final_path):
             download_queue.task_done()
             continue

        q_size = download_queue.qsize()
        display_name = original_filename if original_filename else f"Media ID {message.id}"
        print(f"[Queue: {q_size}] Downloading: {display_name[:40]}...")

        try:
            path = await client.download_media(message, file=final_path)
            if path:
                file_md5 = get_md5(path)
                if indexer.exists(file_md5):
                    print(f"[MD5 DUPLICATE] Deleting {os.path.basename(path)}")
                    os.remove(path)
                else:
                    indexer.add(file_md5)
                    total_downloaded += 1
                    print(f"[OK] Saved. (Session total: {total_downloaded})")
        except Exception as e:
            print(f"Error downloading: {e}")

        download_queue.task_done()

async def history_scanner(entity):
    print(f"Starting history scan: {entity.title}")
    count = 0
    async for message in client.iter_messages(entity, reverse=True):
        if should_download(message):
            await download_queue.put((message, entity.title))
            count += 1
            if count % 20 == 0:
                print(f"Scanner: {count} found. Current queue: {download_queue.qsize()}")
    print("History scan completed.")

@client.on(events.NewMessage(chats=CHANNEL_TARGET))
async def new_message_handler(event):
    channel = await event.get_chat()
    if should_download(event.message):
        print("New file detected in real-time!")
        await download_queue.put((event.message, channel.title))

async def main():
    print("Connecting...")
    await client.start()
    
    try:
        entity = await client.get_entity(CHANNEL_TARGET)
        print(f"Monitor active for: {entity.title}")
        print(f"Configuration loaded from JSON")

        worker_task = asyncio.create_task(download_worker())

        if DOWNLOAD_HISTORY:
            asyncio.create_task(history_scanner(entity))
        else:
            print("History skip enabled (Real-time only).")

        print("System waiting. Press Ctrl+C to exit.")
        await client.run_until_disconnected()

    except ValueError:
        print("Error: Cannot access channel. Check ID in config.json and membership.")
    except Exception as e:
        print(f"Unexpected error: {e}")

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nExiting...")