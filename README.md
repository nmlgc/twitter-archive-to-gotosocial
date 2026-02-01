*This script is based on **[KevinPayravi's Mastodon importer](https://github.com/KevinPayravi/twitter-archive-to-mastodon)**, which in turn was heavily derived from **[lucahammer's fediporter](https://github.com/lucahammer/fediporter)** Python Notebook. Thanks to everyone for the simple, no-nonsense foundation.*

----

# twitter-archive-to-gotosocial

This is a Python3 script you can use to import your [Twitter archive](https://help.twitter.com/en/managing-your-account/how-to-download-your-twitter-archive) into a GoToSocial instance you have API access to.
It assumes that you own the instance and have disabled rate limits by setting `advanced-rate-limit-requests` to `0`.
Progress is persisted in the form of a tweet→toot mapping in `ids_dict.json`, allowing the import to be arbitrarily aborted and resumed.

When migrating archived Tweets to GoToSocial, this script will do the following:
* Upload media, including videos
* Optionally scraping alt text of images from the web frontend of a self-hosted Nitter instance
* t.co short URLs are replaced with their targets
* Replace @username with @username@twitter.com
* Threads are recreated as threads, though this is fragile; threads may sometimes have missing posts

Limitations:
* ⚠️ Private Twitter Circle tweets will become public toots!
* I have no idea what happens if the script comes across a poll
* Edit history isn't imported

Using this script, I was successfully able to import 2,000+ tweets from all the way back in 2015.

Note that I don't plan to actively maintain or expand this script, but feel free to open PRs.

### Running

#### Configs

Near the top of `import.py` are some variables you need to update:
* `API_BASE_URL` is the URL of your GoToSocial instance (e.g. `https://example.com`)
* `GTS_ACCESS_TOKEN` is your private API access token you need to post toots. You can get a token by [following the documented authentication flow](https://docs.gotosocial.org/en/latest/api/authentication/) and specifying the `write` scope.
* `DATA_DIR` is the location of your unzipped Twitter archive. Needs a trailing slash.
* `MEDIA_DIR` is the location of your Twitter archive's media folder (`/tweets_media`). Needs a trailing slash.
* `TWITTER_USERNAME` is your Twitter username (no @). This is used to track your threads.
* `NITTER_BASE_URL` is the optional URL of a Nitter instance, which will be used for web-scraping
  any data that Twitter demonstrably stores but does not include in your data archive. Currently,
  this category only includes alt text for images.
  Someone from the EU should probably try suing Twitter for this rather selective interpretation of
  Art. 20 GDPR…\
  Since both the official <https://nitter.net> instance and all other tested [public instances]
  prevent scraping in one way or another, this must point to a self-hosted instance without such
  protections.

#### Dependencies
Have Python3 and Pip installed. Install the following packages using pip:

* `beautifulsoup4` (for Nitter scraping)
* `requests`

#### Run
After updating the configs and installing the dependencies, simply run `python3 import.py` and hopefully it works!

The script will output Tweet data as it runs.

[public instances]: https://github.com/zedeus/nitter/wiki/Instances
