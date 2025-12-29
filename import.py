from pathlib import Path
from tqdm import tqdm
from time import sleep
from urllib.parse import urlparse
import datetime
import json
import re
import requests

# UPDATE THESE VARIABLES
API_BASE_URL = "https://example.com"
GTS_ACCESS_TOKEN = ""
DATA_DIR = "../data/"  # Unzipped twitter data export
MEDIA_DIR = "../data/tweets_media/"  # media folder of twitter data export
TWITTER_USERNAME = "YourTwitterUsername"

IDS_DICT_FN = "ids_dict.json"

# Test GoToSocial bearer token
url = f"{API_BASE_URL}/api/v1/apps/verify_credentials"
HEADERS = {"Authorization": f"Bearer {GTS_ACCESS_TOKEN}"}
r = requests.get(url, headers=HEADERS)

print(r)

def post_status(data):
    HEADERS = {
        "Authorization": f"Bearer {GTS_ACCESS_TOKEN}",
        "Idempotency-Key": data["scheduled_at"],
    }
    url = f"{API_BASE_URL}/api/v1/statuses"
    r = requests.post(url, data=data, headers=HEADERS)
    return r.json()


def load_tweets():
    with open(DATA_DIR + "tweets.js", "r", encoding="utf8") as f:
        raw = f.read()
    raw = raw.replace("window.YTD.tweets.part0 = ", "")
    tweets = json.loads(raw)
    tweets = [tweet["tweet"] for tweet in tweets]
    tweets = sorted(tweets, key=lambda d: int(d["id"]))
    return tweets


def load_ids_dict():
    try:
        with open(IDS_DICT_FN, "r") as f:
            return json.load(f)
    except:
        return {}


def save_ids_dict():
    with open(IDS_DICT_FN, "w") as f:
        f.write(json.dumps(
            ids_dict,
            ensure_ascii=False,
            indent='\t',
            separators=(',', ': '),
            sort_keys=True
        ))


def to_timestamp(created_at):
    timestamp = datetime.datetime.strptime(created_at, "%a %b %d %X %z %Y").isoformat(
        timespec="seconds"
    )
    return timestamp


def replace_urls(tweet):
    if "full_text" in tweet:
        text = tweet["full_text"]
    else:
        text = tweet["text"]
    if "entities" in tweet and "urls" in tweet["entities"]:
        for url in tweet["entities"]["urls"]:
            text = text.replace(url["url"], url["expanded_url"])
    return text


def replace_usernames(text):
    text = re.sub(r"(\B\@[A-Za-z0-9_]{1,15})(\:)?", r"\1@twitter.com\2", text)
    return text


def tweet_to_toot(tweet):
    toot = {
        "status": replace_usernames(replace_urls(tweet)),
        "visibility": "public",
        "scheduled_at": to_timestamp(tweet["created_at"]),
        "language": tweet["lang"],
    }
    return toot


tweets = load_tweets()
ids_dict = load_ids_dict()
counter = 0

for tweet in tqdm(tweets):
    print("Tweet number " + str(counter))
    counter += 1
    if tweet["id"] in ids_dict:
        # was already posted, we can skip it
        continue
    print(tweet)
    try:
        toot = tweet_to_toot(tweet)
        if "media" in tweet["entities"]:
            # upload media to append to the post
            media_ids = []
            for media in tweet["extended_entities"]["media"]:
                image_path = None
                if "video_info" in media:
                    for variant in media['video_info']['variants']:
                        url = urlparse(variant['url'])
                        variant_path = f"{MEDIA_DIR}{tweet['id']}-{url.path.split('/')[-1]}"
                        if Path(variant_path).is_file():
                            image_path = variant_path
                            break
                else:
                    image_path = f"{MEDIA_DIR}{tweet['id']}-{media['media_url_https'].split('/')[-1]}"
                file = open(image_path, "rb")
                data = file.read()
                url = f"{API_BASE_URL}/api/v2/media"
                files = {
                    "file": (image_path, data, "application/octet-stream")}
                r = requests.post(url, files=files, headers=HEADERS)
                json_data = r.json()
                media_ids.append(json_data["id"])
                toot["status"] = toot["status"].replace(media["url"], "")
            toot["media_ids[]"] = media_ids
        if (
            "in_reply_to_screen_name" in tweet
            and tweet["in_reply_to_screen_name"] == TWITTER_USERNAME
        ):
            # if Tweet is part of a thread, get ID if previous post
            try:
                toot["in_reply_to_id"] = ids_dict.get(
                    tweet["in_reply_to_status_id"]
                )
            except:
                print("======= FAILED!! ======= Error: ")
                print(err)
                pass
        posted = post_status(toot)
        print("POSTED!!")
        print(posted)
        ids_dict[tweet["id"]] = posted["id"]
        save_ids_dict()
    except Exception as err:
        print("======= FAILED!! ======= Error: ")
        print(err)
        pass

save_ids_dict()
