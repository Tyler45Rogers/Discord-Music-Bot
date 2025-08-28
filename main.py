#imports
import os, sys, requests, subprocess
from dotenv import load_dotenv
import discord
from collections import defaultdict
from discord import app_commands
from discord.ext import commands
import yt_dlp
import asyncio
import random
import spotipy
from spotipy.oauth2 import SpotifyOAuth
#I dont really understand fully but i need to change encoding for songs with wacky characters (I hate you for this panchiko)
import os
os.environ["PYTHONIOENCODING"] = "utf-8"

load_dotenv()

#Spotify Variable
sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
    client_id=os.getenv("SPOTIPY_CLIENT_ID"),
    client_secret=os.getenv("SPOTIPY_CLIENT_SECRET"),
    redirect_uri="http://localhost:8888/callback",
    scope="user-read-playback-state user-modify-playback-state",
    cache_path="C:\\botStuff\\spotify_token_cache"
))


VERSION = "1.0.2"
print("Version 1.0.1")

VERSION_URL = "https://raw.githubusercontent.com/Tyler45Rogers/Discord-Music-Bot/refs/heads/main/Version.txt"
BOT_URL = "https://raw.githubusercontent.com/Tyler45Rogers/Discord-Music-Bot/refs/heads/main/main.py"

def checkUpdate():
    try:
        latest = requests.get(VERSION_URL, timeout=10).text.strip()
        if latest != VERSION:
            print(f"New version {latest}: found. Updating")

            #Download Update
            r = requests.get(BOT_URL, timeout=10)
            with open("updatedVersion.py", "wb") as f:
                f.write(r.content)

            #Replace
            os.replace("updatedVersion.py", "main.py")

            #Restart
            subprocess.Popen([sys.executable, "main.py"])
            sys.exit()
        else:
            print("No Update")

    except Exception as e:
        print("Update Failed Womp Womp", e)
                  
checkUpdate()


token = os.getenv("DISCORD_TOKEN")
client = commands.Bot(command_prefix="/", intents=discord.Intents.default())

yt_dl_opts = {'format': 'bestaudio/best'}
ytdl = yt_dlp.YoutubeDL(yt_dl_opts)
ffmpeg_options = {
    'options': '-vn',
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5'
}

queues = defaultdict(list)  # Stores queue per guild
isPlaying = defaultdict(bool)  # Tracks playing state per guild
isLooping = defaultdict(bool) #Tracks whether looping is enabled or not per guild
current_song = defaultdict(list) #Stores current song per guild

#Play Count Variables - For Stats
#File path
playCountsPath = "C:\\botStuff\\botStats.txt"
#Dictionary with each count
playCounts = {}

#Loads play counts from file
def load_play_counts():
    global playCounts
    try:
        with open(playCountsPath, "r", encoding="utf-8", errors="replace") as f: #Opens file
            for line in f:
                if line.strip(): #Skips blank lines
                    title, count = line.strip().rsplit(",",1) #stores url and count
                    playCounts[title] = int(count) #adds to dictionary
    except FileNotFoundError:
        #Whoops, no file found
        print("Create your file silly, it wasnt found")

