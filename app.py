import asyncio
import time
import httpx
import json
import os
import datetime
import urllib3
from collections import defaultdict
from flask import Flask, request, jsonify
from flask_cors import CORS
from cachetools import TTLCache
from typing import Tuple
from google.protobuf import json_format, message
from google.protobuf.message import Message
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad as crypto_pad, unpad as crypto_unpad
from werkzeug.exceptions import HTTPException

from config import Config
from Pb2 import FreeFire_pb2, main_pb2, AccountPersonalShow_pb2
import game_version

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

app = Flask(__name__)
CORS(app)
app.json.sort_keys = False 
cache = TTLCache(maxsize=100, ttl=300)
cached_tokens = defaultdict(dict)

LEVELS = {
    "1": 0, "2": 48, "3": 202, "4": 544, "5": 1012, "6": 1844, "7": 2792, "8": 3800,
    "9": 4870, "10": 6004, "11": 7192, "12": 8448, "13": 9776, "14": 11140, "15": 12566,
    "16": 14060, "17": 15610, "18": 17224, "19": 18902, "20": 20632, "21": 22424,
    "22": 24728, "23": 26192, "24": 28166, "25": 30200, "26": 32294, "27": 34448,
    "28": 37804, "29": 41174, "30": 44870, "31": 48852, "32": 53334, "33": 58566,
    "34": 64096, "35": 69994, "36": 76460, "37": 83108, "38": 91128, "39": 99322,
    "40": 108092, "41": 120144, "42": 133266, "43": 147472, "44": 162760, "45": 179126,
    "46": 196572, "47": 215368, "48": 235516, "49": 257010, "50": 279860, "51": 304056,
    "52": 348318, "53": 394982, "54": 444044, "55": 495508, "56": 549364, "57": 633756,
    "58": 721744, "59": 813336, "60": 908522, "61": 1041438, "62": 1180352, "63": 1325256,
    "64": 1476184, "65": 1634300, "66": 1840946, "67": 2056594, "68": 2281242, "69": 2514880,
    "70": 2757530, "71": 3059506, "72": 3372284, "73": 3699456, "74": 4041030, "75": 4397020,
    "76": 4829104, "77": 5282204, "78": 5756304, "79": 6251404, "80": 6767504, "81": 7381324,
    "82": 8043154, "83": 8752952, "84": 9510808, "85": 10316638, "86": 11277190, "87": 12360748,
    "88": 13360304, "89": 14482858, "90": 15659418, "91": 17026708, "92": 18453688, "93": 19941280,
    "94": 21488570, "95": 23095858, "96": 24763138, "97": 26490138, "98": 28277708, "99": 30124996,
    "100": 32032284,
}

PRIORITY_REGIONS = ["BD", "IND", "SG", "BR", "US", "SAC", "NA", "ME", "ID", "TW", "VN", "TH", "PK", "CIS", "RU", "EU"]

def pad(text: bytes) -> bytes:
    padding_length = AES.block_size - (len(text) % AES.block_size)
    return text + bytes([padding_length] * padding_length)

def aes_cbc_encrypt(key: bytes, iv: bytes, plaintext: bytes) -> bytes:
    aes = AES.new(key, AES.MODE_CBC, iv)
    return aes.encrypt(pad(plaintext))

def decode_protobuf(encoded_data: bytes, message_type: message.Message) -> message.Message:
    instance = message_type()
    instance.ParseFromString(encoded_data)
    return instance

async def json_to_proto(json_data: str, proto_message: Message) -> bytes:
    json_format.ParseDict(json.loads(json_data), proto_message)
    return proto_message.SerializeToString()

def format_timestamp(ts):
    try:
        if not ts or str(ts) == "0": return "N/A"
        return datetime.datetime.fromtimestamp(int(ts)).strftime('%Y-%m-%d %I:%M:%S %p')
    except:
        return str(ts)

def get_detailed_time_diff(timestamp):
    if not timestamp or str(timestamp) == "0": return "N/A"
    try:
        ts = int(timestamp)
        now = int(time.time())
        diff = now - ts
        if diff < 0: return "Just now"

        years = diff // 31536000
        diff %= 31536000
        months = diff // 2592000
        diff %= 2592000
        weeks = diff // 604800
        diff %= 604800
        days = diff // 86400
        diff %= 86400
        hours = diff // 3600
        diff %= 3600
        minutes = diff // 60
        seconds = diff % 60

        parts = []
        if years > 0: parts.append(f"{years} Years")
        if months > 0: parts.append(f"{months} Months")
        if weeks > 0: parts.append(f"{weeks} Weeks")
        if days > 0: parts.append(f"{days} Days")
        if hours > 0: parts.append(f"{hours} Hours")
        if minutes > 0: parts.append(f"{minutes} Minutes")
        if seconds > 0 or not parts: parts.append(f"{seconds} Seconds")

        return " ".join(parts)
    except Exception:
        return "N/A"

