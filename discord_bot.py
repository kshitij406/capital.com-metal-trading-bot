import base64
import os
from datetime import datetime, timezone

import discord
import requests
from discord import app_commands
from dotenv import load_dotenv

import config
from capital_api import CapitalAPI

load_dotenv()

DISCORD_BOT_TOKEN = os.environ["DISCORD_BOT_TOKEN"]
GITHUB_USERNAME = os.environ["GITHUB_USERNAME"]
GITHUB_REPO = os.environ["GITHUB_REPO"]
GITHUB_ACCESS_TOKEN = os.environ["GITHUB_ACCESS_TOKEN"]

STATS_URL = f"https://raw.githubusercontent.com/{GITHUB_USERNAME}/{GITHUB_REPO}/main/stats.json"
STATS_UNAVAILABLE = "Stats unavailable, bot may be mid-cycle. Try again in 30 seconds."
STATS_UNAVAILABLE_SHORT = "Stats unavailable. Try in 30 seconds."

GITHUB_API_BASE = f"https://api.github.com/repos/{GITHUB_USERNAME}/{GITHUB_REPO}"
GITHUB_HEADERS = {
    "Authorization": f"Bearer {GITHUB_ACCESS_TOKEN}",
    "Accept": "application/vnd.github+json",
}
STARTING_BALANCE = 1000

client = discord.Client(intents=discord.Intents.default())
tree = app_commands.CommandTree(client)


def fetch_stats():
    try:
        resp = requests.get(STATS_URL, timeout=10)
        resp.raise_for_status()
        return resp.json()
    except Exception:
        return None


def format_streak(streak):
    if streak == 0:
        return "0"
    return f"{abs(streak)} win{'s' if abs(streak) != 1 else ''}" if streak > 0 else f"{abs(streak)} loss{'es' if abs(streak) != 1 else ''}"


def time_ago(iso_ts):
    then = datetime.fromisoformat(iso_ts)
    minutes = int((datetime.now(timezone.utc) - then).total_seconds() / 60)
    if minutes < 1:
        return "just now"
    if minutes < 60:
        return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
    hours = minutes // 60
    return f"{hours} hour{'s' if hours != 1 else ''} ago"


def signed(v):
    return f"+${v:.2f}" if v >= 0 else f"-${abs(v):.2f}"


@tree.command(name="profits", description="Show full trading stats")
async def profits(interaction: discord.Interaction):
    data = fetch_stats()
    if data is None:
        await interaction.response.send_message(STATS_UNAVAILABLE, ephemeral=True)
        return

    overall = data["overall"]
    color = 0x00FF00 if overall["total_pnl"] >= 0 else 0xFF0000

    embed = discord.Embed(title="Trading Stats", color=color)
    embed.add_field(name="Total PnL", value=signed(overall["total_pnl"]), inline=True)
    embed.add_field(name="Win rate", value=f"{overall['win_rate']}%", inline=True)
    embed.add_field(name="Streak", value=format_streak(overall["current_streak"]), inline=True)
    embed.add_field(
        name="Trades",
        value=f"{overall['total_trades']} total ({overall['closed_trades']} closed, {overall['open_trades']} open)",
        inline=False,
    )
    embed.add_field(name="Best trade", value=signed(overall["best_trade"]), inline=True)
    embed.add_field(name="Worst trade", value=signed(overall["worst_trade"]), inline=True)

    for epic, epic_stats in data["by_epic"].items():
        embed.add_field(
            name=epic,
            value=f"{epic_stats['trades']} trades, PnL {signed(epic_stats['pnl'])}",
            inline=True,
        )

    embed.set_footer(text=f"Last updated: {time_ago(data['last_updated'])}")

    await interaction.response.send_message(embed=embed, ephemeral=True)


@tree.command(name="status", description="Quick one-line bot status")
async def status(interaction: discord.Interaction):
    data = fetch_stats()
    if data is None:
        await interaction.response.send_message(STATS_UNAVAILABLE, ephemeral=True)
        return

    overall = data["overall"]
    await interaction.response.send_message(
        f"Bot running. {overall['total_trades']} trades, {overall['win_rate']}% win rate, "
        f"PnL: {signed(overall['total_pnl'])}. Last cycle: {time_ago(data['last_updated'])}.",
        ephemeral=True,
    )


