import discord
from discord import Interaction, Option
from discord.ext import commands


class SendFromInput(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ----------<Send from input>----------

    # Send message from user input
    @commands.slash_command(description="Send your message or attatchment")
    async def send(self, interaction: Interaction, message: Option(str, name="message", description="The message u would like to send. Leave this empty if u want to send the attachment only.", required=False), attachment: Option(discord.Attachment, name="attachment", description="The attachment u would like to send. Leave this empty if u want to send the message only.", required=False)):
        if message is None and attachment is None:
            # Returns if no message or attachment are provided
            await interaction.response.send_message("You cannot send nothing to me! (say at least send a message or an attachment)")
        else:
            # Sends the required input
            await interaction.response.defer()
            # Checks if the attachment is None or not
            if attachment is not None:
                # Converts the attachment to a discord.File() object
                files = await attachment.to_file()
                # Checks if the message is None or not
                if message is not None:
                    # Sends the message and the attachment in both
                    await interaction.channel.send(message, file=files)
                else:
                    # Sends the attachment only
                    await interaction.send(file=files)
            else:
                # Sends the message only
                await interaction.send(message)
            # Deletes the interaction
            await interaction.followup.send('\u200b', delete_after=0)

    # ----------</Send from input>----------


def setup(bot):
    bot.add_cog(SendFromInput(bot))
  