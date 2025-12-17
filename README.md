# Telegram Media Downloader

A robust, asynchronous Python "Userbot" designed to download media (videos, photos, documents) from **private Telegram channels** automatically.

This tool interacts directly with the **Telegram MTProto API** using [Telethon](https://docs.telethon.dev/). It is capable of downloading content even from channels with **"Restricted Content"** (Copying/Forwarding disabled) enabled, as it intercepts the raw file stream directly.

## Key Features

* **Restricted Content Bypass:** No more coments here...
* **Smart Duplicate Detection:** Uses **MD5 Hashing** to prevent downloading the same file twice (even if renamed). I accept ideas to avoid the re-download of content.
* **Original Filenames:** Preserves the original filename of documents and videos whenever available.
* **Dual Mode:**
    * **History Scan:** Downloads all past media from the channel history.
    * **Real-Time Monitor:** Listens for new messages and downloads them instantly as they arrive.
* **Async Producer-Consumer:** Uses `asyncio` queues to scan history rapidly while downloading files in the background without blocking.
* **Stealth Mode:** Configurable device spoofing to avoid `RPCError 406 (UPDATE_APP_TO_LOGIN)` errors.

---

## 📋 Prerequisites

1.  **Python 3.8+** installed.
2.  **Telegram API Credentials:**
    * Go to [my.telegram.org](https://my.telegram.org).
    * Log in and select **API development tools**.
    * Create a new application to get your `api_id` and `api_hash`.
3.  **Channel Access:** The account you use **must already be a member** in case of a private channel to scrape.

---

## Installation

1.  **Clone the repository:**
    ```bash
    git clone [https://github.com/dperez-sct/tg-down.git](https://github.com/dperez-sct/tg-down.git)
    cd tg-down
    ```

2.  **Set up a Virtual Environment (Recommended):**
    * *Linux/Mac:*
        ```bash
        python3 -m venv venv
        source venv/bin/activate
        ```
    * *Windows:*
        ```bash
        python -m venv venv
        .\venv\Scripts\activate
        ```

3.  **Install dependencies:**
    ```bash
    pip install telethon tqdm
    ```

---

## Configuration

Create a file named `config.json` in the root directory. You can copy the structure below and fill in your details.

```json
{
    "api_credentials": {
        "api_id": 1234567,
        "api_hash": "API_HASH",
        "session_name": "session_name"
    },
    "target": {
        "channel_id": -100123456789,
        "download_path": "./downloads/"
    },
    "settings": {
        "download_filter": "all",
        "download_history": true,
        "max_queue_size": 50,
        "concurrent_workers": 1
    },
    "system_spoofing": {
        "device_model": "Desktop",
        "system_version": "Windows 11",
        "app_version": "4.10.4"
    }
}
```

### Configuration guide

|Key|Description|
|---|---|
|api_id / api_hash|Your credentials from my.telegram.org|
|channel_id|The ID of the target channel. For private channels, it usually starts with -100|
|download_filter|Options: ""all"", ""video"", ""photo""|
|download_history|true to scan old messages, false to listen for new ones only|
|system_spoofing|Do not change unless necessary. Prevents connection errors by mimicking an official client|

## Usage

Run the script:

```bash
python3 monitor.py
```

## First Run Authentication:

The terminal will prompt you for your Phone Number (international format, e.g., +123456789) and the Login Code sent to your Telegram app.

If you have 2FA enabled, it will ask for your password.

Note: This only happens once. A .session file will be created to save your login.

Running in Background (Linux/VPS): To keep the bot running after closing the terminal:

```bash
nohup python monitor.py > output.log 2>&1 &
```

But... I recommend you to use byobu or similar. At the moment tg-down don't have logging.

## Disclaimer
Terms of Service: This tool is for educational purposes and personal archiving only. Do not use it to infringe on copyright or distribute content without permission.

## Safety

The session file generated contains your account credentials. Never share it or commit it to a public repository. 

## License

Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International (CC BY-NC-SA 4.0)

This is a human-readable summary of (and not a substitute for) the license. 
To view the full legal code, visit: https://creativecommons.org/licenses/by-nc-sa/4.0/legalcode

YOU ARE FREE TO:
- Share: Copy and redistribute the material in any medium or format.
- Adapt: Remix, transform, and build upon the material.

UNDER THE FOLLOWING TERMS:

1. ATTRIBUTION (BY): You must give appropriate credit, provide a link to the license, and indicate if changes were made. You may do so in any reasonable manner, but not in any way that suggests the licensor endorses you or your use.

2. NON-COMMERCIAL (NC): You may not use the material for commercial purposes. THE SALE OF THIS SOFTWARE OR ANY DERIVATIVE WORK IS STRICTLY PROHIBITED.

3. SHARE ALIKE (SA): If you remix, transform, or build upon the material, you must distribute your contributions under the same license as the original.

4. MANDATORY NOTICE: As an additional condition of this specific distribution, users are required to notify the author dperez-sct at dperez@santaclaratech.es regarding any implementation or use of this software in other projects.

NO WARRANTIES: This software is provided "as is" without warranty of any kind. The author shall not be liable for any claim, damages, or other liability arising from the use of this software.