@tree.command(name="balance", description="Quick PnL and open trade check")
async def balance(interaction: discord.Interaction):
    data = fetch_stats()
    if data is None:
        await interaction.response.send_message(STATS_UNAVAILABLE, ephemeral=True)
        return

    overall = data["overall"]
    await interaction.response.send_message(
        f"PnL: {signed(overall['total_pnl'])} | Open trades: {overall['open_trades']}",
        ephemeral=True,
    )


@tree.command(name="winstreak", description="Show current win/loss streak")
async def winstreak(interaction: discord.Interaction):
    data = fetch_stats()
    if data is None:
        await interaction.response.send_message(STATS_UNAVAILABLE_SHORT, ephemeral=True)
        return

    overall = data["overall"]
    streak = overall["current_streak"]
    color = 0x00FF00 if streak > 0 else (0xFF0000 if streak < 0 else 0x808080)

    embed = discord.Embed(title="Win Streak", color=color)
    embed.add_field(name="Current streak", value=format_streak(streak), inline=False)
    embed.add_field(
        name="Best streak ever",
        value="Track your best streak manually for now, stats module does not record this yet",
        inline=False,
    )
    embed.add_field(name="Overall win rate", value=f"{overall['win_rate']}%", inline=False)

    await interaction.response.send_message(embed=embed, ephemeral=True)


@tree.command(name="bestday", description="Show the best single trade")
async def bestday(interaction: discord.Interaction):
    data = fetch_stats()
    if data is None:
        await interaction.response.send_message(STATS_UNAVAILABLE_SHORT, ephemeral=True)
        return

    best = data["overall"]["best_trade"]
    embed = discord.Embed(description=f"Best single trade: {signed(best)}", color=0x00FF00)
    embed.set_footer(text="Per-day breakdown not yet tracked. This shows best single trade.")

    await interaction.response.send_message(embed=embed, ephemeral=True)


@tree.command(name="worstday", description="Show the worst single trade")
async def worstday(interaction: discord.Interaction):
    data = fetch_stats()
    if data is None:
        await interaction.response.send_message(STATS_UNAVAILABLE_SHORT, ephemeral=True)
        return

    worst = data["overall"]["worst_trade"]
    embed = discord.Embed(description=f"Worst single trade: {signed(worst)}", color=0xFF0000)
    embed.set_footer(text="Per-day breakdown not yet tracked. This shows worst single trade.")

    await interaction.response.send_message(embed=embed, ephemeral=True)


@tree.command(name="breakdown", description="Show individual trade history info")
async def breakdown(interaction: discord.Interaction):
    data = fetch_stats()
    if data is None:
        await interaction.response.send_message(STATS_UNAVAILABLE_SHORT, ephemeral=True)
        return

    await interaction.response.send_message(
        "Individual trade history is stored in trades.db on the GitHub Actions runner. "
        "To view it, go to your repo > Actions > most recent run > download the trades.db artifact.\n"
        "Note: this is a known limitation. Individual trade log export can be added as a future feature.",
        ephemeral=True,
    )


@tree.command(name="expectancy", description="Show expectancy per trade")
async def expectancy(interaction: discord.Interaction):
    data = fetch_stats()
    if data is None:
        await interaction.response.send_message(STATS_UNAVAILABLE_SHORT, ephemeral=True)
        return

    overall = data["overall"]
    exp = overall["expectancy"]
    closed = overall["closed_trades"]
    color = 0x00FF00 if exp >= 0 else 0xFF0000

    if exp >= 0:
        explanation = f"On average each trade makes you ${exp:.2f}. Keep the sample size growing."
    else:
        explanation = f"On average each trade loses you ${abs(exp):.2f}. Need more data or strategy adjustment."

    if closed < 20:
        explanation += f"\n⚠️ Only {closed} trades closed — too early to trust this number. Need 20+ trades."

    embed = discord.Embed(description=f"Expectancy: {signed(exp)} per trade\n{explanation}", color=color)

    await interaction.response.send_message(embed=embed, ephemeral=True)


