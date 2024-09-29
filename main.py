import discord
from discord import app_commands
from discord.ext import commands
import yt_dlp
import asyncio
import random

token = "TokenHere"
client = commands.Bot(command_prefix="/", intents=discord.Intents.default())

yt_dl_opts = {'format': 'bestaudio/best'}
ytdl = yt_dlp.YoutubeDL(yt_dl_opts)
ffmpeg_options = {
    'options': '-vn',
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5'
}

queue = []
isPlaying = False


discord.Intents.message_content = True

#Syncs commands, starts bot
@client.event
async def on_ready():
    print(f"Bot logged in as {client.user}")
    try:
        synced = await client.tree.sync()
        print(f"Synced {len(synced)} command(s)")
    except Exception as err:
        print(err)
        




#Searches Youtube and returns video link
async def search_youtube(query):
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, lambda: ytdl.extract_info(f"ytsearch:{query}", download=False))
    if 'entries' in result and len(result['entries']) > 0:
        return result['entries'][0]['webpage_url']
    return None



#Play command, adds songs to queue, and calls process_playback
@client.tree.command(name="play", description="Add a song to the queue, or start a new queue :)")
@app_commands.describe(url="input")
async def play(interaction: discord.Interaction, url: str):
    voice_channel = interaction.user.voice.channel
    voice_client = discord.utils.get(client.voice_clients, guild=interaction.guild)

    try:
        # Respond immediately to acknowledge the interaction
        await interaction.response.send_message("Processing your request...", delete_after=5)
        
        # Check if the input is a URL or a search term
        if not (url.startswith('http://') or url.startswith('https://')):
            url = await search_youtube(url)
            if not url:
                message = await interaction.followup.send("No results found for the search term.")
                await asyncio.sleep(3)  # Wait for 10 seconds
                await message.delete()  # Delete the message
                return

        # Process playback
        await process_playback(interaction, url, voice_channel, voice_client)
        
    except Exception as err:
        print("Error in play command:", err)
        if not interaction.response.is_done():
            message = await interaction.followup.send("An error occurred while processing your request.")
            await asyncio.sleep(3)  # Wait for 10 seconds
            await message.delete()  # Delete the message




#Takes input to play command and uses url to play song using playSong()
async def process_playback(interaction: discord.Interaction, url: str, voice_channel, voice_client):
    global isPlaying
 # Get Song Info
    loop = asyncio.get_event_loop()
    data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=False))

    # Check if the input is a playlist or a single video
    if 'entries' in data:
        # It's a playlist, so process each video in the playlist
        for entry in data['entries']:
            audio_url = entry['url']
            title = entry.get('title', 'Unknown Title')
            uploader = entry.get('uploader', 'Unknown Uploader')
            webpage_url = entry.get('webpage_url', 'Unknown URL')
            
            # Add each video in the playlist to the queue
            queue.append({'url': audio_url, 'webpage_url': webpage_url, 'title': title, 'uploader': uploader})

        message = await interaction.followup.send(f"Added playlist to the queue!")
        await asyncio.sleep(3)  # Wait for 10 seconds
        await message.delete()  # Delete the message   
    else:
        # It's a single video
        audio_url = data['url']
        title = data.get('title', 'Unknown Title')
        uploader = data.get('uploader', 'Unknown Uploader')
        webpage_url = data.get('webpage_url', 'Unknown URL')

        # Track the initial state of the queue
        
        # Add Song to Queue
        queue.append({'url': audio_url, 'webpage_url': webpage_url, 'title': title, 'uploader': uploader})

        # Send a different message if the queue was previously empty
        if isPlaying:
            message = await interaction.followup.send(f"Added **{title}** by **{uploader}** to the queue!\nURL: {webpage_url}")
            await asyncio.sleep(3)  # Wait for 10 seconds
            await message.delete()  # Delete the message

    # Check if the bot is already connected to the voice channel
    if not voice_client:
        voice_client = await voice_channel.connect()
    elif voice_client.channel != voice_channel:
        await voice_client.move_to(voice_channel)

    if not isPlaying:
        await playSong(interaction.guild, voice_client, interaction)


