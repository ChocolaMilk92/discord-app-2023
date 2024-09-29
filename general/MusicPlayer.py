import discord
import wavelink
import logging
import math
import os
import asyncio
from discord import app_commands, Interaction
from discord.ext import commands
from discord.ui import Select, View
from discord import app_commands, Interaction
from typing import cast, Optional, List
from tinytag import TinyTag
from general.VoiceChannelFallbackConfig import *
from errorhandling.ErrorHandling import *

track_list = {}
selectlist = []
current_track_index = {}
loading_prev = {}

tracks_per_page_limit = 15  # Should not exceed 20 (Theocratically it should be able to exceed 23, but we limited it to 20 just in case.)
# or it will raise HTTPException: 400 Bad Request (error code: 50035): Invalid Form Body In data.embeds.0.fields.1.value: Must be 1024 or fewer in length.


# Page select for track queue
class MySelect(Select):
    def __init__(self):
        global selectlist
        global tracks_per_page
        global current_track_index
        global track_queue
        global repeat_one
        global repeat_all
        
        options = selectlist
        super().__init__(placeholder="Page", min_values=1, max_values=1, options=options)

    # Callback for the page select dropdown
    async def callback(self, interaction):
        global selectlist
        guild_id = interaction.guild.id
        view = None
        page = int(self.values[0])
        player: wavelink.Player
        player = cast(wavelink.Player, interaction.guild.voice_client)
        queue_embed = discord.Embed(title="Queue:", color=interaction.user.colour)
        if player is None:
            return await interaction.response.send_message(embed=AuthorNotInVoiceError(interaction, interaction.user).return_embed())
        if player.current is None and player.queue.is_empty:
            queue_embed.add_field(name="", value="There are no tracks in the queue", inline=False)
        if player.current is None:
            queue_embed.add_field(name=f"Now Playing :notes: :", value=f"There are no tracks playing now", inline=False)
        else:
            # Refreshing page
            # 1st page
            total_page = math.ceil(float((len(track_list[guild_id]) - current_track_index[guild_id]) / tracks_per_page_limit))
            start = 1 + current_track_index[guild_id]
            if len(track_list[guild_id]) - current_track_index[guild_id] - 1 > tracks_per_page_limit:
                end = 1 + current_track_index[guild_id] + tracks_per_page_limit
            else:
                end = len(track_list[guild_id])
            selectlist = []
            if start == end:
                selectlist.append(discord.SelectOption(label=f"1", value=f"1", description=f"{start}"))
            else:
                selectlist.append(discord.SelectOption(label=f"1", value=f"1", description=f"{start} - {end}"))
            if len(track_list[guild_id]) - current_track_index[guild_id] > tracks_per_page_limit:
                for i in range(2, total_page + 1):
                    # 2nd page and so on
                    start = 1 + end
                    end = start + tracks_per_page_limit
                    if start >= len(track_list[guild_id]) + 1:
                        break
                    elif end >= len(track_list[guild_id]):
                        if start > len(track_list[guild_id]) - 1:
                            selectlist.append(discord.SelectOption(label=f"{i}", value=f"{i}", description=f"{len(track_list[guild_id])}"))
                        else:
                            selectlist.append(discord.SelectOption(label=f"{i}", value=f"{i}", description=f"{start} - {len(track_list[guild_id])}"))
                    else:
                        selectlist.append(discord.SelectOption(label=f"{i}", value=f"{i}", description=f"{start} - {end}"))
            # Custom audio check
            custom_audio = track_list[guild_id][current_track_index[guild_id]][1]
            # Current track index and title, with index starts from 1
            if custom_audio is None:
                queue_embed.add_field(name=f"Now Playing :notes: ({1 + current_track_index[guild_id]}/{len(track_list[guild_id])}) :", value=f"> **#{1 + current_track_index[guild_id]}** - {player.current.title}", inline=False)
            else:
                queue_embed.add_field(name=f"Now Playing :notes: ({1 + current_track_index[guild_id]}/{len(track_list[guild_id])}) :", value=f"> **#{1 + current_track_index[guild_id]}** - {custom_audio["title"]}", inline=False)
            queue_embed.add_field(name="Upcoming Tracks:", value="", inline=False)
            if player.queue.is_empty and player.autoplay == wavelink.AutoPlayMode.enabled:
                # Empty queue, with autoplay enabled
                queue_embed.add_field(name="", value="Will be fetched from web after the current track is finished", inline=False)
            elif player.queue.is_empty:
                # Empty queue
                queue_embed.add_field(name="", value="There are no upcoming tracks will be played", inline=False)
            else:
                pass
            # Retrieving pages
            if len(track_list[guild_id]) - current_track_index[guild_id] - 1 > tracks_per_page_limit: 
                end = 1 + current_track_index[guild_id] + tracks_per_page_limit
            else:
                end = len(track_list[guild_id])
            if page < 2:
                start = 1 + current_track_index[guild_id] + tracks_per_page_limit * (page - 1)
            else:
                start = current_track_index[guild_id] + (page - 1) + tracks_per_page_limit * (page - 1)
            end = current_track_index[guild_id] + page + tracks_per_page_limit * (page)
            # Upcoming track index and title, with index starts from 2 
            for index, upcoming_tracks in enumerate(track_list[guild_id][start:end]):
                custom_audio = upcoming_tracks[1]
                if page < 2 and custom_audio is None:
                    # Page < 2, not custom audio
                    queue_embed.add_field(name="", value=f"> **#{2 + current_track_index[guild_id] + index}** - {upcoming_tracks[0].title}", inline=False)
                elif page < 2:
                    # Page < 2, custom audio
                    queue_embed.add_field(name="", value=f"> **#{2 + current_track_index[guild_id] + index}** - {custom_audio["title"]}", inline=False)
                elif custom_audio is None:
                    # Page >= 2, not custom audio
                    queue_embed.add_field(name="", value=f"> **#{page + current_track_index[guild_id] + index + (page - 1) * tracks_per_page_limit}** - {upcoming_tracks[0].title}", inline=False)
                else:
                    # Page >= 2, custom audio
                    queue_embed.add_field(name="", value=f"> **#{page + current_track_index[guild_id] + index + (page - 1) * tracks_per_page_limit}** - {custom_audio["title"]}", inline=False)
            view = DropdownView()
        if player.queue.mode == wavelink.QueueMode.loop or player.queue.mode == wavelink.QueueMode.loop_all or player.autoplay == wavelink.AutoPlayMode.enabled:
            # Creates an blank field
            queue_embed.add_field(name='\u200b', value="", inline=False)
        if player.queue.mode == wavelink.QueueMode.loop:
            queue_embed.add_field(name='''"Repeat one" has been enabled.''', value="", inline=False)
        if player.queue.mode == wavelink.QueueMode.loop_all:
            queue_embed.add_field(name='''"Repeat all" has been enabled.''', value="", inline=False)
        if player.autoplay == wavelink.AutoPlayMode.enabled:
            queue_embed.add_field(name='''"Autoplay mode" has been enabled.''', value="", inline=False)
        if view is None:
            await interaction.response.edit_message(embed=queue_embed)
        else:
            await interaction.response.edit_message(embed=queue_embed, view=view)

