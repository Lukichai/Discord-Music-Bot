import discord
from discord.ext import commands
from yt_dlp import YoutubeDL
import asyncio
import os
from dotenv import load_dotenv
from discord.ui import View, Button

load_dotenv()
TOKEN = os.getenv("DISCORD_BOT_TOKEN")

intents = discord.Intents.default()
intents.message_content = True

# Use `commands.Bot` for hybrid commands (supports both prefix and slash commands)
bot = commands.Bot(command_prefix="/", intents=intents, help_command=None)  # Disable default help command

ytdl_format_options = {
    'format': 'bestaudio/best',
    'outtmpl': 'downloads/%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0'
}

ffmpeg_options = {
    'options': '-vn -loglevel quiet'
}

ytdl = YoutubeDL(ytdl_format_options)
queues = {}

class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)
        self.data = data
        self.title = data.get('title')

    @classmethod
    async def from_url(cls, url, *, loop=None, stream=False):
        loop = loop or asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=not stream))

        if 'entries' in data:
            data = data['entries'][0]

        filename = data['url'] if stream else ytdl.prepare_filename(data)
        return cls(discord.FFmpegPCMAudio(filename, **ffmpeg_options), data=data)

async def play_next(ctx):
    server_id = ctx.guild.id
    try:
        if queues[server_id]:
            next_song_url = queues[server_id].pop(0)
            print(f"Playing next song: {next_song_url}")
            player = await YTDLSource.from_url(next_song_url, loop=bot.loop, stream=False)
            
            if ctx.voice_client:
                ctx.voice_client.play(player, after=lambda e: asyncio.run_coroutine_threadsafe(play_next(ctx), bot.loop))
                await ctx.send(f"🎶 Now playing: {player.title}\n{get_queue_message(server_id)}", view=PlayerControls(ctx))
            else:
                await ctx.send("Bot disconnected. Reconnecting...")
                await join(ctx)
                await play_next(ctx)
        else:
            await ctx.voice_client.disconnect()
            await ctx.send("Queue finished. Left the voice channel.")
    except Exception as e:
        print(f"Error in play_next: {e}")
        await ctx.send(f"Error occurred: {e}")

