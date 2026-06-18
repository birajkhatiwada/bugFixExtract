import os
import re
import discord
import requests
from dotenv import load_dotenv

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")

# Matches GitHub PR URLs: github.com/{owner}/{repo}/pull/{number}
PR_URL_PATTERN = re.compile(
    r"https://github\.com/([^/\s]+)/([^/\s]+)/pull/(\d+)"
)

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)


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

    # Truncate long descriptions to fit Discord's 4096 char embed limit
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


@client.event
async def on_ready():
    print(f"Bot ready — logged in as {client.user}")


@client.event
async def on_message(message: discord.Message):
    # Ignore messages from the bot itself
    if message.author == client.user:
        return

    matches = PR_URL_PATTERN.findall(message.content)
    if not matches:
        return

    # Handle up to 3 PR links per message to avoid spam
    for owner, repo, pr_number in matches[:3]:
        pr_url = f"https://github.com/{owner}/{repo}/pull/{pr_number}"
        pr = fetch_pr(owner, repo, pr_number)

        if pr is None:
            await message.reply(
                f"Could not fetch PR info for {pr_url} — check that the GitHub token has access.",
                mention_author=False,
            )
            continue

        embed = build_embed(pr, pr_url)
        await message.reply(embed=embed, mention_author=False)


if __name__ == "__main__":
    if not DISCORD_TOKEN:
        raise RuntimeError("DISCORD_TOKEN is not set in .env")
    if not GITHUB_TOKEN:
        raise RuntimeError("GITHUB_TOKEN is not set in .env")
    client.run(DISCORD_TOKEN)