#Saves play counts to file
def save_playcounts():
    print(f"Saving play counts to {playCountsPath}")
    with open(playCountsPath, "w") as f: #Open file
        for title, count in playCounts.items(): #Loop thru counts
            f.write(f"{title},{count}\n") #Write to file





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
        
        #Check for spotify url's - if spotify url is given we will search youtube for the song
        if "spotify.com" in url:
            #Get Song Info (Name and Artist)
            try:
                spotifyData = sp.track(url)
                spotName = spotifyData['name']
                spotArtist = spotifyData['artists'][0]['name']
                ytSearch = f"{spotName} {spotArtist} song"

                #Search song
                url = await search_youtube(ytSearch)
                if not url:
                    message = await interaction.followup.send("No results found for the requested song, this song may only be on spotify. Try finging a direct link from youtube or soundcloud.")
                    await asyncio.sleep(3)
                    await message.delete()
                    return
            except Exception as spotify_error:
                message = await interaction.followup.send("Cant process spotify link, ruh roh")
                print("Spotify Link Brokey")
                await asyncio.sleep(3)
                await message.delete()
                return


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
    guild_id = interaction.guild.id #Find the server
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
            requester = interaction.user
            
            # Add each video in the playlist to the queue
            queues[guild_id].append({'url': audio_url, 'webpage_url': webpage_url, 'title': title, 'uploader': uploader, 'requester': requester})

        message = await interaction.followup.send(f"Added playlist to the queue!")
        await asyncio.sleep(3)  # Wait for 10 seconds
        await message.delete()  # Delete the message   
    else:
        # It's a single video
        audio_url = data['url']
        title = data.get('title', 'Unknown Title')
        uploader = data.get('uploader', 'Unknown Uploader')
        webpage_url = data.get('webpage_url', 'Unknown URL')
        requester = interaction.user

        # Track the initial state of the queue
        
        # Add Song to Queue
        queues[guild_id].append({'url': audio_url, 'webpage_url': webpage_url, 'title': title, 'uploader': uploader, 'requester': requester})

        # Send a different message if the queue was previously empty
        if isPlaying[guild_id]:
            message = await interaction.followup.send(f"Added **{title}** by **{uploader}** to the queue!\nURL: {webpage_url}")
            await asyncio.sleep(3)  # Wait for 10 seconds
            await message.delete()  # Delete the message

    # Check if the bot is already connected to the voice channel
    if not voice_client:
        voice_client = await voice_channel.connect()
    elif voice_client.channel != voice_channel:
        await voice_client.move_to(voice_channel)

    if not isPlaying[guild_id]:
        await playSong(interaction.guild, voice_client, interaction)


#Plays songs from queue
async def playSong(guild, voice_client, interaction: discord.Interaction):
    global isPlaying, isLooping, current_song
    guild_id = interaction.guild.id #Find what server is being used
    if len(queues[guild_id]) > 0:
        
        isPlaying[guild_id] = True
        song_info = queues[guild_id].pop(0)
        audio_url = song_info['url']
        title = song_info['title']
        uploader = song_info['uploader']
        webpage_url = song_info['webpage_url']
        requester = song_info['requester']

        #Store current song info
        current_song[guild_id] = ({'url': audio_url, 'webpage_url': webpage_url, 'title': title, 'uploader': uploader, 'requester': requester})

        # Play Song
        player = discord.FFmpegPCMAudio(audio_url, **ffmpeg_options, executable="C:\\botStuff\\ffmpeg.exe")
        voice_client.play(player)


        #Add to counts
        
        titleToCount = title.lower() + " by " + uploader.lower()
        if titleToCount in playCounts:  # Title exists
            count = playCounts[titleToCount]  #Get the current play count
            playCounts[titleToCount] = count + 1 # Increment the play count
        else:  # Title doesn't exist
            playCounts[titleToCount] = 1  # Initialize with a count of 1
        
        #Save Counts
        try:
            save_playcounts()
        except Exception as err:
            #Probably some encoding issue womp womp
            print("Error saving the play count, idk why")

        await interaction.followup.send(f"Playing **{title}** by **{uploader}**!\nRequested By: **{requester}**\nLooping: **{isLooping[guild_id]}**\nURL: {webpage_url}")
        
        #Check if looping is enabled, if looping add the song back to the end of the queue
        if(isLooping[guild_id]):
            queues[guild_id].append({'url': audio_url, 'webpage_url': webpage_url, 'title': title, 'uploader': uploader, 'requester': requester})

        # Wait for the song to finish playing
        while voice_client.is_playing():
            await asyncio.sleep(1)

        # Recursively Call again to play next song in queue
        if len(queues[guild_id]) > 0:
            await playSong(interaction.guild, voice_client, interaction)
        else:
            isPlaying[guild_id] = False
            
        
    else:
        isPlaying[guild_id] = False
        print("Empty Queue")



#Displays the queue
@client.tree.command(name="queue", description="Display the current queue")
async def viewQueue(interaction: discord.Interaction):
    guild_id = interaction.guild.id
    if len(queues[guild_id]) == 0:
        await interaction.response.send_message("There is currently nothing in the queue, add songs using '/play [url]'!", delete_after=3)
        return
    message = "Queue:\n"
    
    for index, song_info in enumerate(queues[guild_id]):
        title = song_info['title']
        uploader = song_info['uploader']
        webpage_url = song_info['webpage_url']  # Use webpage_url to display the YouTube video link
        message += f"{index + 1}. {title} by {uploader}\n"

    await interaction.response.send_message(message, delete_after=15)
    


