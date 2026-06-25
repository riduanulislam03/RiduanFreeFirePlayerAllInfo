import os
import base64
import game_version  # গেম ভার্সনের ফাইল ইম্পোর্ট করা হলো

class Config:
    # ডিফল্ট পোর্ট এবং সেটিংস
    PORT = int(os.environ.get("PORT", 5000))
    DEBUG = os.environ.get("DEBUG", "False").lower() == "true"
    
    # ক্রিপ্টোগ্রাফি কি (Keys)
    MAIN_KEY = base64.b64decode(os.environ.get("MAIN_KEY", "WWcmdGMlREV1aDYlWmNeOA=="))
    MAIN_IV = base64.b64decode(os.environ.get("MAIN_IV", "Nm95WkRyMjJFM3ljaGpNJQ=="))
    
    # গেম কনফিগারেশন - game_version.py থেকে ডাটা নেওয়া হচ্ছে
    RELEASE_VERSION = game_version.RELEASE_VERSION
    UNITY_VERSION = game_version.UNITY_VERSION
    CLIENT_VERSION = game_version.CLIENT_VERSION
    
    # ডায়নামিক ইউজার এজেন্ট তৈরি করা হচ্ছে game_version.py এর ভ্যালু ব্যবহার করে
    USER_AGENT = f"Dalvik/2.1.0 (Linux; U; {game_version.ANDROID_OS_VERSION}; {game_version.USER_AGENT_MODEL} Build/RKQ1.211119.001)"
    
    # রিজিয়ন সেটিংস
    SUPPORTED_REGIONS = {"IND", "BR", "US", "SAC", "NA", "SG", "RU", "ID", "TW", "VN", "TH", "ME", "PK", "CIS", "BD", "EU"}
    
    # ক্রিডেনশিয়ালস (Credentials)
    ACCOUNTS = {
        "IND": "uid=4356917206&password=FD5364ADEF5CABF22B54D82235F5572C2AF42B65EC799CEC90FD9E4B3E32A318",
        "BD": "uid=4343645299&password=C5C216587364AD7247730F433CABA4A5C91C6889BCCC2A4D8105E3D7297B5CE2",
        "ME": "uid=4571117089&password=C36429E131AAD3CDE6FBE4E6DBB58D424C3A9762763633B3E57AD668C05DFB21"
    }

    @staticmethod
    def get_account(region):
        r = region.upper()
        
        # ১. যদি রিজিয়নটি সরাসরি ACCOUNTS ডিকশনারিতে থাকে, তবে সেটি রিটার্ন করবে
        if r in Config.ACCOUNTS:
            return Config.ACCOUNTS[r]
            
        # ২. কিছু নির্দিষ্ট রিজিয়নের জন্য ফলব্যাক (Optional)
        if r in {"BR", "US", "SAC"}:
            return Config.ACCOUNTS.get("OTHER", Config.ACCOUNTS.get("IND"))
        
        # ৩. যদি কোনো রিজিয়ন ম্যাচ না করে, তবে ডিফল্ট হিসেবে IND এর আইডি ব্যবহার করবে
        return Config.ACCOUNTS.get("IND")