@tree.command(name="drawdown", description="Show max drawdown and risk context")
async def drawdown(interaction: discord.Interaction):
    data = fetch_stats()
    if data is None:
        await interaction.response.send_message(STATS_UNAVAILABLE_SHORT, ephemeral=True)
        return

    dd = data["overall"]["max_drawdown"]
    pct = abs(dd) / STARTING_BALANCE * 100

    if pct < 10:
        context, color = "Healthy. Under 10% drawdown.", 0x00FF00
    elif pct <= 20:
        context, color = "Moderate. Watch this carefully.", 0xFFFF00
    else:
        context, color = "High drawdown. Consider pausing and reviewing strategy.", 0xFF0000

    embed = discord.Embed(description=f"Max drawdown: -${abs(dd):.2f}\n{context}", color=color)

    await interaction.response.send_message(embed=embed, ephemeral=True)


@tree.command(name="price", description="Show live bid/ask/mid price for a metal")
@app_commands.describe(metal="gold, silver, or copper")
async def price(interaction: discord.Interaction, metal: str):
    epic = metal.strip().upper()
    if epic not in ("GOLD", "SILVER", "COPPER"):
        await interaction.response.send_message("metal must be gold, silver, or copper", ephemeral=True)
        return

    try:
        api = CapitalAPI()
        api.login()
        candle = api.get_candles(epic, max_candles=1)["prices"][-1]
        bid = candle["closePrice"]["bid"]
        ask = candle["closePrice"]["ask"]
        ts = candle["snapshotTimeUTC"]
    except Exception:
        await interaction.response.send_message("Could not connect to Capital.com API.", ephemeral=True)
        return

    mid = (bid + ask) / 2
    spread = ask - bid

    embed = discord.Embed(
        title=epic,
        description=f"Bid: ${bid:.2f} | Ask: ${ask:.2f} | Mid: ${mid:.2f}\nSpread: {spread:.2f} points\nAs of: {ts} UTC",
        color=0x808080,
    )

    await interaction.response.send_message(embed=embed, ephemeral=True)


def _epic_embed(data, epic, color):
    e = data["by_epic"][epic]
    embed = discord.Embed(title=epic, color=color)
    embed.add_field(name="Trades", value=str(e["trades"]), inline=True)
    embed.add_field(name="Winners", value=str(e["winners"]), inline=True)
    embed.add_field(name="Losers", value=str(e["losers"]), inline=True)
    embed.add_field(name="Win rate", value=f"{e['win_rate']}%", inline=True)
    embed.add_field(name="Total PnL", value=signed(e["pnl"]), inline=True)
    embed.set_footer(text="Individual trade data not available from stats.json")
    return embed


@tree.command(name="gold", description="Show GOLD stats")
async def gold(interaction: discord.Interaction):
    data = fetch_stats()
    if data is None:
        await interaction.response.send_message(STATS_UNAVAILABLE_SHORT, ephemeral=True)
        return
    await interaction.response.send_message(embed=_epic_embed(data, "GOLD", 0xFFD700), ephemeral=True)


@tree.command(name="silver", description="Show SILVER stats")
async def silver(interaction: discord.Interaction):
    data = fetch_stats()
    if data is None:
        await interaction.response.send_message(STATS_UNAVAILABLE_SHORT, ephemeral=True)
        return
    await interaction.response.send_message(embed=_epic_embed(data, "SILVER", 0xC0C0C0), ephemeral=True)


@tree.command(name="copper", description="Show COPPER stats")
async def copper(interaction: discord.Interaction):
    data = fetch_stats()
    if data is None:
        await interaction.response.send_message(STATS_UNAVAILABLE_SHORT, ephemeral=True)
        return
    await interaction.response.send_message(embed=_epic_embed(data, "COPPER", 0xB87333), ephemeral=True)