#Plays songs from queue
async def playSong(guild, voice_client, interaction: discord.Interaction):
    global isPlaying
    if len(queue) > 0:
        
        isPlaying = True
        song_info = queue.pop(0)
        audio_url = song_info['url']
        title = song_info['title']
        uploader = song_info['uploader']
        webpage_url = song_info['webpage_url']
        # Play Song
        player = discord.FFmpegPCMAudio(audio_url, **ffmpeg_options, executable="C:\\ffmpeg\\ffmpeg.exe")
        voice_client.play(player)
        await interaction.followup.send(f"Playing **{title}** by **{uploader}**!\nURL: {webpage_url}")
        
        # Wait for the song to finish playing
        while voice_client.is_playing():
            await asyncio.sleep(1)

        # Recursively Call again to play next song in queue
        if len(queue) > 0:
            await playSong(interaction.guild, voice_client, interaction)
        else:
            isPlaying = False
            
        
    else:
        isPlaying = False
        print("Empty Queue")



#Displays the queue
@client.tree.command(name="queue", description="Display the current queue")
async def viewQueue(interaction: discord.Interaction):
    if len(queue) == 0:
        await interaction.response.send_message("There is currently nothing in the queue, add songs using '/play [url]'!", delete_after=3)
        return
    message = "Queue:\n"
    
    for index, song_info in enumerate(queue):
        title = song_info['title']
        uploader = song_info['uploader']
        webpage_url = song_info['webpage_url']  # Use webpage_url to display the YouTube video link
        message += f"{index + 1}. {title} by {uploader}\n"

    await interaction.response.send_message(message, delete_after=15)
    


#Clears the queue
@client.tree.command(name="clear", description="Clears the queue")
async def clearQueue(interaction: discord.Interaction):
    if len(queue) == 0:
        await interaction.response.send_message("The queue is already empty dummy, add songs using '/play [url]!", delete_after=3)
    else:
        queue.clear()
        await interaction.response.send_message("The queue has been cleared :)", delete_after=3)



@client.tree.command(name="skip")
async def skip(interaction: discord.Interaction):
    voice_client = discord.utils.get(client.voice_clients, guild=interaction.guild)
    if voice_client and voice_client.is_playing():
        voice_client.stop()
        isPlaying = False
        await interaction.response.send_message(f"Skipping", delete_after=3)
        if(len(queue) > 0):
            await playSong(interaction.guild, voice_client, interaction)
        else:
            return
    



#Pauses the song actively playing
@client.tree.command(name="pause", description="Pause the current song")
async def pause(interaction: discord.Interaction):
    voice_client = discord.utils.get(client.voice_clients, guild=interaction.guild)
    if voice_client and voice_client.is_playing():
        voice_client.pause()
        await interaction.response.send_message("Paused", delete_after=3)
    else:
        await interaction.response.send_message("No song to pause", delete_after=3)



#Resumes paused song
@client.tree.command(name="resume", description="Resume the current song")
async def resume(interaction: discord.Interaction):
    voice_client = discord.utils.get(client.voice_clients, guild=interaction.guild)
    if voice_client and voice_client.is_paused():
        voice_client.resume()
        await interaction.response.send_message("Resumed", delete_after=3)
    else:
        await interaction.response.send_message("No song to resume", delete_after=3)



#Stops the song playing, clears queue, disconnects from vc
@client.tree.command(name="stop", description="Stop playing and disconnect")
async def stop(interaction: discord.Interaction):
    voice_client = discord.utils.get(client.voice_clients, guild=interaction.guild)
    if voice_client and voice_client.is_playing():
        voice_client.stop()
        queue.clear()

        isPlaying = False
        await voice_client.disconnect()
        await interaction.response.send_message("Stopped", delete_after=3)
        
    else:
        await interaction.response.send_message("No song to stop", delete_after=3)



# Shuffle command to shuffle the queue
@client.tree.command(name="shuffle", description="Shuffle the current queue")
async def shuffleQueue(interaction: discord.Interaction):
    if len(queue) == 0:
        await interaction.response.send_message("The queue is empty dummy", delete_after=3)
    else:
        random.shuffle(queue)  # Shuffle the queue
        await interaction.response.send_message("The queue has been shuffled!", delete_after=3)
client.run(token)
