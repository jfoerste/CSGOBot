import os
import requests
import datetime
from discord.ext import commands
from discord import Embed, Game
import traceback
import sys
import re
# import sentry_sdk
import logging
from functools import wraps
# from cachetools import cached, TTLCache


PROFILE_URL_STUB = 'http://steamcommunity.com/profiles/'
WEB_PAGE_URL = "https://github.com/jfoerste/CSGOBot"

INFO_MESSAGE = """\
**To look up a players CSGO Statistics use `$cs` followed by an ID or URL in one \
of the following forms:**
steamID: `STEAM_0:0:139398065`
steamID64: `76561198239061858`
customURL: `http://steamcommunity.com/id/theheadshooter` or `theheadshooter`
profileURL: `http://steamcommunity.com/profiles/76561198239061858`
"""

bot = commands.Bot(command_prefix='$')


# def async_sentry_transaction():
#    def wrapper(fn):
#        @wraps(fn)
#        async def wrapped(*args, **kwargs):
#            with sentry_sdk.start_transaction(op=fn.__name__, name="Command recognized"):
#                return await fn(*args, **kwargs)
#        return wrapped
#    return wrapper


def result_embed(data, bans, id):
    # config and meta information
    embed = Embed(colour=8545008)
    embed.description = f"**Profile: **[**{data['platformInfo']['platformUserHandle']}**]({PROFILE_URL_STUB + id})"
    embed.timestamp = datetime.datetime.utcnow()
    embed.set_footer(text="CSGO Profile Statistics")
    embed.set_author(name="CSGO Profile Statistics", url=WEB_PAGE_URL)
    embed.set_thumbnail(url=data['platformInfo']['avatarUrl'])

    # content
    stats = data["segments"][0]["stats"]
    embed.add_field(name="Kills:", value=stats["kills"]["displayValue"], inline=True)
    embed.add_field(name="Deaths:", value=stats["deaths"]["displayValue"], inline=True)
    embed.add_field(name="K/D:", value=stats["kd"]["displayValue"], inline=True)
    embed.add_field(name="Accuracy:", value=stats["shotsAccuracy"]["displayValue"], inline=True)
    embed.add_field(name="Wins:", value=stats["wins"]["displayValue"], inline=True)
    embed.add_field(name="Win%:", value=stats["wlPercentage"]["displayValue"], inline=True)

    # ban information
    ban_str = f"""\
        VAC: {'✅' if bans[0] is None else f'❌ Banned {bans[0]} days ago!'}
        Trade: {'✅' if bans[1] == False else '❌'}
        Community: {'✅' if bans[2] == False else '❌'}
        """
    embed.add_field(name="Reputation:", value=ban_str)

    return embed


def err_embed(message):
    embed = Embed(colour=16711680)
    embed.timestamp = datetime.datetime.utcnow()
    embed.set_footer(text="CSGO Profile Statistics")
    embed.set_author(name="CSGO Profile Statistics", url=WEB_PAGE_URL)

    embed.add_field(name="❌ ERROR ❌", value=f"{message}")
    return embed


def info_embed():
    embed = Embed(colour=255)
    embed.timestamp = datetime.datetime.utcnow()
    embed.set_footer(text="CSGO Profile Statistics")
    embed.set_author(name="CSGO Profile Statistics", url=WEB_PAGE_URL)

    embed.add_field(name="➡ ℹ ", value=f"{INFO_MESSAGE}")
    return embed


@bot.event
async def on_ready():
    await bot.change_presence(activity=Game("$cs with steam ID or URL"))
    print('Logged in as {0.user}'.format(bot), flush=True)
    # print("test0", flush=True)
    # channel = bot.get_channel(823310803369328650)
    # print("test1", flush=True)
    # await channel.send('test')
    # print("test2", flush=True)


@bot.command(name="cs")
# @async_sentry_transaction()
async def cs(ctx, *args):
    if len(args) == 0:
        embed = info_embed()
    else:
        # TODO replace with aiohttp
        r = requests.get("http://api:5000", params={"name": " ".join(args)})
        data = r.json()
        try:
            if r.status_code == 200:
                embed = result_embed(data["data"], data["bans"], data["id"])
            elif r.status_code == 400:
                embed = info_embed()
            else:
                embed = err_embed(data["message"])
        except Exception as err:
            embed = err_embed("An unknown error occured.")
            traceback.print_exc()

    await ctx.reply(embed=embed)


def load_env(name):
    var = os.getenv(name)
    if var:
        return var
    print(f"The environment variable {name} is missing!")
    exit()


if __name__ == '__main__':
    TOKEN = load_env('TOKEN')
    #SENTRY_URL = load_env('SENTRY_URL')
    # sentry_sdk.init(
    #     SENTRY_URL,
    #     traces_sample_rate=1.0
    # )

    bot.run(TOKEN)