#Clears the queue
@client.tree.command(name="clear", description="Clears the queue")
async def clearQueue(interaction: discord.Interaction):
    guild_id = interaction.guild.id
    if len(queues[guild_id]) == 0:
        await interaction.response.send_message("The queue is already empty dummy, add songs using '/play [url]!", delete_after=3)
    else:
        queues[guild_id].clear()
        await interaction.response.send_message("The queue has been cleared :)", delete_after=3)


#Skips Current Song
@client.tree.command(name="skip")
async def skip(interaction: discord.Interaction):
    guild_id = interaction.guild.id
    voice_client = discord.utils.get(client.voice_clients, guild=interaction.guild)
    if voice_client and voice_client.is_playing():
        voice_client.stop()
        isPlaying[guild_id] = False
        await interaction.response.send_message(f"Skipping", delete_after=3)
        if(len(queues[guild_id]) > 0):
            await playSong(interaction.guild, voice_client, interaction)
        else:
            return
    



#Pauses the song actively playing
@client.tree.command(name="pause", description="Pause the current song")
async def pause(interaction: discord.Interaction):
    guild_id = interaction.guild.id
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
    guild_id = interaction.guild.id
    voice_client = discord.utils.get(client.voice_clients, guild=interaction.guild)
    if voice_client and voice_client.is_playing():
        voice_client.stop()
        queues[guild_id].clear()

        isPlaying[guild_id] = False
        isLooping[guild_id] = False
        await voice_client.disconnect()
        await interaction.response.send_message("Stopped, if looping was enabled it has been disabled", delete_after=3)
        
    else:
        await interaction.response.send_message("No song to stop", delete_after=3)

# Shuffle command to shuffle the queue
@client.tree.command(name="shuffle", description="Shuffle the current queue")
async def shuffleQueue(interaction: discord.Interaction):
    guild_id = interaction.guild.id
    if len(queues[guild_id]) == 0:
        await interaction.response.send_message("The queue is empty dummy", delete_after=3)
    else:
        random.shuffle(queues[guild_id])  # Shuffle the queue
        await interaction.response.send_message("The queue has been shuffled!", delete_after=3)

#Upload File With Stats of Songs
@client.tree.command(name="get_stats", description="Uploads text file of songs in name,number format")
async def getStats(interaction: discord.Interaction):
    try:
        await interaction.response.send_message("Uploading Stats File...", ephemeral=True)
        await interaction.followup.send(file=discord.File(playCountsPath), ephemeral=True)
    except FileNotFoundError:
        await interaction.response.send_message("Beezer is stupid/bot broke, file not found contact someone idk who tho", ephemeral=True)

#Loop command to loop songs
@client.tree.command(name='loop', description='Loops the queue starting form the current song')
async def loop(interaction: discord.Interaction):
    global isLooping, current_song
    guild_id = interaction.guild.id
    #Check if looping already
    if (isLooping[guild_id]):
        isLooping[guild_id] = False
        await interaction.response.send_message("Looping disabled", delete_after=3)
    else:
        isLooping[guild_id] = True
        await interaction.response.send_message("Looping enabled, all songs in the queue will loop starting from the current song", delete_after=3)

    #If a song is currently playing, add it to the queue so it is played again, only if looping was just enabled
    if(isPlaying[guild_id] and isLooping[guild_id]):
        audio_url = current_song[guild_id]['url']
        webpage_url = current_song[guild_id]['webpage_url']
        title = current_song[guild_id]['title']
        uploader = current_song[guild_id]['uploader']
        requester = current_song[guild_id]['requester']

        queues[guild_id].append({'url': audio_url, 'webpage_url': webpage_url, 'title': title, 'uploader': uploader, 'requester': requester})
#Restart Command
@client.tree.command(name="restart", description="Restart the bot")
async def restart(interaction: discord.Interaction):
    await interaction.response.send_message("Restarting bot...", delete_after=3)

    # Start a new instance of the bot
    subprocess.Popen([sys.executable, os.getenv("BOT_PATH")])

    # Exit the current instance
    await client.close()




load_play_counts()
client.run(token)



