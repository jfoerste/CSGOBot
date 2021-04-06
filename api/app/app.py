import os
import requests
import datetime
import traceback
import sys
import re
import logging
from functools import wraps
from cachetools import cached, TTLCache
from flask import Flask, request
from flask_json import FlaskJSON, json_response


print(sys.implementation.version)

TRACKER_API_URL = 'https://public-api.tracker.gg/v2/csgo/standard/profile/steam/'
PROFILE_URL_STUB = 'http://steamcommunity.com/profiles/'
rate_limit_until = datetime.datetime.min
app = Flask(__name__)
json = FlaskJSON(app)


def load_env(name):
    var = os.getenv(name)
    if var:
        return var
    print(f"The environment variable {name} is missing!")
    exit()


TRACKER_KEY = load_env('TRACKER_KEY')
STEAM_KEY = load_env('STEAM_KEY')
headers = {'TRN-Api-Key': TRACKER_KEY}


class APIError(LookupError):
    """Error calling API"""
    cases = {
        "rate_limit": "**Rate limit hit! Please wait til the next minute and slow down your requests.**",
        "CollectorResultStatus::NotFound": "**No user profile with that ID or URL was found.**",
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
    raise APIError("")


re_ID32 = re.compile("^STEAM_0:[01]:[0-9]{4,10}$")
re_ID64 = re.compile("^https?://steamcommunity\\.com/profiles/([0-9]{17})/?$|^([0-9]{17})$")
re_custom_URL = re.compile("^https?://steamcommunity\\.com/id/([a-zA-Z0-9]+)/?$|(^[a-zA-Z0-9]+)$")


def id32_to_id64(id32):
    parts = id32.split(":")
    universe = int(parts[0][6:])
    universe = 1 if universe == 0 else universe
    return str((universe << 56) | (1 << 52) | (1 << 32) | (int(parts[2]) << 1) | int(parts[1]))


@cached(cache=TTLCache(maxsize=128, ttl=3600))
def custom_url_to_id64(string):
    # with sentry_sdk.start_span(op="prep_http", description="Call SteamAPI to convert custom URL to id64"):
    r = get_steam_api("ISteamUser/ResolveVanityURL/v0001/", {"vanityurl": string})

    if r["response"]["success"] == 1:
        return r["response"]["steamid"]
    else:
        raise APIError("CollectorResultStatus::NotFound")


def parse_id64(string):
    # with sentry_sdk.start_span(op="parse", description="Parse SteamID"):
    if re_ID32.fullmatch(string):
        return id32_to_id64(string)  # string is SteamID32
    elif match := re_ID64.fullmatch(string):
        return ''.join(filter(None, match.group(1, 2)))  # is SteamID64
    elif match := re_custom_URL.fullmatch(string):
        return custom_url_to_id64(''.join(filter(None, match.group(1, 2))))  # is custom url name
    raise (APIError("invalid_format"))


@cached(cache=TTLCache(maxsize=128, ttl=3600))
def get_stats(id):
    # with sentry_sdk.start_span(op="prep_http", description="Call Tracker API to get player stats"):
    # TODO: Query data from steam web api instead of tracker.gg
    global rate_limit_until
    if datetime.datetime.now() < rate_limit_until:
        raise APIError("rate_limit")

    r = requests.get(
        TRACKER_API_URL + id,
        headers=headers
    )

    json = r.json()

    # print(r.headers)
    if "X-RateLimit-Remaining-minute" in r.headers and int(r.headers["X-RateLimit-Remaining-minute"]) <= 1:
        rate_limit_until = datetime.datetime.now().replace(second=0, microsecond=0) + datetime.timedelta(minutes=1)

    if "errors" in json:
        raise APIError(json["errors"][0]["code"])
    return r.json()["data"]


@cached(cache=TTLCache(maxsize=128, ttl=3600))
def get_bans(id):
    # with sentry_sdk.start_span(op="prep_http", description="Call SteamAPI to get user ban status"):
    r = get_steam_api("ISteamUser/GetPlayerBans/v1/", {"steamids": id})

    data = r["players"][0]
    return (
        None if data["VACBanned"] is False else data["DaysSinceLastBan"],
        False if data["EconomyBan"] == "none" else True,
        data["CommunityBanned"]
    )


@app.route('/', methods=['GET'])
def get_data():
    try:
        name = request.args["name"]
        if len(name.split(" ")) != 1:
            raise APIError("invalid_format")
        id = parse_id64(name)
        data = get_stats(id)
        bans = get_bans(id)
        return json_response(status_=200, id=id, data=data, bans=bans)
    except KeyError:
        return json_response(status_=400, message=APIError("invalid_format").message)
    except APIError as err:
        return json_response(status_=404, message=err.message)
    except Exception as e:
        return json_response(status_=500, message="An unknown error occured!")