def get_exp_for_level(level):
    try:
        return LEVELS.get(str(int(level)), 0)
    except:
        return 0

def calculate_level_progress(current_exp, current_level):
    try:
        current_level = int(current_level)
        current_exp = int(current_exp)
        
        if current_level >= 100:
            return {
                "CurrentLevel": current_level,
                "NextLevel": 100,
                "CurrentExp": current_exp,
                "ExpForCurrentLevel": LEVELS["100"],
                "ExpForNextLevel": LEVELS["100"],
                "ExpNeededForNextLevel": 0,
                "ProgressPercentage": 100.0
            }
        
        exp_for_current = get_exp_for_level(current_level)
        exp_for_next = get_exp_for_level(current_level + 1)
        
        if exp_for_next == 0 or exp_for_current == 0:
            return None
        
        exp_needed = max(0, exp_for_next - current_exp)
        exp_in_current_level = current_exp - exp_for_current
        exp_range_for_level = exp_for_next - exp_for_current
        
        progress_percentage = min(100.0, max(0.0, (exp_in_current_level / exp_range_for_level) * 100)) if exp_range_for_level > 0 else 0.0
            
        return {
            "CurrentLevel": current_level,
            "NextLevel": current_level + 1,
            "CurrentExp": current_exp,
            "ExpForCurrentLevel": exp_for_current,
            "ExpForNextLevel": exp_for_next,
            "ExpNeededForNextLevel": exp_needed,
            "ProgressPercentage": round(progress_percentage, 1)
        }
    except Exception:
        return None

def run_async(coro):
    new_loop = asyncio.new_event_loop()
    try:
        asyncio.set_event_loop(new_loop)
        return new_loop.run_until_complete(coro)
    finally:
        new_loop.close()
        asyncio.set_event_loop(None)

async def check_ban_status_garena(uid):
    ban_url = f'https://ff.garena.com/api/antihack/check_banned?lang=en&uid={uid}'
    ban_headers = {
        'User-Agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36',
        'Accept': 'application/json, text/plain, */*',
        'authority': 'ff.garena.com',
        'referer': 'https://ff.garena.com/en/support/',
        'x-requested-with': 'B6FksShzIgjfrYImLpTsadjS86sddhFH',
    }
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(ban_url, headers=ban_headers)
            data = resp.json()
            if data.get("status") == "success" and "data" in data:
                return data["data"].get("is_banned", 0)
    except Exception:
        pass
    return 0

async def get_access_token(account: str):
    url = "https://ffmconnect.live.gop.garenanow.com/oauth/guest/token/grant"
    payload = account + "&response_type=token&client_type=2&client_secret=2ee44819e9b4598845141067b281621874d0d5d7af9d8f7e00c1e54715b7d1e3&client_id=100067"
    headers = {
        'User-Agent': Config.USER_AGENT, 
        'Connection': "Keep-Alive", 
        'Accept-Encoding': "gzip", 
        'Content-Type': "application/x-www-form-urlencoded"
    }
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(url, data=payload, headers=headers)
        data = resp.json()
        return data.get("access_token", "0"), data.get("open_id", "0")

async def create_jwt(region: str):
    account = Config.get_account(region)
    token_val, open_id = await get_access_token(account)
    body = json.dumps({"open_id": open_id, "open_id_type": "4", "login_token": token_val, "orign_platform_type": "4"})
    proto_bytes = await json_to_proto(body, FreeFire_pb2.LoginReq())
    payload = aes_cbc_encrypt(Config.MAIN_KEY, Config.MAIN_IV, proto_bytes)
    url = "https://loginbp.ggblueshark.com/MajorLogin"
    headers = {
        'User-Agent': Config.USER_AGENT, 
        'Connection': "Keep-Alive", 
        'Accept-Encoding': "gzip",
        'Content-Type': "application/octet-stream", 
        'Expect': "100-continue",
        'X-Unity-Version': Config.UNITY_VERSION, 
        'X-GA': "v1 1", 
        'ReleaseVersion': Config.RELEASE_VERSION
    }
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(url, data=payload, headers=headers)
        msg = json.loads(json_format.MessageToJson(decode_protobuf(resp.content, FreeFire_pb2.LoginRes)))
        cached_tokens[region] = {
            'token': f"Bearer {msg.get('token','0')}",
            'region': msg.get('lockRegion','0'),
            'server_url': msg.get('serverUrl','0'),
            'expires_at': time.time() + 25200
        }

async def initialize_tokens():
    tasks = [create_jwt(r) for r in PRIORITY_REGIONS]
    await asyncio.gather(*tasks, return_exceptions=True)

