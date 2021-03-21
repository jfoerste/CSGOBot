import os
import requests
import datetime
from discord.ext import commands
from discord import Embed, Game
import traceback
import sys
import re

headers = {}

tracker_api_url = 'https://public-api.tracker.gg/v2/csgo/standard/profile/steam/'
profile_url_stub = 'http://steamcommunity.com/profiles/'
steam_api_url = 'http://api.steampowered.com/ISteamUser/GetPlayerBans/v1/'

STEAM_KEY = ''

bot = commands.Bot(command_prefix='$')

rate_limit_until = datetime.datetime.min

info_message = """**To look up a players CSGO Statistics please use `$cs` followed by an ID or URL in one \
of the following forms:**
steamID: `STEAM_0:0:139398065`
steamID64: `76561198239061858`
customURL: `http://steamcommunity.com/id/theheadshooter` or `theheadshooter`
profileURL: `http://steamcommunity.com/profiles/76561198239061858`
"""


class APIError(LookupError):
    """Error calling API"""
    cases = {
        "rate_limit": "**Rate limit hit! Please wait til the next minute and slow down your requests.**",
        "CollectorResultStatus::NotFound": "**No user profile with that id or URL was found.**",
        "CollectorResultStatus::Private": "**The player either hasn't played CSGO or their profile is private.**",
        "invalid_format": """**The profile identifier does not match one of the supported formats.\
        Please use any of the following:**
        steamID: `STEAM_0:0:139398065`
        steamID64: `76561198239061858`
        customURL: `http://steamcommunity.com/id/theheadshooter` or `theheadshooter`
        profileURL: `http://steamcommunity.com/profiles/76561198239061858`
        """
    }

    def __init__(self, case):
        if case is not None and case in self.cases:
            self.message = self.cases[case]
        else:
            self.message = "An unknown error occured while fetching data for the given user."
        # print(f"message: {self.message} case: {str(case)}")


def get_steam_api(endpoint, params):
    params["key"] = STEAM_KEY
    r = requests.get(
        "http://api.steampowered.com/" + endpoint,
        params=params
    )

    if r.status_code == 200:
        return r.json()
    else:
        raise APIError("")


re_ID32 = re.compile("^STEAM_0:[01]:[0-9]{4,10}$")
re_ID64 = re.compile("^https?://steamcommunity\\.com/profiles/([0-9]{17})/?$|^([0-9]{17})$")
re_custom_URL = re.compile("^https?://steamcommunity\\.com/id/([a-zA-Z0-9/]+)$|(^[a-zA-Z0-9]+)$")


def id32_to_id64(id32):
    parts = id32.split(":")
    universe = int(parts[0][6:])
    universe = 1 if universe == 0 else universe
    return str((universe << 56) | (1 << 52) | (1 << 32) | (int(parts[2]) << 1) | int(parts[1]))


def custom_url_to_id64(string):
    r = get_steam_api("ISteamUser/ResolveVanityURL/v0001/", {"vanityurl": string})

    if r["response"]["success"] == 1:
        return r["response"]["steamid"]
    else:
        raise APIError("CollectorResultStatus::NotFound")


def parse_id64(string):
    if re_ID32.fullmatch(string):
        return id32_to_id64(string)  # string is SteamID32
    elif match := re_ID64.match(string):
        return ''.join(filter(None, match.group(1, 2)))  # is SteamID64
    elif match := re_custom_URL.match(string):
        return custom_url_to_id64(''.join(filter(None, match.group(1, 2))))  # is custom url name
    else:
        raise(APIError("invalid_format"))


def get_stats(id):
    # TODO: Query data from steam web api instead of tracker.gg
    # TODO: Cache results for 5 mins???
    global rate_limit_until
    if datetime.datetime.now() < rate_limit_until:
        raise APIError("rate_limit")

    r = requests.get(
        tracker_api_url + id,
        headers=headers
    )

    json = r.json()

    # print(r.headers)
    if "X-RateLimit-Remaining-minute" in r.headers and int(r.headers["X-RateLimit-Remaining-minute"]) <= 1:
        rate_limit_until = datetime.datetime.now().replace(second=0, microsecond=0) + datetime.timedelta(minutes=1)

    if "errors" in json:
        raise APIError(json["errors"][0]["code"])
    return r.json()["data"]


