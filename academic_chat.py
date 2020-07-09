#!/usr/bin/env python

import json
import os
import time

import tweepy


class Config:
    def __init__(self, api, block_accounts, block_words, dryrun):
        """
        :param api: Tweepy API object
        :param block_accounts: list[str] -- account names to block
        :param block_words: list[str] -- words/phrases to block
        :param dryrun: bool -- whether to actually retweet things
        """
        self.api = api
        self.block_accounts = block_accounts
        self.block_words = block_words
        self.dryrun = dryrun


def search(config, query):
    return tweepy.Cursor(config.api.search,
                         q=query,
                         result_type="recent",
                         lang='en').items(1)


def retweet(config, tweet):
    if config.dryrun:
        print("Dry run - not retweeting")
    else:
        tweet.retweet()


def try_search_and_retweet(config, query):
    """
    :param config: Config
    :param query: str -- Twitter query
    :return: bool: whether the search generated a successful retweet
    """
    for tweet in search(config, query):
        if tweet.user.screen_name in config.block_accounts:
            # don't share
            print("Avoiding spam user:", tweet.user.screen_name)
            continue

        # information for output logs
        print("username:", tweet.user.screen_name)

        if any(word in tweet.text for word in config.block_words):
            # don't share
            print("spam found")
            continue

        print("tweet content:", tweet.text)
        print("length of original tweet:", len(tweet.text))
        try:
            retweet(config, tweet)
            return True
        except tweepy.TweepError as e:
            print("retweet error:", e)
            if 'Failed to send request' in e.reason:
                time.sleep(240)
            return False


def search_loop(config, query_list):
    """
    :param config: Config
    :param query_list: list[str] -- list of Twitter queries to try
    :return: never returns
    """
    print("query list:", query_list)
    while True:
        successful_query_idx = None
        for i, query in enumerate(query_list):
            if try_search_and_retweet(config, query):
                successful_query_idx = i
                break
        if successful_query_idx is None:
            print("Did {} searches but found nothing to share - sleeping for 600 seconds (10 mins)".format(len(query_list)))
            time.sleep(600)
        else:
            print("Found something to share on search {} - sleeping for 800 seconds (15 mins)".format(successful_query_idx))
            time.sleep(800)


def main(env):
    twitter_handle = env["TWITTER_HANDLE"]
    twitter_secret_file = env.get("TWITTER_SECRET_FILE") or "config/secret.json"
    never_share_accounts_file = env.get("TWITTER_NEVER_SHARE_ACCOUNTS_FILE") or "config/never_share_accounts.txt"
    never_share_words_file = env.get("TWITTER_NEVER_SHARE_WORDS_FILE") or "config/never_share_words.txt"
    dryrun = env.get("TWITTER_DRYRUN") == "1"
    direct_query_file = env.get("TWITTER_DIRECT_QUERY_FILE") or "config/direct.txt"
    indirect_query_file = env.get("TWITTER_INDIRECT_QUERY_FILE") or "config/indirect.txt"

    # insert Twitter Dev App security keys and tokens
    with open(twitter_secret_file) as f:
        secret = json.load(f)
    auth = tweepy.OAuthHandler(secret["consumer_key"], secret["consumer_secret"])
    auth.set_access_token(secret["access_token"], secret["access_token_secret"])
    authorized_api = tweepy.API(auth, wait_on_rate_limit=True)

    # add troll/abusive/exploitative accounts to this list never to share them
    with open(never_share_accounts_file) as f:
        never_share_accounts = set(l.strip() for l in f.readlines())

    # if found tweet contains any of these strings, don't share (block
    # inappropriate content)
    with open(never_share_words_file) as f:
        never_share_words = set(l.strip() for l in f.readlines())

    config = Config(
        api=authorized_api,
        block_accounts=never_share_accounts,
        block_words=never_share_words,
        dryrun=dryrun,
    )

    # set search content
    # we prioritize tweets that have tagged our account directly (search 1)
    with open(direct_query_file) as f:
        direct = ["(" + l.strip() + ")" for l in f.readlines()]
    query1 = " OR ".join(direct) + " -filter:retweets AND -filter:replies AND -from:" + twitter_handle

    # if we don't find tweets that included our tag then we search for general
    # hashtags (search 2)
    with open(indirect_query_file) as f:
        indirect = ["(" + l.strip() + ")" for l in f.readlines()]
    query2 = " OR ".join(indirect) + " -filter:retweets AND -filter:replies AND -from:" + twitter_handle

    search_loop(config, [query1, query2])


if __name__ == "__main__":
    main(os.environ)