async def get_token_info(region: str) -> Tuple[str, str, str]:
    info = cached_tokens.get(region)
    if info and time.time() < info['expires_at']:
        return info['token'], info['region'], info['server_url']
    await create_jwt(region)
    info = cached_tokens[region]
    return info['token'], info['region'], info['server_url']

async def GetAccountInformation(uid, unk, region, endpoint):
    payload = await json_to_proto(json.dumps({'a': uid, 'b': unk}), main_pb2.GetPlayerPersonalShow())
    data_enc = aes_cbc_encrypt(Config.MAIN_KEY, Config.MAIN_IV, payload)
    token, lock, server = await get_token_info(region)
    headers = {
        'User-Agent': Config.USER_AGENT, 
        'Connection': "Keep-Alive", 
        'Accept-Encoding': "gzip",
        'Content-Type': "application/octet-stream", 
        'Expect': "100-continue",
        'Authorization': token, 
        'X-Unity-Version': Config.UNITY_VERSION, 
        'X-GA': "v1 1",
        'ReleaseVersion': Config.RELEASE_VERSION
    }
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(server + endpoint, data=data_enc, headers=headers)
        if resp.status_code == 200 and resp.content:
            return json.loads(json_format.MessageToJson(decode_protobuf(resp.content, AccountPersonalShow_pb2.AccountPersonalShowInfo)))
        return None

async def fetch_for_region(uid, region):
    try:
        data = await GetAccountInformation(uid, "7", region, "/GetPlayerPersonalShow")
        if data and data.get("basicInfo") and data["basicInfo"].get("nickname"):
            return region, data
    except Exception: pass
    return None, None

async def auto_detect_region_and_data(uid):
    tasks = [fetch_for_region(uid, r) for r in PRIORITY_REGIONS]
    for future in asyncio.as_completed(tasks):
        region, data = await future
        if region and data:
            return region, data
    return None, None

