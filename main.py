import os
import requests
import datetime
from discord.ext import commands
from discord import Embed, Game
import traceback
import sys


headers = {}

api_url = 'https://public-api.tracker.gg/v2/csgo/standard/profile/steam/'
profile_url_stub = 'http://steamcommunity.com/profiles/'
steam_api_url = 'http://api.steampowered.com/ISteamUser/GetPlayerBans/v1/'

STEAM_KEY = ''

bot = commands.Bot(command_prefix='$')

rate_limit_until = datetime.datetime.min


class APIError(LookupError):
    """Error calling API"""
    cases = {
        "rate_limit": "Rate limit hit! Please wait til the next minute and slow down your requests.",
        "CollectorResultStatus::NotFound": "No user profile with that id or URL was found.",
        "CollectorResultStatus::Private": "The player either hasn't played CSGO or their profile is private."
    }

    def __init__(self, case):
        if case is not None and case in self.cases:
            self.message = self.cases[case]
        else:
            self.message = "An unknown error occured while fetching data for the given user."
        #print(f"message: {self.message} case: {str(case)}")


def get_stats(profile):
    # TODO: Query data from steam web api instead of tracker.gg
    # TODO: Cache results for 5 mins???
    global rate_limit_until
    if datetime.datetime.now() < rate_limit_until:
        raise APIError("rate_limit")

    profile = profile.replace("https://steamcommunity.com/profiles/", "").replace("https://steamcommunity.com/id/", "")
    #print(profile)
    r = requests.get(
        api_url + profile,
        headers=headers
    )

    json = r.json()

    #print(r.headers)
    if "X-RateLimit-Remaining-minute" in r.headers and int(r.headers["X-RateLimit-Remaining-minute"]) <= 1:
        rate_limit_until = datetime.datetime.now().replace(second=0, microsecond=0) + datetime.timedelta(minutes=1)

    if "errors" in json:
        raise APIError(json["errors"][0]["code"])
    return r.json()["data"]


def get_bans(id):
    r = requests.get(
        steam_api_url,
        params={
            "steamids": id,
            "key": STEAM_KEY
        }
    )
    data = r.json()["players"][0]
    return (
        None if data["VACBanned"] is False else data["DaysSinceLastBan"],
        False if data["EconomyBan"] == "none" else True,
        data["CommunityBanned"]
    )


def gen_embed(profile):
    try:
        data = get_stats(profile)
        bans = get_bans(data['platformInfo']['platformUserIdentifier'])

        name = data['platformInfo']['platformUserHandle']
        profile_url = profile_url_stub + data['platformInfo']['platformUserIdentifier']
        thumbnail_url = data['platformInfo']['avatarUrl']
        stats = data["segments"][0]["stats"]

        ban_str = f"""\
        VAC: {'✅' if bans[0] is None else f'❌ Banned {bans[0]} days ago!'}
        Trade: {'✅' if bans[1] == False else '❌'}
        Community: {'✅' if bans[2] == False else '❌'}
        """

        embed = Embed(colour=8545008)
        embed.description = f"Profile: [**{name}**]({profile_url})"
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
    except APIError as err:
        embed = Embed(colour=16711680)
        embed.timestamp = datetime.datetime.utcnow()
        embed.set_footer(text="CSGO Profile Statistics")
        embed.set_author(name="CSGO Profile Statistics")

        embed.add_field(name="❌ ERROR ❌", value=f"{err.message}")
    except Exception as e:
        embed = Embed(colour=16711680)
        embed.timestamp = datetime.datetime.utcnow()
        embed.set_footer(text="CSGO Profile Statistics")
        embed.set_author(name="CSGO Profile Statistics")
        embed.add_field(name="❌ ERROR ❌", value="An unknown error occured.")
        print(traceback.print_exc())
        sys.stdout.flush()
        print(e)
        sys.stdout.flush()

    return embed


@bot.event
async def on_ready():
    print('Logged in as {0.user}'.format(bot))
    await bot.change_presence(activity=Game("$cs with steam ID or URL"))


@bot.command()
async def cs(ctx, arg):
    embed = gen_embed(arg)
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

