from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from tqdm import tqdm
from typing import List
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
NITTER_BASE_URL = None

IDS_DICT_FN = "ids_dict.json"

# Test GoToSocial bearer token
url = f"{API_BASE_URL}/api/v1/apps/verify_credentials"
HEADERS = {"Authorization": f"Bearer {GTS_ACCESS_TOKEN}"}
r = requests.get(url, headers=HEADERS)


@dataclass
class Poll:
    count: int
    labels: List[str]
    votes: List[int]


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


def url_basename(url: str):
    u = urlparse(url)
    return u.path.split('/')[-1]


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


if NITTER_BASE_URL is not None:
    from bs4 import BeautifulSoup

    def fetch_from_nitter(rel_url: str):
        html = requests.get(f"{NITTER_BASE_URL}{rel_url}")
        return BeautifulSoup(html.content, "html.parser")

    def fetch_alt_text(expanded_url: str, media_url: str):
        bs = fetch_from_nitter(expanded_url.removeprefix("https://x.com"))
        if not bs:
            return ""

        # Also remove the extension to allow imports with re-encoded images.
        basename = Path(url_basename(media_url)).stem

        img = bs.find("img", src=lambda x: basename in x)
        if not img:
            return ""
        return img.get("alt")

    def fetch_poll(status_url: str):
        bs = fetch_from_nitter(status_url)
        if not bs:
            return None
        post = bs.find("div", class_="main-tweet")
        if not post:
            return None
        div = post.find("div", class_="poll")
        if not div:
            return None
        print(status_url)
        info = div.find("span", class_="poll-info")
        if not info:
            return None
        count = float(info.get_text().split()[0])
        labels: List[str] = []
        votes: List[int] = []
        for opt in div.find_all("div", class_="poll-meter"):
            labels.append(
                opt.find("span", class_="poll-choice-option").get_text())
            pct = float(opt.find(
                "span", class_="poll-choice-value").get_text().split("%")[0])
            votes.append(int(round((pct / 100.0) * count)))
        return Poll(int(count), labels, votes)
else:
    def fetch_alt_text(expanded_url: str, media_url: str):
        return None

    def fetch_poll(status_url: str):
        return None


tweets = load_tweets()
ids_dict = load_ids_dict()
counter = 0
tweets.reverse()

for tweet in tqdm(tweets):
    print("Tweet number " + str(counter))
    counter += 1
    if tweet["id"] in ids_dict:
        # was already posted, we can skip it
        continue
    print(tweet)
    toot = tweet_to_toot(tweet)
    poll = fetch_poll(f"/{TWITTER_USERNAME}/status/{tweet["id"]}")
    created_at = datetime.datetime.strptime(
        tweet["created_at"], "%a %b %d %H:%M:%S %z %Y")
    created_at += datetime.timedelta(days=7)
    created_at = created_at.strftime("%Y-%m-%d %H:%M:%S.00000+00:00")
    if "media" in tweet["entities"]:
        # upload media to append to the post
        media_ids = []
        for media in tweet["extended_entities"]["media"]:
            image_path = None
            if "video_info" in media:
                for variant in media['video_info']['variants']:
                    basename = url_basename(variant['url'])
                    variant_path = f"{MEDIA_DIR}{tweet['id']}-{basename}"
                    if Path(variant_path).is_file():
                        image_path = variant_path
                        break
            else:
                image_path = f"{MEDIA_DIR}{tweet['id']}-{media['media_url_https'].split('/')[-1]}"
            alt_text = fetch_alt_text(
                media['expanded_url'], media['media_url_https'])
            data = None
            file = open(image_path, "rb")
            data = file.read()
            url = f"{API_BASE_URL}/api/v2/media"
            files = {
                "file": (image_path, data, "application/octet-stream")}

            data = None
            if alt_text is not None:
                data = {"description": alt_text}
            r = requests.post(url, files=files, data=data, headers=HEADERS)
            json_data = r.json()
            media_ids.append(json_data["id"])
            toot["status"] = toot["status"].replace(media["url"], "")
        toot["media_ids[]"] = media_ids
    if (
        "in_reply_to_screen_name" in tweet
        and tweet["in_reply_to_screen_name"] == TWITTER_USERNAME
    ):
        # if Tweet is part of a thread, get ID if previous post
        toot["in_reply_to_id"] = ids_dict.get(tweet["in_reply_to_status_id"])

    # GoToSocial prevents the creation of backdated statuses with polls:
    #
    #   https://codeberg.org/superseriousbusiness/gotosocial/src/commit/c4f1988a30a013f132f98a84274583305c066c39/internal/processing/status/create.go#L249-L252
    #
    # But if you removed this condition in a custom build of the server, you could at least do the
    # following…
    #
    # if poll:
    #     toot["poll"] = {}
    #     toot["poll"]["options"] = poll.labels
    #     toot["poll"]["expires_in"] = 0
    #
    # …and then construct SQL queries with the returned poll ID (`posted["poll"]["id"]`).
    # See https://rec98.nmlgc.net/blog/2026-03-16#polls-2026-03-16 for more info.

    posted = post_status(toot)
    print("POSTED!!")
    print(posted)

    if poll:
        print(f"Poll results for {tweet['id']} / {posted["id"]}:")
        for (label, votes) in zip(poll.labels, poll.votes):
            print(f"• {votes} {label}")
        print(f"Total votes: {poll.count}")

    ids_dict[tweet["id"]] = posted["id"]
    save_ids_dict()

save_ids_dict()
