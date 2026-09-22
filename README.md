# TheHostServer — Telegram Bot Hosting Service

**Developed by Aditya**

Ye ek Telegram bot hai jo doosre logon ke Python-based Telegram bots ko host karta hai.

## Setup

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

export BOT_TOKEN="your_main_hoster_bot_token_from_botfather"
python main.py
```

## Kaam kaise karta hai

1. User `/deploy` bhejta hai
2. User `.zip` ya `.py` file upload karta hai
3. Bot automatically entry file (`main.py`/`bot.py`) detect karta hai
4. User apna bot token bhejta hai
5. Server us bot ke liye alag virtual environment banata hai, `requirements.txt` install karta hai
6. Bot ko subprocess ke roop mein start kar deta hai, `BOT_TOKEN` env var ke through token pass hota hai

## Commands

| Command | Kaam |
|---|---|
| `/start`, `/help` | Info dikhata hai |
| `/deploy` | Deploy shuru karta hai |
| `/list` | Tumhare saare deployed bots dikhata hai |
| `/stop <id>` | Ek chalte hue bot ko band karta hai |
| `/start_bot <id>` | Band bot ko phir se start karta hai |
| `/delete <id>` | Bot ko permanently delete karta hai |

## ⚠️ Security — zaroor padhna

Ye current version **subprocess-based isolation** use karta hai, jo production-grade
sandbox NAHI hai. Agar tum ise real users ke liye deploy kar rahe ho (unknown/untrusted
code upload hoga), toh in cheezon ko add karna zaroori hai:

- **Docker containers** (ya gVisor/Firecracker) — har user bot ko poori tarah isolate karne ke liye
- **CPU/RAM/network limits** per container (cgroups)
- **No network egress control** — abhi koi restriction nahi hai ki uploaded code kisi
  aur server se connect kare, ye add karna chahiye
- **Code scanning** — malicious imports (`os.system`, `subprocess`, file system access
  bahar apne sandbox se) ke liye basic static check
- Is version mein koi bhi uploaded `.py` file seedha subprocess mein run hoti hai —
  matlab agar koi malicious code upload kare, wo tumhare server pe wahi permissions
  se chal sakta hai jisse ye hoster bot chal raha hai. **Isko kabhi bhi root/admin
  user se mat chalao.**

Isliye maine ye clean, working, aur samajhne mein easy code diya hai — lekin agar
ye real strangers ke liye public service banegi, Docker-based sandboxing add karna
non-negotiable hai.
