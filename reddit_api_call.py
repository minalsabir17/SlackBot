import praw
import pandas as pd
import numpy as np


def reddit_api_call_func(reddit):
    comments_data = []
    subreddit = reddit.subreddit("jerseycity")  # Change to your subreddit of choice
    for submission in subreddit.new(limit=1000):  # You can change the limit
        submission.comments.replace_more(limit=0)  # To flatten comment tree and remove 'MoreComments' objects
        for comment in submission.comments.list():
            comments_data.append({
                'Post_ID': submission.id,
                'Post_Title': submission.title,
                'Comment_ID': comment.id,
                'Comment_Body': comment.body,
                'Comment_Author': str(comment.author),
                'Score': comment.score,
                'Created': comment.created_utc
            })

    comments_df = pd.DataFrame(comments_data)

    
    return comments_df
    # subjects = ["mayor", "mussab", "ali", "boe"]
    # filtered_df = pd.DataFrame()

    # for subject in subjects:
    #     matches = comments_df[comments_df['Comment_Body'].str.lower().str.contains(subject.lower(), na=False)]
    #     filtered_df = pd.concat([filtered_df, matches], ignore_index=True)

    # filtered_df