def format_response(data, is_banned):
    if not isinstance(data, dict): data = {}
        
    basic_info = data.get("basicInfo") or {}
    profile_info = data.get("profileInfo") or {}
    clan_info = data.get("clanBasicInfo") or {}
    captain_info = data.get("captainBasicInfo") or {}
    pet_info = data.get("petInfo") or {}
    social_info = data.get("socialInfo") or {}
    credit_info = data.get("creditScoreInfo") or {}

    create_ts = basic_info.get("createAt", "0")
    login_ts = basic_info.get("lastLoginAt", "0")
    current_level = basic_info.get("level", 0)
    current_exp = basic_info.get("exp", 0)
    
    level_progress = calculate_level_progress(current_exp, current_level)

    result = {
        "DeveloperInfo": {
            "Developer": "Riduanul Islam",
            "TelegramBot": "https://t.me/RiduanFFBot",
            "TelegramChannel": "https://t.me/RiduanOfficialBD"
        },
        "PlayerInfo": {
            "AccountName": basic_info.get("nickname", "N/A"),
            "AccountId": social_info.get("accountId", "N/A"),
            "AccountLevel": current_level,
            "AccountLikes": basic_info.get("liked", 0),
            "AccountEXP": current_exp,
            "AccountRegion": basic_info.get("region", "N/A"),
            "Gender": str(social_info.get("gender", "N/A")).replace("Gender_", ""),
            "Language": str(social_info.get("language", "N/A")).replace("Language_", ""),
            "AccountAvatarId": basic_info.get("headPic", 0),
            "AccountBannerId": basic_info.get("bannerId", 0),
            "AccountBPBadges": basic_info.get("badgeCnt", 0),
            "AccountBPID": basic_info.get("badgeId", 0),
            "AccountSeasonId": basic_info.get("seasonId", 0),
            "Title": basic_info.get("title", 0),
            "RankShow": social_info.get("rankShow", "N/A"),
            "AccountType": basic_info.get("accountType", 0),
            "ReleaseVersion": basic_info.get("releaseVersion", "N/A"),
            "Signature": social_info.get("signature", "N/A")
        },
        "LevelProgressInfo": level_progress if level_progress else {},
        "AccountAgeInfo": {
            "AccountAge": get_detailed_time_diff(create_ts),
            "AccountCreateDate": format_timestamp(create_ts),
            "AccountCreateTimestamp": create_ts
        },
        "BanCheckInfo": {
            "BanStatus": "Account Banned" if is_banned else "Not Banned",
            "BanDuration": get_detailed_time_diff(login_ts) if is_banned else "N/A"
        },
        "PlayerRankInfo": {
            "BrRankPoint": basic_info.get("rankingPoints", 0), "BrMaxRank": basic_info.get("maxRank", 0),
            "CsRankPoint": basic_info.get("csRankingPoints", 0), "CsMaxRank": basic_info.get("csMaxRank", 0),
            "ShowBrRank": basic_info.get("showBrRank", False), "ShowCsRank": basic_info.get("showCsRank", False)
        },
        "PetInfo": {
            "PetId": pet_info.get("id", 0), "PetLevel": pet_info.get("level", 0), "PetExp": pet_info.get("exp", 0),
            "IsSelected": pet_info.get("isSelected", False), "SelectedSkillId": pet_info.get("selectedSkillId", 0),
            "SkinId": pet_info.get("skinId", 0)
        },
        "EquippedItemsInfo": {
            "EquippedWeapon": basic_info.get("weaponSkinShows", []),
            "EquippedOutfit": profile_info.get("clothes", []),
            "EquippedSkills": profile_info.get("equipedSkills", [])
        },
        "GuildInfo": {
            "GuildName": clan_info.get("clanName", "N/A"), "GuildID": str(clan_info.get("clanId", "N/A")),
            "GuildLevel": clan_info.get("clanLevel", 0), "GuildMember": clan_info.get("memberNum", 0),
            "GuildCapacity": clan_info.get("capacity", 0), "GuildOwner": str(clan_info.get("captainId", "N/A"))
        },
        "GuildLeaderInfo": {
            "LeaderName": captain_info.get("nickname", "N/A"), "LeaderId": captain_info.get("accountId", "N/A"),
            "LeaderLevel": captain_info.get("level", 0), "LeaderLikes": captain_info.get("liked", 0),
            "LeaderExp": captain_info.get("exp", 0), "LeaderAvatarId": captain_info.get("headPic", 0),
            "LeaderBannerId": captain_info.get("bannerId", 0), "LeaderBadgeCount": captain_info.get("badgeCnt", 0),
            "LeaderBadgeId": captain_info.get("badgeId", 0), "LeaderBrRankPoint": captain_info.get("rankingPoints", 0),
            "LeaderBrMaxRank": captain_info.get("maxRank", 0), "LeaderCsRankPoint": captain_info.get("csRankingPoints", 0),
            "LeaderCsMaxRank": captain_info.get("csMaxRank", 0), "LeaderTitle": captain_info.get("title", 0),
            "LeaderPinId": captain_info.get("pinId", 0), "LeaderEquippedWeapon": captain_info.get("weaponSkinShows", []),
            "LeaderCreateDate": format_timestamp(captain_info.get("createAt")),
            "LeaderCreateTime": captain_info.get("createAt", "0"),
            "LeaderLastLoginDate": format_timestamp(captain_info.get("lastLoginAt")),
            "LeaderLastLogin": captain_info.get("lastLoginAt", "0")
        },
        "CreditScoreInfo": {
            "CreditScore": credit_info.get("creditScore", 100), "RewardState": credit_info.get("rewardState", "N/A"),
            "PeriodicSummaryEndDate": format_timestamp(credit_info.get("periodicSummaryEndTime")),
            "PeriodicSummaryEndTime": credit_info.get("periodicSummaryEndTime", "0")
        }
    }
    return result

@app.errorhandler(Exception)
def handle_exception(e):
    if isinstance(e, HTTPException): return jsonify({"error": e.description}), e.code
    return jsonify({"error": str(e)}), 500

@app.route('/')
def root_guide():
    return jsonify({
        "DeveloperInfo": {
            "Developer": "Riduanul Islam",
            "TelegramBot": "https://t.me/RiduanFFBot",
            "TelegramChannel": "https://t.me/RiduanOfficialBD"
        },
        "API_Usage_Guide": {
            "Status": "Active",
            "Message": "Welcome to Riduan FF Info API! Auto-detects region and includes Level Progress, Account Age & Ban Check.",
            "API_Format": {
                "Get_Player_Info": "/playerinfo?uid=[uid]"
            },
            "ExampleUsage": "/playerinfo?uid=2764669166"
        }
    }), 200

@app.route('/playerinfo')
def get_account_info():
    uid = request.args.get('uid')
    if not uid: return jsonify({"error": "Please provide UID."}), 400
    try:
        region, raw_data = run_async(auto_detect_region_and_data(uid))
        if not region or not raw_data: 
            return jsonify({"error": "Player not found in any supported region or invalid UID."}), 404
        
        is_banned = run_async(check_ban_status_garena(uid))
        
        formatted = format_response(raw_data, is_banned)
        return jsonify(formatted), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/refresh', methods=['GET', 'POST'])
def refresh_tokens_endpoint():
    try:
        run_async(initialize_tokens())
        return jsonify({'message': 'Tokens refreshed successfully.'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=Config.PORT, debug=Config.DEBUG)
