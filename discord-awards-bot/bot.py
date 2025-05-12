import discord
from discord.ext import commands
from discord import app_commands
import json
import os

# Intents
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

APPROVER_ROLE = "Council"
NOMINATOR_ROLE = "Phantom Company"
NOMINATIONS_FILE = "nominations.json"

# Load nominations
if os.path.exists(NOMINATIONS_FILE):
    with open(NOMINATIONS_FILE, "r") as f:
        nominations = json.load(f)
else:
    nominations = {}

def save_nominations():
    with open(NOMINATIONS_FILE, "w") as f:
        json.dump(nominations, f, indent=4)

class AwardButtons(discord.ui.View):
    def __init__(self, nomination_id, guild):
        super().__init__(timeout=None)
        self.nomination_id = nomination_id
        self.guild = guild

    @discord.ui.button(label="✅ Approve", style=discord.ButtonStyle.green)
    async def approve(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not any(role.name == APPROVER_ROLE for role in interaction.user.roles):
            await interaction.response.send_message("You are not authorized to approve awards.", ephemeral=True)
            return

        nomination = nominations.get(str(self.nomination_id))
        if not nomination or nomination["status"] != "pending":
            await interaction.response.send_message("Invalid or already processed nomination.", ephemeral=True)
            return

        nomination["status"] = "approved"
        nomination["approved_by"] = interaction.user.name
        save_nominations()

        # Give role to nominated users
        role = discord.utils.get(self.guild.roles, name=nomination["medal"])
        if not role:
            role = await self.guild.create_role(name=nomination["medal"])

        for user_id in nomination["user_ids"]:
            member = self.guild.get_member(int(user_id))
            if member:
                await member.add_roles(role)

        await interaction.response.edit_message(content=f"✅ Nomination approved by {interaction.user.mention}. Role **{role.name}** granted.", view=None)

    @discord.ui.button(label="❌ Deny", style=discord.ButtonStyle.red)
    async def deny(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not any(role.name == APPROVER_ROLE for role in interaction.user.roles):
            await interaction.response.send_message("You are not authorized to deny awards.", ephemeral=True)
            return

        nomination = nominations.get(str(self.nomination_id))
        if not nomination or nomination["status"] != "pending":
            await interaction.response.send_message("Invalid or already processed nomination.", ephemeral=True)
            return

        nomination["status"] = "denied"
        nomination["denied_by"] = interaction.user.name
        save_nominations()

        await interaction.response.edit_message(content=f"❌ Nomination denied by {interaction.user.mention}.", view=None)

@bot.event
async def on_ready():
    await tree.sync()
    print(f"Logged in as {bot.user}")
    print("Slash commands synced.")

@tree.command(name="award", description="Nominate members for a medal/role.")
@app_commands.describe(
    users="Mention users (space separated)",
    medal="Medal or role name",
    reason="Reason for the award"
)
async def award(interaction: discord.Interaction, users: str, medal: str, reason: str):
    # Check for "Phantom Company" role
    if not any(role.name == NOMINATOR_ROLE for role in interaction.user.roles):
        await interaction.response.send_message("Only Phantom Company can nominate members.", ephemeral=True)
        return

    user_mentions = users.split()
    user_ids = [user.strip("<@!>") for user in user_mentions if user.startswith("<@")]
    if not user_ids:
        await interaction.response.send_message("Please mention valid users.", ephemeral=True)
        return

    nomination_id = str(len(nominations) + 1)
    nominations[nomination_id] = {
        "nominator": interaction.user.name,
        "user_ids": user_ids,
        "users": user_mentions,
        "medal": medal,
        "reason": reason,
        "status": "pending"
    }
    save_nominations()

    embed = discord.Embed(
        title=f"🎖️ Award Nomination #{nomination_id}",
        description=f"**Nominated:** {', '.join(user_mentions)}\n**Medal:** {medal}\n**Reason:** {reason}\n**Nominated by:** {interaction.user.mention}",
        color=discord.Color.gold()
    )

    view = AwardButtons(nomination_id, interaction.guild)
    await interaction.response.send_message(embed=embed, view=view)
