import os
import re
import discord
from discord import app_commands
import requests
from dotenv import load_dotenv

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")

PR_URL_PATTERN = re.compile(
    r"https://github\.com/([^/\s]+)/([^/\s]+)/pull/(\d+)"
)

intents = discord.Intents.default()
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)


def fetch_pr(owner: str, repo: str, pr_number: str) -> dict | None:
    url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}"
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    response = requests.get(url, headers=headers, timeout=10)
    if response.status_code == 200:
        return response.json()
    return None


def build_embed(pr: dict, pr_url: str) -> discord.Embed:
    title = pr.get("title", "No title")
    body = pr.get("body") or "_No description provided._"
    author = pr.get("user", {}).get("login", "Unknown")
    state = pr.get("state", "unknown")
    base_branch = pr.get("base", {}).get("ref", "")
    head_branch = pr.get("head", {}).get("ref", "")

    if len(body) > 1000:
        body = body[:1000] + "\n\n_[description truncated — click link to read more]_"

    color = discord.Color.green() if state == "open" else discord.Color.red()

    embed = discord.Embed(title=title, url=pr_url, color=color)
    embed.add_field(name="Branch", value=f"`{head_branch}` → `{base_branch}`", inline=True)
    embed.add_field(name="Author", value=author, inline=True)
    embed.add_field(name="Status", value=state.capitalize(), inline=True)
    embed.add_field(name="Description", value=body, inline=False)
    embed.set_footer(text=f"PR #{pr['number']} · {pr.get('changed_files', '?')} files changed")

    return embed


@tree.command(name="bfe", description="Pull bug fix PR info from a GitHub PR link")
@app_commands.describe(link="GitHub PR URL")
async def bfe(interaction: discord.Interaction, link: str):
    match = PR_URL_PATTERN.search(link)
    if not match:
        await interaction.response.send_message("That doesn't look like a valid GitHub PR link.", ephemeral=True)
        return

    await interaction.response.defer()

    owner, repo, pr_number = match.groups()
    pr_url = f"https://github.com/{owner}/{repo}/pull/{pr_number}"
    pr = fetch_pr(owner, repo, pr_number)

    if pr is None:
        await interaction.followup.send("Could not fetch PR info — check that the GitHub token has access.")
        return

    embed = build_embed(pr, pr_url)
    await interaction.followup.send(embed=embed)


@client.event
async def on_ready():
    for guild in client.guilds:
        await tree.sync(guild=guild)
    await tree.sync()
    print(f"Bot ready — logged in as {client.user}")


if __name__ == "__main__":
    if not DISCORD_TOKEN:
        raise RuntimeError("DISCORD_TOKEN is not set in .env")
    if not GITHUB_TOKEN:
        raise RuntimeError("GITHUB_TOKEN is not set in .env")
    client.run(DISCORD_TOKEN)