class DropdownView(View):
    def __init__(self):
        super().__init__()
        self.add_item(MySelect())

# ----------<Music Player>----------

class MusicPlayer(commands.Cog):
    def __init__(self, bot) -> None:
        global loading_prev
        self.bot = bot
    discord.utils.setup_logging(level=logging.INFO)

    # Connect to lavalink node
    @commands.Cog.listener()
    async def on_ready(self) -> None:
        global ftp
        nodes = [wavelink.Node(uri="http://linux20240907.eastus.cloudapp.azure.com:2333", password="youshallnotpass")]
        # cache_capacity is EXPERIMENTAL. Turn it off by passing None
        await wavelink.Pool.connect(nodes=nodes, client=self.bot, cache_capacity=100)

    @commands.Cog.listener()
    async def on_wavelink_node_ready(self, payload: wavelink.NodeReadyEventPayload) -> None:
        logging.info("Wavelink Node connected: %r | Resumed: %s", payload.node, payload.resumed)

    @commands.Cog.listener()
    async def on_wavelink_track_start(self, payload: wavelink.TrackStartEventPayload) -> None:
        global track_list
        global current_track_index
        guild_id = payload.player.guild.id
        player: wavelink.Player | None = payload.player
        if not player:
            # Handle edge cases...
            return

        original: wavelink.Playable | None = payload.original
        track: wavelink.Playable = payload.track

        embed: discord.Embed = discord.Embed(title="Now Playing")
        custom_audio = None
        try:
            custom_audio = track_list[guild_id][current_track_index[guild_id]][1]
        except IndexError as e:
            if original and original.recommended:
                track_list[guild_id].append([payload.track, None])
            else:
                raise e
        if custom_audio is None:
            embed.description = f"**{track.title}** by **{track.author}**"
            if track.artwork:
                embed.set_image(url=track.artwork)
            if track.album.name:
                embed.add_field(name="Album", value=track.album.name)

        else:
            embed.description = f"**{custom_audio["title"]}** by **{custom_audio["artist"]}**"
            if custom_audio["artwork"]:
                embed.set_image(url=custom_audio["artwork"])
            if custom_audio["album"]:
                embed.add_field(name="Album", value=custom_audio["album"])

        if original and original.recommended:
            embed.description += f"\n\nThis track was recommended via **{track.source}**"

        if track.album.name:
            embed.add_field(name="Album", value=track.album.name)
        
        await player.channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_wavelink_track_end(self, payload: wavelink.TrackEndEventPayload):
        global current_track_index
        global loading_prev
        player: wavelink.Player | None = payload.player
        if not player:
            # Handle edge cases...
            return
        guild_id = player.guild.id
        if guild_id in track_list and guild_id in current_track_index:
            if current_track_index[guild_id] >= len(track_list[guild_id]) - 1 and player.queue.mode == wavelink.QueueMode.loop_all and not loading_prev[guild_id]:
                current_track_index[guild_id] = 0
            elif payload.track != None and not loading_prev[guild_id] and player.queue.mode != wavelink.QueueMode.loop:
                current_track_index[guild_id] += 1
        else:
            # Stop the player
            return

    # Discord Autocomplete for Web search, rewrited for discord.py and wavelink discord
    async def web_serach_autocomplete(self,
        interaction: Interaction,
        query: str
    ) -> List[app_commands.Choice[str]]:
        if interaction.namespace.source == "web":
            result_list = []
            if not query.startswith("https://"):
                # Serach from keywords
                try:
                    max_limit = 25
                    search: wavelink.Search = await wavelink.Playable.search(query)
                    for i in range(max_limit):
                        try:
                            result_list.append(search[i].title)
                        except IndexError:
                            break
                    return [
                        app_commands.Choice(name=video, value=video)
                        for video in result_list if query.lower() in video.lower()
                    ]
                except TypeError:
                    # The author did not entered anything yet
                    # Originally it should return a defult list on Windows, not sure why it's not working on linux...
                    return []
            # Reutrn a blank list because web URL's does not required to be searched.
            return []
        else:
            # The source is not from the web
            return []


    # Custom files
    # Fetching raw data from custom file
    # The file will be temporaily stored as a cache and will be deleted afterwards
    async def fetch_custom_rawfile(self, attachment: discord.Attachment):
        try:
            supported_type = {"audio/mpeg": "mp3", "audio/x-wav": "wav", "audio/flac": "flac", "audio/mp4": "m4a"}
            if attachment.content_type in supported_type:
                extension = supported_type[attachment.content_type]
            else:
                # Unsupportted file
                return "!error%!unsupportted_file_type%"
            cache_dir = f"plugins/custom_audio/caches"
            audio_path = f"{cache_dir}/{attachment.id}.{extension}"
            # Download the attachment to the client, and deletes it afterwards.
            await attachment.save(audio_path, use_cached=False)
            audiofile = TinyTag.get(audio_path)
            audio_artist =  audiofile.artist
            audio_title = audiofile.title
            if audiofile.title is None:
                audio_title = attachment.filename.replace("_", " ")
            if audiofile.title is None and audiofile.artist is None:
                audio_title = attachment.filename.replace("_", " ")
                audio_artist =  "<Unknown artist>"
            # Delete the file to save storage space
            for file in os.listdir(cache_dir):
                if not file.endswith(".gitkeep"):
                    os.remove(os.path.join(cache_dir, file))
            # Return the track information
            return {"source": attachment, "filename": attachment.filename, "audio_url": attachment.url, "title": audio_title, "artist": audio_artist, "album": audiofile.album, "album_artist": audiofile.albumartist, "track_number": audiofile.track, "artwork": audiofile.get_image(), "filesize": audiofile.filesize, "duration": audiofile.duration, "year": audiofile.year}
        except discord.errors.HTTPException as e:
            if e.status == 413:
                return "!error%!payload_too_large%"
            else:
                raise e

    # Main Player
    # Play selected tracks
    @app_commands.command(description="Adds a selected track to the queue from web link, keywords or a local file")
    @app_commands.describe(source="Source to play the track on")
    @app_commands.describe(query="Link or keywords of the track you want to play.")
    @app_commands.describe(attachment="The track to be played.")
    @app_commands.choices(source=[app_commands.Choice(name="Web", value="web"),
                                    app_commands.Choice(name="Custom files", value="custom")
                                    ])
    @app_commands.autocomplete(query=web_serach_autocomplete)
    async def play(self, interaction: Interaction, source: app_commands.Choice[str], query: Optional[str] = None, attachment: Optional[discord.Attachment] = None):
        guild_id = interaction.guild.id
        if guild_id not in track_list:
            track_list[guild_id] = []
        if guild_id not in current_track_index:
            current_track_index[guild_id] = 0
        if guild_id not in loading_prev:
            loading_prev[guild_id] = False
        play_embed = discord.Embed(title="", color=interaction.user.colour)
        await interaction.response.defer()
        if query is None and source.value == "web":
            play_embed.add_field(name="", value=f'''Looks like you've selected searching online for the audio source, but haven't specified the track you would like to play :thinking: ...
    Just curious to know, what should I play right now, {interaction.user.mention}?''', inline=False)
            return await interaction.followup.send(embed=play_embed)
        if source.value == "custom":
            if attachment is None:
                play_embed.add_field(name="", value=f'''Looks like you've selected your custom files as the audio source, but haven't specified the track you would like to play :thinking: ...
        Just curious to know, what should I play right now, {interaction.user.mention}?''', inline=False)
                return await interaction.followup.send(embed=play_embed)
            custom_track = await self.fetch_custom_rawfile(attachment)
            # Return errors if occurs, or proceed to the next step if no errors encountered
            if custom_track == "!error%!payload_too_large%":
                play_embed.add_field(name="", value=f"Yooo {interaction.user.mention}, The file you uploaded was too large! I can't handle it apparently...", inline=False)
                return await interaction.followup.send(embed=play_embed)
            elif custom_track == "!error%!unsupportted_file_type%":
                play_embed.add_field(name="", value=f"Looks like the file you uploaded has an unsupportted format :thinking: ... Perhaps try to upload another file and gave me a chance to handle it, {interaction.user.mention}?", inline=False)
                return await interaction.followup.send(embed=play_embed)
        player: wavelink.Player
        player = cast(wavelink.Player, interaction.guild.voice_client)
        if not player:
            # Join author's voice channel
            try:
                player = await interaction.user.voice.channel.connect(cls=wavelink.Player)
                set_fallback_text_channel(interaction, interaction.channel)
            except AttributeError:
                # The author is not in a voice channel
                return await interaction.followup.send(embed=AuthorNotInVoiceError(interaction, interaction.user).return_embed())
            except discord.ClientException:
                # Something went wrong on discord or network side while joining voice channel
                play_embed.add_field(name="", value=f"I was unable to join {interaction.user.voice.channel}. Please try again.", inline=False)
                return await interaction.followup.send(embed=play_embed)
        player.autoplay = wavelink.AutoPlayMode.partial
        tracks: wavelink.Search = await wavelink.Playable.search(query or custom_track["audio_url"])
        if not tracks:
            # Could not find any tracks from author's query
            play_embed.add_field(name="", value=f"I couldn't find any tracks with that query you entered :thinking: ... Perhaps try to search something else and gave me a chance to play it, {interaction.user.mention}?", inline=False)
            return await interaction.followup.send(embed=play_embed)

        if isinstance(tracks, wavelink.Playlist):
            # tracks is a playlist...
            added: int = await player.queue.put_wait(tracks)
            # Copy the entire list for self checking, with custom_track attribute = None
            for track in tracks.tracks:
                track_list[guild_id].append([track, None])
            # Return track or playlist message
            play_embed.add_field(name="", value=f"Added the playlist **{tracks.name}** (**{added}** songs) to the queue.", inline=False)
            await interaction.followup.send(embed=play_embed)
        else:
            track: wavelink.Playable = tracks[0]
            if source.value == "custom":
                # Copy the entire list for self checking, with custom_track attribute
                track_list[guild_id].append([track, custom_track])
            else:
                # Copy the entire list for self checking, with custom_track attribute = None
                track_list[guild_id].append([track, None])
            await player.queue.put_wait(track)
            # Return track message
            if track.title == "Unknown title":
                play_embed.add_field(name="", value=f"Added **{custom_track["title"]}** to the queue.", inline=False)
                await interaction.followup.send(embed=play_embed)
            else:
                play_embed.add_field(name="", value=f"Added **{track}** to the queue.", inline=False)
                await interaction.followup.send(embed=play_embed)

        if not player.playing:
            # Play now since we aren't playing anything...
            await player.play(player.queue.get(), volume=30)

    # Pauses the current track
    @app_commands.command(name="pause", description="Pauses the current track being played in voice channel")
    async def pause(self, interaction: Interaction):
        pause_embed = discord.Embed(title="", color=interaction.user.colour)
        player: wavelink.Player
        player = cast(wavelink.Player, interaction.guild.voice_client)
        if player is None:
            pause_embed.add_field(name="", value="No tracks were playing. I'm not even in a voice channel.", inline=False)
            return await interaction.response.send_message(embed=pause_embed)
        if player.current is None and player.queue.is_empty:
            pause_embed.add_field(name="", value="No tracks were playing in voice channel.", inline=False)
            return await interaction.response.send_message(embed=pause_embed)
        if player.paused:
            pause_embed.add_field(name="", value="The track has been already paused!", inline=False)
        else:
            await player.pause(True)
            pause_embed.add_field(name="", value="The track has been paused.", inline=False)
        await interaction.response.send_message(embed=pause_embed)

    # Resume a paused track
    @app_commands.command(name = "resume", description="Resume a paused track in voice channel")
    async def resume(self, interaction: Interaction):
        resume_embed = discord.Embed(title="", color=interaction.user.colour)
        player: wavelink.Player
        player = cast(wavelink.Player, interaction.guild.voice_client)
        if player is None:
            resume_embed.add_field(name="", value="No track has been paused before. I'm not even in a voice channel.", inline=False)
            return await interaction.response.send_message(embed=resume_embed)
        if player.current is None and player.queue.is_empty:
            resume_embed.add_field(name="", value="No tracks were paused or played before in the voice channel.", inline=False)
            return await interaction.response.send_message(embed=resume_embed)
        if not player.paused:
            resume_embed.add_field(name="", value="No track has been paused before in voice channel.", inline=False)
        else:
            await player.pause(False)
            resume_embed.add_field(name="", value="Resuming the track...", inline=False)
        await interaction.response.send_message(embed=resume_embed)

    # Plays the previous track in the list
    @app_commands.command(name="previous", description="Plays the previous track in the list")
    @app_commands.describe(amount="Number of tracks to be rollback. Leave this blank if you want to play the previous track only.")
    async def previous(self, interaction: Interaction, amount: Optional[app_commands.Range[int, 1]] = 1):
        global loading_prev
        global current_track_index
        guild_id = interaction.guild.id
        player = cast(wavelink.Player, interaction.guild.voice_client)
        prev_embed = discord.Embed(title="", color=interaction.user.colour)
        if player is None:
            prev_embed.add_field(name="", value="There is no previous track in the list. I'm not even in a voice channel.", inline=False)
            return await interaction.response.send_message(embed=prev_embed)
        if player.current is None and player.queue.is_empty:
            prev_embed.add_field(name="", value="There is no previous track in the list.", inline=False)
            return await interaction.response.send_message(embed=prev_embed)
        previous_index = current_track_index[guild_id] - amount
        loading_prev[guild_id] = True
        if player and len(player.queue.history) == 0 or (current_track_index[guild_id] == 0 and previous_index == -1):
            previous_index = 0
            prev_embed.add_field(name="", value="There is no previous track in the list.", inline=False)
            return await interaction.response.send_message(embed=prev_embed)
        elif previous_index <= -1:
            previous_index = 0
            prev_embed.add_field(name="", value="The amount of tracks you tried to rollback exceeded the total number of available tracks can be rollback in the queue. Automatically rolling back to the first track in the list...", inline=False)
        elif amount > 1:
            prev_embed.add_field(name="", value=f"Rolling back **{amount}** tracks from the list...", inline=False)
        else:
            prev_embed.add_field(name="", value="Playing previous track in the list...", inline=False)
        # Getting previous track and replaces all upcoming tracks from the queue
        player.queue.clear()
        is_loop = player.queue.mode
        if player.queue.mode == wavelink.QueueMode.loop:
            # Bypass loop mode
            player.queue.mode = wavelink.QueueMode.normal
        for track in track_list[guild_id][previous_index:]:
            await player.queue.put_wait(track[0])
        await player.play(player.queue.get())
        current_track_index[guild_id] = previous_index
        if is_loop == wavelink.QueueMode.loop:
            player.queue.mode == wavelink.QueueMode.loop
        await interaction.response.send_message(embed=prev_embed)
        await asyncio.sleep(2)
        loading_prev[guild_id] = False

    # Skipping tracks
    @app_commands.command(name="skip", description="Skips the current track being played in voice channel")
    @app_commands.describe(amount="Number of track to skip. Leave this blank if you want to skip the current track only.")
    async def skip(self, interaction: Interaction, amount: Optional[app_commands.Range[int, 1]] = 1):
        global loading_prev
        player: wavelink.Player
        player = cast(wavelink.Player, interaction.guild.voice_client)
        guild_id = interaction.guild.id
        loading_prev[guild_id] = False
        skip_embed = discord.Embed(title="", color=interaction.user.colour)
        if player is None:
            return await interaction.response.send_message(embed=AuthorNotInVoiceError(interaction, interaction.user).return_embed())
        if player.current is None and player.queue.is_empty:
            skip_embed.add_field(name="", value="There are no tracks in the queue.")
            return await interaction.response.send_message(embed=skip_embed)
        if current_track_index[guild_id] > len(track_list[guild_id]) - 1:
            # The author has been already gone through all tracks in the queue
            skip_embed.add_field(name="", value=f"<@{interaction.user.id}> You have already gone through all tracks in the queue.", inline=False)
            return await interaction.response.send_message(embed=skip_embed)
        if player.current and player.queue.is_empty and player.autoplay == wavelink.AutoPlayMode.enabled:
            # The author just skipped the final track, with autoplay enabled
            await player.skip(force=True)
            skip_embed.add_field(name="", value=f"Skipped the **final track**. Now fetching some **recommendations** from the web...", inline=False)
        elif player.current and player.queue.is_empty:
            # The author just skipped the final track
            await player.skip(force=True)
            skip_embed.add_field(name="", value=f"Skipped the **final track**. There are **no upcoming tracks** will be played.", inline=False)
        elif amount > player.queue.count:
            skip_embed.add_field(name="", value="The amount of tracks you tried to skip **exceeded** the **total number of available tracks can be skipped** in the queue. Automatically **skipping to the last track** in the queue...", inline=False)
            player.queue.clear()
            current_track_index[guild_id] = len(track_list[guild_id]) - 2
            await player.queue.put_wait(track_list[guild_id][-1][0])
            await player.play(player.queue.get())
        else:
            # Skip one or multiple tracks
            player.queue.clear()
            is_loop = player.queue.mode
            if player.queue.mode == wavelink.QueueMode.loop:
                # Bypass loop mode
                player.queue.mode = wavelink.QueueMode.normal
            for track in track_list[guild_id][amount + current_track_index[guild_id]:]:
                await player.queue.put_wait(track[0])
            current_track_index[guild_id] += amount - 1
            await player.play(player.queue.get())
            if amount > 1:
                skip_embed.add_field(name="", value=f"Skipped **{amount}** tracks in the queue", inline=False)
            else:
                skip_embed.add_field(name="", value="Skipped the **current** track in the queue", inline=False)
            if is_loop == wavelink.QueueMode.loop:
                player.queue.mode == wavelink.QueueMode.loop
        await interaction.response.send_message(embed=skip_embed)

    # Replay the current track in the queue
    @app_commands.command(name="replay", description="Replay the current track from the beginning")
    async def replay(self, interaction: Interaction):
        global current_track_index
        player = cast(wavelink.Player, interaction.guild.voice_client)
        replay_embed = discord.Embed(title="", color=interaction.user.colour)
        if player is None:
            return await interaction.response.send_message(embed=AuthorNotInVoiceError(interaction, interaction.user).return_embed())
        if player.paused or not player.playing:
            replay_embed.add_field(name="", value="No tracks were playing in voice channel.", inline=False)
            return await interaction.response.send_message(embed=replay_embed)
        await player.seek(0)   # To restart the song from the beginning, disregard this parameter or set position to 0.
        replay_embed.add_field(name="", value=f"Replaying the current track...", inline=False)
        await interaction.response.send_message(embed=replay_embed)

    # Looping the current track or all tracks in the list
    @app_commands.command(name="repeat", description="Looping the current track or all tracks in the list")
    @app_commands.describe(type="The type to repeat (Can be the current track or all tracks)")
    @app_commands.choices(type=[app_commands.Choice(name="Repeat one", value="loop"),
                                 app_commands.Choice(name="Repeat all", value="loop_all")
                                 ])
    @app_commands.choices(option=[app_commands.Choice(name="Enable", value="true"),
                                 app_commands.Choice(name="Disable", value="false")
                                 ])
    async def repeat(self, interaction: Interaction, type: app_commands.Choice[str], option: app_commands.Choice[str]):
        repeat_embed = discord.Embed(title="", color=interaction.user.colour)
        player: wavelink.player = cast(wavelink.Player, interaction.guild.voice_client)
        
        if player is None:
            repeat_embed.add_field(name="", value=f"I'm not in a voice channel!", inline=False)
            return await interaction.response.send_message(embed=repeat_embed)
        if type.value == "loop":
            # Loop
            if player.queue.mode == wavelink.QueueMode.loop and option.value == "true":
                repeat_embed.add_field(name="", value=f'''**"Repeat one"** has been already **enabled**!''', inline=False)
            elif ((player.queue.mode == wavelink.QueueMode.normal) or (player.queue.mode ==wavelink.QueueMode.loop_all)) and option.value == "false":
                repeat_embed.add_field(name="", value=f'''**"Repeat one"** has been already **disabled**!''', inline=False)
            elif ((player.queue.mode == wavelink.QueueMode.normal) or (player.queue.mode ==wavelink.QueueMode.loop_all)) and option.value == "true":
                player.queue.mode = wavelink.QueueMode.loop
                repeat_embed.add_field(name="", value=f'''**"Repeat one"** has been **enabled**.''', inline=False)
            elif player.queue.mode == wavelink.QueueMode.loop and option.value == "false":
                player.queue.mode = wavelink.QueueMode.normal
                repeat_embed.add_field(name="", value=f'''**"Repeat one"** has been **disabled**.''', inline=False)
        elif type.value == "loop_all":
            # Loop all
            if player.queue.mode == wavelink.QueueMode.loop_all and option.value == "true":
                repeat_embed.add_field(name="", value=f'''**"Repeat all"** has been already **enabled**!''', inline=False)
            elif ((player.queue.mode == wavelink.QueueMode.normal) or (player.queue.mode ==wavelink.QueueMode.loop)) and option.value == "false":
                repeat_embed.add_field(name="", value=f'''**"Repeat all"** has been already **disabled**!''', inline=False)
            elif ((player.queue.mode == wavelink.QueueMode.normal) or (player.queue.mode ==wavelink.QueueMode.loop)) and option.value == "true":
                player.queue.mode = wavelink.QueueMode.loop_all
                repeat_embed.add_field(name="", value=f'''**"Repeat all"** has been **enabled**.''', inline=False)
            elif player.queue.mode == wavelink.QueueMode.loop_all and option.value == "false":
                player.queue.mode = wavelink.QueueMode.normal
                repeat_embed.add_field(name="", value=f'''**"Repeat all"** has been **disabled**.''', inline=False)
        else:
            # Runtime error
            raise RuntimeError("An unexpected error occured while repeating tracks.")
        await interaction.response.send_message(embed=repeat_embed)

    # Enable or disable autoplay mode
    @app_commands.command(description="Toggle autoplay to automatically fetch recommendations for you")
    @app_commands.describe(mode="The option you want to choose.")
    @app_commands.choices(mode=[app_commands.Choice(name="Enable", value="enable"),
                                    app_commands.Choice(name="Disable", value="disable")
                                    ])
    async def autoplay(self, interaction: Interaction, mode: app_commands.Choice[str]):
        player: wavelink.Player
        player = cast(wavelink.Player, interaction.guild.voice_client)
        autoplay_embbed = discord.Embed(title="", color=interaction.user.color)
        if player is None:
            return await interaction.response.send_message(embed=AuthorNotInVoiceError(interaction, interaction.user).return_embed())
        if mode.value == "enable" and player.autoplay == wavelink.AutoPlayMode.enabled:
            # Autoplay mode has been already enabled
            autoplay_embbed.add_field(name="", value="Autoplay mode has been already **enabled**!")
        elif mode.value == "enable":
            # Enable Autoplay mode
            player.autoplay = wavelink.AutoPlayMode.enabled
            autoplay_embbed.add_field(name="", value="Autoplay mode has been **enabled**.")
        elif mode.value == "disable" and (player.autoplay == wavelink.AutoPlayMode.partial or player.autoplay == wavelink.AutoPlayMode.disabled):
            # Autoplay mode has been already disabled
            autoplay_embbed.add_field(name="", value="Autoplay mode has been already **disabled**!")
        elif mode.value == "disable":
            # Disable Autoplay mode
            player.autoplay = wavelink.AutoPlayMode.partial
            autoplay_embbed.add_field(name="", value="Autoplay mode has been **disabled**.")
        else:
            # Runtime error
            raise RuntimeError("An unexpected error occured while toggling Autoplay mode.")
        await interaction.response.send_message(embed=autoplay_embbed)

    # Change the volume of the music player
    @app_commands.command(name="volume", description="Change the volume of the music player")
    @app_commands.describe(value="The new volume you want me to set. Leave this blank if you want me to set it as default.")
    async def volume(self, interaction: Interaction, value: Optional[app_commands.Range[int, 0, 1000]] = 30):
        player: wavelink.player = cast(wavelink.Player, interaction.guild.voice_client)
        volume_embed = discord.Embed(title="", color=interaction.user.colour)
        if player is None:
            volume_embed.add_field(name="", value="I'm not in a voice channel!", inline=False)
        else:
            await player.set_volume(value)
            volume_embed.add_field(name="", value=f"Changed volume to **{value}%**", inline=False)
        await interaction.response.send_message(embed=volume_embed)

    # Shows the queue
    @app_commands.command(name="queue", description="Shows the queue in this server")
    async def queue(self, interaction: Interaction):
        global selectlist
        guild_id = interaction.guild.id
        view = None
        player: wavelink.Player
        player = cast(wavelink.Player, interaction.guild.voice_client)
        queue_embed = discord.Embed(title="Queue:", color=interaction.user.colour)
        if player is None:
            return await interaction.response.send_message(embed=AuthorNotInVoiceError(interaction, interaction.user).return_embed())
        if player.current is None and player.queue.is_empty:
            queue_embed.add_field(name="", value="There are no tracks in the queue", inline=False)
        if player.current is None:
            queue_embed.add_field(name=f"Now Playing :notes: :", value=f"There are no tracks playing now", inline=False)
        else:
            # Refreshing page
            # 1st page
            total_page = math.ceil(float((len(track_list[guild_id]) - current_track_index[guild_id]) / tracks_per_page_limit))
            start = 1 + current_track_index[guild_id]
            if len(track_list[guild_id]) - current_track_index[guild_id] - 1 > tracks_per_page_limit:
                end = 1 + current_track_index[guild_id] + tracks_per_page_limit
            else:
                end = len(track_list[guild_id])
            selectlist = []
            if start == end:
                selectlist.append(discord.SelectOption(label=f"1", value=f"1", description=f"{start}"))
            else:
                selectlist.append(discord.SelectOption(label=f"1", value=f"1", description=f"{start} - {end}"))
            if len(track_list[guild_id]) - current_track_index[guild_id] > tracks_per_page_limit:
                for i in range(2, total_page + 1):
                    # 2nd page and so on
                    start = 1 + end
                    end = start + tracks_per_page_limit
                    if start >= len(track_list[guild_id]) + 1:
                        break
                    elif end >= len(track_list[guild_id]):
                        if start > len(track_list[guild_id]) - 1:
                            selectlist.append(discord.SelectOption(label=f"{i}", value=f"{i}", description=f"{len(track_list[guild_id])}"))
                        else:
                            selectlist.append(discord.SelectOption(label=f"{i}", value=f"{i}", description=f"{start} - {len(track_list[guild_id])}"))
                    else:
                        selectlist.append(discord.SelectOption(label=f"{i}", value=f"{i}", description=f"{start} - {end}"))
            # Custom audio check
            custom_audio = track_list[guild_id][current_track_index[guild_id]][1]
            # Current track index and title, with index starts from 1
            if custom_audio is None:
                queue_embed.add_field(name=f"Now Playing :notes: ({1 + current_track_index[guild_id]}/{len(track_list[guild_id])}) :", value=f"> **#{1 + current_track_index[guild_id]}** - {player.current.title}", inline=False)
            else:
                queue_embed.add_field(name=f"Now Playing :notes: ({1 + current_track_index[guild_id]}/{len(track_list[guild_id])}) :", value=f"> **#{1 + current_track_index[guild_id]}** - {custom_audio["title"]}", inline=False)
            queue_embed.add_field(name="Upcoming Tracks:", value="", inline=False)
            if player.queue.is_empty and player.autoplay == wavelink.AutoPlayMode.enabled:
                # Empty queue, with autoplay enabled
                queue_embed.add_field(name="", value="Will be fetched from web after the current track is finished", inline=False)
            elif player.queue.is_empty:
                # Empty queue
                queue_embed.add_field(name="", value="There are no upcoming tracks will be played", inline=False)
            else:
                pass
            # Retrieving tracks
            if len(track_list[guild_id]) - current_track_index[guild_id] - 1 > tracks_per_page_limit: 
                end = 1 + current_track_index[guild_id] + tracks_per_page_limit
            else:
                end = len(track_list[guild_id])
            # Upcoming track index and title, with index starts from 2
            for index, upcoming_tracks in enumerate(track_list[guild_id][1 + current_track_index[guild_id]:end]):
                custom_audio = upcoming_tracks[1]
                if custom_audio is None:
                    queue_embed.add_field(name="", value=f"> **#{2 + current_track_index[guild_id] + index}** - {upcoming_tracks[0].title}", inline=False)
                else:
                    queue_embed.add_field(name="", value=f"> **#{2 + current_track_index[guild_id] + index}** - {custom_audio["title"]}", inline=False)
            view =  DropdownView()
        if player.queue.mode == wavelink.QueueMode.loop or player.queue.mode == wavelink.QueueMode.loop_all or player.autoplay == wavelink.AutoPlayMode.enabled:
            # Creates an blank field
            queue_embed.add_field(name='\u200b', value="", inline=False)
        if player.queue.mode == wavelink.QueueMode.loop:
            queue_embed.add_field(name='''"Repeat one" has been enabled.''', value="", inline=False)
        if player.queue.mode == wavelink.QueueMode.loop_all:
            queue_embed.add_field(name='''"Repeat all" has been enabled.''', value="", inline=False)
        if player.autoplay == wavelink.AutoPlayMode.enabled:
            queue_embed.add_field(name='''"Autoplay mode" has been enabled.''', value="", inline=False)
        if view is None:
            await interaction.response.send_message(embed=queue_embed)
        else:
            await interaction.response.send_message(embed=queue_embed, view=view)

    # Stops the track currently playing and clears the queue
    @app_commands.command(name="stop", description="Stops the track currently playing and reset the queue")
    async def stop(self, interaction: Interaction):
        player: wavelink.Player
        player = cast(wavelink.Player, interaction.guild.voice_client)
        guild_id = interaction.guild.id
        stop_embed = discord.Embed(title="Queue:", color=interaction.user.colour)
        if player is None:
            return await interaction.response.send_message(embed=AuthorNotInVoiceError(interaction, interaction.user).return_embed())
        if player.current is None and player.queue.is_empty:
            stop_embed.add_field(name="", value="There are no tracks in the queue.")
            return await interaction.response.send_message(embed=stop_embed)
        if track_list[guild_id] != []:
            player.queue.reset()
            player.autoplay == wavelink.AutoPlayMode.partial
            del track_list[guild_id]
            del current_track_index[guild_id]
            await player.skip()
            stop_embed.add_field(name="", value="Queue has been reset.")
        else:
            stop_embed.add_field(name="", value="There are no tracks in the queue")
        await interaction.response.send_message(embed=stop_embed)

    # Removes the last or a specified track added to the queue
    @app_commands.command(name="remove", description="Removes the last or a specified track added to the queue")
    @app_commands.describe(position="Postion of track to remove. Leave this blank if you want to remove the last track.")
    async def remove(self, interaction: Interaction, position: Optional[app_commands.Range[int, 1]] = None):
        player: wavelink.Player
        player = cast(wavelink.Player, interaction.guild.voice_client)
        guild_id = interaction.guild.id
        remove_embed = discord.Embed(title="Queue", color=interaction.user.colour)
        if player is None:
            return await interaction.response.send_message(embed=AuthorNotInVoiceError(interaction, interaction.user).return_embed())
        if player.current is None and player.queue.is_empty:
            remove_embed.add_field(name="", value="There are no tracks in the queue.")
            return await interaction.response.send_message(embed=remove_embed)
        if track_list[guild_id] != []:
            if position is None:
                position = len(track_list[guild_id])
            if position > len(track_list[guild_id]):
                remove_embed.add_field(name="", value=f"Please enter a valid position of the track you want to remove from the queue.", inline=False)
            else:
                track_list[guild_id].pop(position - 1)
                remove_embed.add_field(name="", value=f"**#{position}** has been **removed** from queue.", inline=False)
                if current_track_index[guild_id] == position - 1:
                    # Skips to next track to prevent errors as the track is not exists anymore...
                    await player.skip(force=True)
                    current_track_index[guild_id] -= 1
                elif current_track_index[guild_id] > position - 1:
                    # Adjust track index
                    current_track_index[guild_id] -= 1
                if current_track_index[guild_id] < 0:
                    current_track_index[guild_id] = 0
        else:
            remove_embed.add_field(name="", value="There are no tracks in the queue.")
        await interaction.response.send_message(embed=remove_embed)

    """
    @commands.command()
    async def nightcore(self, ctx: commands.Context) -> None:
        #Set the filter to a nightcore style.
        player: wavelink.Player = cast(wavelink.Player, ctx.voice_client)
        if not player:
            return

        filters: wavelink.Filters = player.filters
        filters.timescale.set(pitch=1.2, speed=1.2, rate=1)
        await player.set_filters(filters)

        await ctx.message.add_reaction("\u2705")
    """

    # ----------</Music Player>----------

async def setup(bot):
    await bot.add_cog(MusicPlayer(bot))