def get_bans(id):
    r = get_steam_api("ISteamUser/GetPlayerBans/v1/", {"steamids": id})

    data = r["players"][0]
    return (
        None if data["VACBanned"] is False else data["DaysSinceLastBan"],
        False if data["EconomyBan"] == "none" else True,
        data["CommunityBanned"]
    )


def result_embed(data, bans, id):
    name = data['platformInfo']['platformUserHandle']
    profile_url = profile_url_stub + id
    thumbnail_url = data['platformInfo']['avatarUrl']
    stats = data["segments"][0]["stats"]

    ban_str = f"""\
    VAC: {'✅' if bans[0] is None else f'❌ Banned {bans[0]} days ago!'}
    Trade: {'✅' if bans[1] == False else '❌'}
    Community: {'✅' if bans[2] == False else '❌'}
    """

    embed = Embed(colour=8545008)
    embed.description = f"**Profile: **[**{name}**]({profile_url})"
    embed.timestamp = datetime.datetime.utcnow()
    embed.set_footer(text="CSGO Profile Statistics")
    embed.set_author(name="CSGO Profile Statistics")
    embed.set_thumbnail(url=thumbnail_url)

    embed.add_field(name="Kills:", value=stats["kills"]["displayValue"], inline=True)
    embed.add_field(name="Deaths:", value=stats["deaths"]["displayValue"], inline=True)
    embed.add_field(name="K/D:", value=stats["kd"]["displayValue"], inline=True)
    embed.add_field(name="Accuracy:", value=stats["shotsAccuracy"]["displayValue"], inline=True)
    embed.add_field(name="Wins:", value=stats["wins"]["displayValue"], inline=True)
    embed.add_field(name="Win%:", value=stats["wlPercentage"]["displayValue"], inline=True)

    embed.add_field(name="Reputation:", value=ban_str)
    return embed


def err_embed(message):
    embed = Embed(colour=16711680)
    embed.timestamp = datetime.datetime.utcnow()
    embed.set_footer(text="CSGO Profile Statistics")
    embed.set_author(name="CSGO Profile Statistics")

    embed.add_field(name="❌ ERROR ❌", value=f"{message}")
    return embed


def info_embed():
    embed = Embed(colour=255)
    embed.timestamp = datetime.datetime.utcnow()
    embed.set_footer(text="CSGO Profile Statistics")
    embed.set_author(name="CSGO Profile Statistics")

    embed.add_field(name="➡ ℹ ", value=f"{info_message}")
    return embed


@bot.event
async def on_ready():
    print('Logged in as {0.user}'.format(bot))
    await bot.change_presence(activity=Game("$cs with steam ID or URL"))


@bot.command()
async def cs(ctx, *args):
    if len(args) == 0:
        embed = info_embed()
    else:
        try:
            if len(args) > 1:
                raise APIError("invalid_format")

            id = parse_id64(args[0])
            data = get_stats(id)
            bans = get_bans(id)
            embed = result_embed(data, bans, id)
        except APIError as err:
            embed = err_embed(err.message)
        except Exception as e:
            print(traceback.print_exc())
            sys.stdout.flush()
            print(e)
            sys.stdout.flush()
            embed = err_embed("An unknown error occured.")
    await ctx.reply(embed=embed)


if __name__ == '__main__':
    TOKEN = os.getenv('TOKEN')
    TRACKER_KEY = os.getenv('TRACKER_KEY')
    STEAM_KEY = os.getenv('STEAM_KEY')
    if TOKEN is None:
        print('The environment variable TOKEN is missing!')
        exit()
    elif TRACKER_KEY is None:
        print('The environment variable TRACKER_KEY is missing!')
        exit()
    elif STEAM_KEY is None:
        print('The environment variable STEAM_KEY is missing!')
        exit()
    else:
        headers = {'TRN-Api-Key': TRACKER_KEY}
    bot.run(TOKEN)