@tree.command(name="pause", description="Pause the trading bot (no new entries)")
async def pause(interaction: discord.Interaction):
    try:
        content = base64.b64encode(b"paused").decode()
        resp = requests.put(
            f"{GITHUB_API_BASE}/contents/PAUSED",
            headers=GITHUB_HEADERS,
            json={"message": "Pause bot", "content": content},
            timeout=10,
        )
        resp.raise_for_status()
    except Exception:
        await interaction.response.send_message(STATS_UNAVAILABLE_SHORT, ephemeral=True)
        return

    embed = discord.Embed(
        description=(
            "Bot paused. No new trades will be opened until /resume is called.\n"
            "Note: any currently open positions will still be managed by Capital.com's SL/TP "
            "— the bot only skips new entries."
        ),
        color=0xFF8C00,
    )
    await interaction.response.send_message(embed=embed, ephemeral=True)


@tree.command(name="resume", description="Resume the trading bot")
async def resume(interaction: discord.Interaction):
    try:
        get_resp = requests.get(f"{GITHUB_API_BASE}/contents/PAUSED", headers=GITHUB_HEADERS, timeout=10)
        if get_resp.status_code != 404:
            get_resp.raise_for_status()
            sha = get_resp.json()["sha"]
            del_resp = requests.delete(
                f"{GITHUB_API_BASE}/contents/PAUSED",
                headers=GITHUB_HEADERS,
                json={"message": "Resume bot", "sha": sha},
                timeout=10,
            )
            del_resp.raise_for_status()
    except Exception:
        await interaction.response.send_message(STATS_UNAVAILABLE_SHORT, ephemeral=True)
        return

    embed = discord.Embed(description="Bot resumed. New trades will open on next signal.", color=0x00FF00)
    await interaction.response.send_message(embed=embed, ephemeral=True)


@tree.command(name="forcecycle", description="Manually trigger a bot cycle now")
async def forcecycle(interaction: discord.Interaction):
    try:
        resp = requests.post(
            f"{GITHUB_API_BASE}/actions/workflows/bot.yml/dispatches",
            headers=GITHUB_HEADERS,
            json={"ref": "main"},
            timeout=10,
        )
        resp.raise_for_status()
    except Exception:
        await interaction.response.send_message(STATS_UNAVAILABLE_SHORT, ephemeral=True)
        return

    embed = discord.Embed(description="Manual cycle triggered. Check GitHub Actions in ~30 seconds.", color=0x0000FF)
    await interaction.response.send_message(embed=embed, ephemeral=True)


@tree.command(name="roast", description="Get roasted based on your trading stats")
async def roast(interaction: discord.Interaction):
    data = fetch_stats()
    if data is None:
        await interaction.response.send_message(STATS_UNAVAILABLE_SHORT, ephemeral=True)
        return

    overall = data["overall"]
    win_rate = overall["win_rate"]
    total_pnl = overall["total_pnl"]
    exp = overall["expectancy"]
    streak = overall["current_streak"]
    total_trades = overall["total_trades"]

    lines = []
    if total_trades < 5:
        lines.append(
            f"You have {total_trades} trades. My nan has more trading experience than you "
            "and she thinks Bitcoin is a type of biscuit."
        )
    if win_rate == 100 and total_trades < 10:
        lines.append(
            f"100% win rate on {total_trades} trades. Very impressive. "
            "Ask me again after 50 trades when reality sets in."
        )
    if win_rate < 35:
        lines.append(f"Win rate of {win_rate}%. Even a coin flip would do better. At least a coin doesn't charge spread.")
    if total_pnl < -50:
        lines.append(f"You're down ${abs(total_pnl):.2f}. The market has seen you coming from a mile away.")
    if streak <= -3:
        lines.append(
            f"{abs(streak)} losses in a row. The definition of insanity is doing the same thing "
            "and expecting different results. Just saying."
        )
    if exp < -5:
        lines.append(f"Your expectancy is ${exp:.2f} per trade. You are literally paying for the privilege of losing money.")
    if win_rate > 45 and total_pnl > 0:
        lines.append("Actually not bad. Don't get cocky — the market specifically waits for overconfidence to punish it.")

    if not lines:
        lines.append("Not enough drama in your stats to roast yet. Boringly average.")

    embed = discord.Embed(description="\n".join(lines), color=0x800080)
    await interaction.response.send_message(embed=embed, ephemeral=True)


@client.event
async def on_ready():
    await tree.sync()
    print(f"Logged in as {client.user}")


if __name__ == "__main__":
    client.run(DISCORD_BOT_TOKEN)
