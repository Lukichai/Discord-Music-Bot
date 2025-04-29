
# Discord Music Bot 🎵

A simple Discord bot that streams music from YouTube using `discord.py` and `youtube_dl`.

## 🚀 Features

- Join and leave voice channels
- Play music via YouTube URL or search term
- Pause, resume, skip songs

## 🛠 Setup (Railway Deployment)

1. Upload this project to GitHub.
2. Go to [https://railway.app](https://railway.app) and create a new project.
3. Link your GitHub repo and deploy.
4. Go to `Variables` tab in Railway and add your bot token:
   - `DISCORD_BOT_TOKEN = your_token_here`
5. Make sure `FFmpeg` is available in your deployment if needed.

## 🧪 Run Locally

```bash
pip install -r requirements.txt
python bot.py
```

Make sure FFmpeg is installed and in your PATH.
