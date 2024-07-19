import discord
import openai
import os
import ast
import math
from openai import OpenAI
from discord import app_commands, Interaction
from discord.ext import commands
from langdetect import detect, DetectorFactory
from datetime import datetime
from ErrorHandling import *

# Connects the bot to the OpenAI API
api_key=os.environ.get("OPENAI_API_KEY")
if api_key == "":
    raise Exception(
        "You didn't provide an API key. You need to provide your API key in an Authorization header using Bearer auth (i.e. Authorization: Bearer YOUR_KEY), or as the password field (with blank username) if you're accessing the API from your browser and are prompted for a username and password. You can obtain an API key from https://platform.openai.com/account/api-keys.\nPlease add your OpenAI Key to the Secrets pane.")

client = OpenAI(
    api_key=api_key,
    base_url="https://api.chatanywhere.cn/v1"
)

class ChatGPT(commands.Cog):
    def __init__(self, bot):
        global client
        self.bot = bot
        # Default values for GPT model
        self.chat_messages: dict = {}
        self.chat_history: dict = {}
        self.default_model_prompt_engine: str = "gpt-3.5-turbo-1106"
        self.default_temperature: float = 0.8
        self.default_max_tokens: int = 4000
        self.default_top_p: float = 0.90
        self.default_frequency_penalty: float = 0.50
        self.default_presence_penalty: float = 0.50
        # This will be futher edited
        self.default_instruction: str = f'''You are ChatGPT, a large language model transformer AI product by OpenAI, and you are 
        purposed with satisfying user requests and questions with very verbose and fulfilling answers beyond user expectations in writing 
        quality, even provide some alternatives based on the topic. For example, if the user asking 'is md5 a encryption method?', you should answer directly first then provide
        some reasons to support your evidence, and provide some alternative encryption method if you think md5 is not suitable for it since the user may looking for
        them. When a destination medium is not specified, assume that the user would want six typewritten pages of composition about their subject of interest. Follow
        the users instructions carefully to extract their desires and wishes in order to format and plan the best style of output, no need to summarize your content unless
        other specified by user. For example, when output formatted in forum markdown, html, LaTeX formulas, or other output format or structure is desired.'''

    # ----------<ChatGPT>----------

    # Startup
    @commands.Cog.listener()
    async def on_ready(self):
        for guild in self.bot.guilds:
            guild_id = int(guild.id)
            self.chat_messages[guild_id] = []
            self.chat_history[guild_id] = []

    def reset_gpt(self, guild_id=None, reset_all=False):
        if reset_all and guild_id is None:
            for guild in self.bot.guilds:
                guild_id = int(guild.id)
                self.chat_history[guild_id] = []
                self.chat_messages[guild_id] = []
        else:
            self.chat_history[guild_id] = []
            self.chat_messages[guild_id] = []
        return True

    # Clear chat history in ChatGPT
    @app_commands.command(name="resetgpt", description="Clear chat history in ChatGPT")
    @app_commands.describe(type="Reset option")
    @app_commands.choices(type=[app_commands.Choice(name="Reset for the current server", value="reset_current"),
                                 app_commands.Choice(name="Reset for all servers", value="reset_all")
                                 ])
    async def resetgpt(self, interaction: Interaction, type: app_commands.Choice[str]):
        guild_id = interaction.guild.id
        if not await self.bot.is_owner(interaction.user):
            return await interaction.response.send_message(NotBotOwnerError())
        if type.value == "reset_current":
            if self.reset_gpt(guild_id=guild_id, reset_all=False):
                return await interaction.response.send_message("Chat history has been cleared.", ephemeral=True, delete_after=1)
        else:   # reset_all
            if self.reset_gpt(None, reset_all=True): 
                return await interaction.response.send_message("Chat history has been cleared for all servers.", ephemeral=True, delete_after=1)

    # Chat with ChatGPT
    @app_commands.command(name="chatgpt", description="Chat with ChatGPT")
    @app_commands.describe(prompt="Anything you would like to ask")
    async def chatgpt(self, interaction: Interaction, prompt: str):
        guild_id = interaction.guild.id
        await interaction.response.defer()
        # Main ChatGPT function
        try:
            if len(self.chat_history[guild_id]) > 15:
                self.reset_gpt(guild_id=guild_id, reset_all=False)
            self.chat_messages[guild_id].append({"role": "system", "content": self.default_instruction})
            self.chat_messages[guild_id].append({"role": "user", "content": prompt})
            response = client.chat.completions.create(
                model=self.default_model_prompt_engine,
                messages=self.chat_messages[guild_id],
                temperature=self.default_temperature,
                max_tokens=self.default_max_tokens,
                top_p=self.default_top_p,
                frequency_penalty=self.default_frequency_penalty,
                presence_penalty=self.default_presence_penalty)
            # Retriving the response from the GPT model
            # Starting from version 1.0.0, response objects are in pydantic models and no longer conform to the dictionary shape.
            gpt_response = response.choices[0].message.content
            self.chat_messages[guild_id].append({"role": "assistant", "content": gpt_response})
            # Adding the response to the chat history. Chat history can be store a maximum of the most recent 15 conversations.
            self.chat_history[guild_id].append({"role": "assistant", "content": gpt_response})
            # Returning the response to the author
            quote = f"> <@{interaction.user.id}>: **{prompt}**"
            final_response = f"{quote}\n{discord.utils.escape_markdown(' ')}\n{gpt_response}"
            # Since Discord has a maximum limit of 2000 charaters for each single message, the response needs to be checked in advance and decide wherether it needs to trucate into mutiple messages or not
            over_max_limit_times = math.trunc(len(final_response) / 2000)
            if over_max_limit_times >= 1:
                # The response is too long (> 2000 charaters maximum limit), so we need to split it into multiple messages
                min_limit = 0
                max_limit = 2000
                for i in range(over_max_limit_times + 1):
                    offset = 0
                    if i == over_max_limit_times:
                        # Return the rest of the charaters to the author
                        await interaction.followup.send(final_response[min_limit:])
                    else:
                        # Return 2000 characters in once for the n(th) time, trucated by complete words
                        DetectorFactory.seed = 0
                        if detect(final_response) != "ko" or detect(final_response) != "ja" or detect(
                                final_response) != "zh-tw" or detect(final_response) != "zh-cn" or detect(
                            final_response) != "th":
                            while True:
                                if final_response[max_limit - offset] != " ":
                                    offset += 1
                                else:
                                    break
                        await interaction.followup.send(final_response[min_limit:max_limit - offset])
                        min_limit += 2000 - offset
                        max_limit += 2000 - offset
            else:
                # The response does not need to be splitted
                # Return the response to the author
                await interaction.followup.send(final_response)
        # End of regular ChatGPT function and the normal procedure
        except openai.APITimeoutError as e:
            error_embed = discord.Embed(title="<a:cross_custom:1219601144905601146>  OpenAI API request timed out", timestamp=datetime.now(), color=discord.Colour.red())
            error_message = ast.literal_eval(str(e).split(f"{e.status_code} - ")[1])["error"]["message"]
            error_embed.add_field(name='\u200b', value=f"OpenAI API request timed out. This may due to the GPT model currently unavailable or overloaded, or the OpenAI service has been blocked from your current network. Please try again later or connect to another network to see if the error could be resolved.\nError message: {error_message}", inline=False)
            error_embed.add_field(name='\u200b', value=f"", inline=False)
            error_embed.add_field(name="Error details:", value=f"Status code: {e.status_code}\nType: {e.type}\nParam: {e.param}\nCode: {e.code}", inline=False)
            await interaction.followup.send(embed=error_embed)
            pass
        except openai.APIConnectionError as e:
            error_embed = discord.Embed(title="<a:cross_custom:1219601144905601146>  Failed to connect OpenAI API", timestamp=datetime.now(), color=discord.Colour.red())
            error_message = ast.literal_eval(str(e).split(f"{e.status_code} - ")[1])["error"]["message"]
            error_embed.add_field(name='\u200b', value=f"Failed to connect OpenAI API. The GPT model may currently unavailable or overloaded, or the OpenAI service has been blocked from your current network. Please try again later or connect to another network to see if the error could be resolved.\nError message: {error_message}", inline=False)
            error_embed.add_field(name='\u200b', value=f"", inline=False)
            error_embed.add_field(name="Error details:", value=f"Status code: {e.status_code}\nType: {e.type}\nParam: {e.param}\nCode: {e.code}", inline=False)
            await interaction.followup.send(embed=error_embed)
            pass
        except openai.RateLimitError as e:
            error_embed = discord.Embed(title="<a:cross_custom:1219601144905601146>  OpenAI API request rate limit exceeded", timestamp=datetime.now(), color=discord.Colour.red())
            error_message = ast.literal_eval(str(e).split(f"{e.status_code} - ")[1])["error"]["message"]
            error_embed.add_field(name='\u200b', value=error_message, inline=False)
            error_embed.add_field(name='\u200b', value=f"", inline=False)
            error_embed.add_field(name="Error details:", value=f"Status code: {e.status_code}\nType: {e.type}\nParam: {e.param}\nCode: {e.code}", inline=False)
            await interaction.followup.send(embed=error_embed)
            pass
        except openai.BadRequestError as e:
            error_embed = discord.Embed(title="<a:cross_custom:1219601144905601146>  Invalid request to OpenAI API", timestamp=datetime.now(), color=discord.Colour.red())
            error_message = ast.literal_eval(str(e).split(f"{e.status_code} - ")[1])["error"]["message"]
            error_embed.add_field(name='\u200b', value=error_message, inline=False)
            error_embed.add_field(name='\u200b', value=f"", inline=False)
            error_embed.add_field(name="Error details:", value=f"Status code: {e.status_code}\nType: {e.type}\nParam: {e.param}\nCode: {e.code}", inline=False)
            await interaction.followup.send(embed=error_embed)
            pass
        except openai.AuthenticationError as e:
            error_embed = discord.Embed(title="<a:cross_custom:1219601144905601146>  Authentication error with OpenAI API", timestamp=datetime.now(), color=discord.Colour.red())
            error_message = ast.literal_eval(str(e).split(f"{e.status_code} - ")[1])["error"]["message"]
            error_embed.add_field(name='\u200b', value=error_message, inline=False)
            error_embed.add_field(name='\u200b', value=f"", inline=False)
            error_embed.add_field(name="Error details:", value=f"Status code: {e.status_code}\nType: {e.type}\nParam: {e.param}\nCode: {e.code}", inline=False)
            await interaction.followup.send(embed=error_embed)
            pass
        except openai.APIError as e:
            error_embed = discord.Embed(title="<a:cross_custom:1219601144905601146>  An error returned from OpenAI API", timestamp=datetime.now(), color=discord.Colour.red())
            error_message = ast.literal_eval(str(e).split(f"{e.status_code} - ")[1])["error"]["message"]
            error_embed.add_field(name='\u200b', value=error_message, inline=False)
            error_embed.add_field(name='\u200b', value=f"", inline=False)
            error_embed.add_field(name="Error details:", value=f"Status code: {e.status_code}\nType: {e.type}\nParam: {e.param}\nCode: {e.code}", inline=False)
            await interaction.followup.send(embed=error_embed)
            pass

# ----------</ChatGPT>----------


async def setup(bot):
    await bot.add_cog(ChatGPT(bot))