class PlayerControls(View):
    def __init__(self, ctx):
        super().__init__(timeout=None)
        self.ctx = ctx

    @discord.ui.button(label="⏸️ Pause", style=discord.ButtonStyle.primary)
    async def pause(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.voice and interaction.guild.voice_client and interaction.guild.voice_client.is_playing():
            interaction.guild.voice_client.pause()
            await interaction.response.send_message("⏸️ Music paused.", ephemeral=True)

    @discord.ui.button(label="▶️ Resume", style=discord.ButtonStyle.success)
    async def resume(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.voice and interaction.guild.voice_client and interaction.guild.voice_client.is_paused():
            interaction.guild.voice_client.resume()
            await interaction.response.send_message("▶️ Music resumed.", ephemeral=True)

    @discord.ui.button(label="⏭️ Skip", style=discord.ButtonStyle.secondary)
    async def skip(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.guild.voice_client and interaction.guild.voice_client.is_playing():
            interaction.guild.voice_client.stop()
            await interaction.response.send_message("⏭️ Skipped!", ephemeral=True)

    @discord.ui.button(label="⏹️ Stop", style=discord.ButtonStyle.danger)
    async def stop(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild_id = interaction.guild.id
        if guild_id in queues:
            queues[guild_id].clear()
        if interaction.guild.voice_client:
            await interaction.guild.voice_client.disconnect()
        await interaction.response.send_message("🛑 Stopped and left the channel.", ephemeral=True)

def get_queue_message(server_id):
    if server_id in queues and queues[server_id]:
        queue_list = "\n".join([f"{i+1}. {url}" for i, url in enumerate(queues[server_id])])
        return f"Current Queue:\n{queue_list}"
    return "The queue is empty!"

# Slash Commands
@bot.hybrid_command(name="join", description="Join the voice channel you're in")
async def join(ctx):
    if ctx.author.voice:
        await ctx.author.voice.channel.connect()
        await ctx.send("Joined the voice channel!")
    else:
        await ctx.send("You're not in a voice channel!")

@bot.hybrid_command(name="play", description="Play a song from a URL or add it to the queue")
async def play(ctx, *, url: str):
    server_id = ctx.guild.id

    if server_id not in queues:
        queues[server_id] = []

    if not ctx.voice_client:
        if ctx.author.voice:
            await ctx.author.voice.channel.connect()
        else:
            await ctx.send("You're not in a voice channel!")
            return

    if ctx.voice_client.is_playing():
        queues[server_id].append(url)
        await ctx.send(f"✅ Added to queue: {url}\n{get_queue_message(server_id)}")
    else:
        player = await YTDLSource.from_url(url, loop=bot.loop, stream=False)
        ctx.voice_client.play(player, after=lambda e: asyncio.run_coroutine_threadsafe(play_next(ctx), bot.loop))
        await ctx.send(f"🎶 Now playing: {player.title}\n{get_queue_message(server_id)}", view=PlayerControls(ctx))

@bot.hybrid_command(name="skip", description="Skip the current song")
async def skip(ctx):
    if ctx.voice_client.is_playing():
        ctx.voice_client.stop()
        await ctx.send("⏭️ Skipped the song.")
        if queues[ctx.guild.id]:
            await play_next(ctx)
    else:
        await ctx.send("❌ Nothing is playing.")

@bot.hybrid_command(name="pause", description="Pause the current song")
async def pause(ctx):
    if ctx.voice_client.is_playing():
        ctx.voice_client.pause()
        await ctx.send("⏸️ Paused the music.")

@bot.hybrid_command(name="resume", description="Resume the paused song")
async def resume(ctx):
    if ctx.voice_client.is_paused():
        ctx.voice_client.resume()
        await ctx.send("▶️ Resumed the music.")

@bot.hybrid_command(name="stop", description="Stop the music and clear the queue")
async def stop(ctx):
    server_id = ctx.guild.id
    if ctx.voice_client:
        ctx.voice_client.stop()
        if server_id in queues:
            queues[server_id].clear()
        await ctx.send("🛑 Stopped the music and cleared the queue.")

@bot.hybrid_command(name="queue", description="Show the current queue")
async def queue(ctx):
    server_id = ctx.guild.id
    if server_id in queues and queues[server_id]:
        q = '\n'.join([f"{i+1}. {url}" for i, url in enumerate(queues[server_id])])
        await ctx.send(f"📜 Current Queue:\n{q}")
    else:
        await ctx.send("📭 The queue is currently empty.")

@bot.hybrid_command(name="leave", description="Leave the voice channel and clear the queue")
async def leave(ctx):
    server_id = ctx.guild.id
    if server_id in queues:
        queues[server_id].clear()
    if ctx.voice_client:
        await ctx.voice_client.disconnect()
        await ctx.send("👋 Left the voice channel and cleared the queue.")

@bot.hybrid_command(name="help", description="Show all available commands")
async def help(ctx):
    embed = discord.Embed(title="🎵 Music Bot Commands", color=discord.Color.blue())
    embed.add_field(
        name="Available Commands:",
        value="""
        **/join** - Join your voice channel  
        **/play <url>** - Play a song or add to queue  
        **/skip** - Skip the current song  
        **/pause** - Pause the music  
        **/resume** - Resume paused music  
        **/stop** - Stop music and clear queue  
        **/queue** - Show the current queue  
        **/leave** - Leave the voice channel  
        **/help** - Show this help message  
        """,
        inline=False
    )
    await ctx.send(embed=embed)

# Sync slash commands on startup
@bot.event
async def on_ready():
    print(f"Logged in as {bot.user.name}")
    await bot.tree.sync()  # Sync slash commands globally
    print("Slash commands synced!")

bot.run(TOKEN)
