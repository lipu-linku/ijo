import requests
import pandas as pd
from io import StringIO
import re
from datetime import datetime as dt
import numpy as np


YEAR = "2024"
PREV = "2023"

def get_last_year():
    series = pd.read_csv("2023.csv", index_col=0)["value"]
    return series
    # return dict(zip(df.word, df.value))


def get_category(value: float) -> str:
    # Uses raw numbers, so doesn't support su
    # Which was grandfathered into uncommon via estimation
    if pd.isna(value):
        return "sandbox"
    value = round(value)
    if value >= 90:
        return "core"
    if value >= 60:
        return "common"
    if value >= 30:
        return "uncommon"
    if value >= 5:
        return "obscure"
    return "sandbox"


def get_scores(df: pd.DataFrame) -> pd.Series:
    # Generate a word list sorted by mean score
    scores = df.loc[:, df.columns.str.contains("w_")].mean()
    # Make word names easier to read
    scores.index = scores.index.map(lambda x: x.split("_")[-1])
    # Reduce floating point precision
    scores = scores.map(lambda x: round(x*100, 2))
    return scores


def countif(df: pd.DataFrame, value: float) -> pd.Series:
    # Generate a word list sorted by mean score
    scores = df.loc[:, df.columns.str.contains("w_")]
    # Count matching values across columns
    scores = scores.transpose().map(lambda x: x == value).transpose().sum()
    # # Make word names easier to read
    scores.index = scores.index.map(lambda x: x.split("_")[-1])
    return scores


SOURCES = [
    # Main sheet
    "https://docs.google.com/spreadsheets/d/e/2PACX-1vTCokTZJsRWYIs7N8IFUBAF-V0lEKAd6F9BP2YLW8SlG-dhuhJAW5m_oILRjiOhUXrjOv-ClxbaTGXi/pub?gid=71465298&single=true&output=csv",
    # No-Google account sheet
    "https://docs.google.com/spreadsheets/d/e/2PACX-1vTCokTZJsRWYIs7N8IFUBAF-V0lEKAd6F9BP2YLW8SlG-dhuhJAW5m_oILRjiOhUXrjOv-ClxbaTGXi/pub?gid=1152794091&single=true&output=csv",
]

COLUMN_ALIASES = {
    "Timestamp": "meta_time",
    "How did you find out about this poll?": "meta_source",
    "How long have you spoken toki pona?": "meta_xp",
    "Did you also take part in the 2023 word survey?": "meta_lastyear",
    "You can leave some identification (e.g. account name) so I can ask you if I'm confused by your responses": "meta_name",
    "ale and ali ": "w_oblig_",
    "core words (117 total, minus ale) ": "w_core_",
    "common, uncommon words (24 total) ": "w_oblig_",
    "obscure words (37 total) ": "w_obsc_",
    "candidate words (18 total) ": "w_obsc_",
    "any extra words you would mark as \"I use it\":": "writein_use",
    "any extra words you would mark as \"I use in some situations\":": "writein_someuse",
    "any extra words you would mark as \"I avoid in most situations\":": "writein_avoid",
    "If you have any closing thoughts, please write them below!": "meta_comment",
}

RESPONSE_ALIASES = {
    "I use it": 1,
    # "I use in some situations": 1,
    # "I use it but not always": 1,
    # "I avoid in most situations": 0,
    # "I avoid using it when possible": 0,
    "I use in some situations": 2/3,
    "I use it but not always": 2/3,
    "I avoid in most situations": 1/3,
    "I avoid using it when possible": 1/3,
    "I never use it": 0,
}

START = dt.fromisoformat("2024-08-09")

df = pd.concat([
    pd.read_csv(StringIO(requests.get(source).content.decode('utf8')))
    for source in SOURCES
])

# Alias columns for ease of use
for k, v in COLUMN_ALIASES.items():
    df.rename(columns=lambda x: re.sub(re.escape(k), v, x), inplace=True)
df.rename(columns=lambda x: re.sub(r"[\[\]]", "", x), inplace=True)

# Interpret timestamp
df.meta_time = df.meta_time.map(lambda t: dt.strptime(t, "%d/%m/%Y %H:%M:%S"))

# Remove rows submitted during testing
# df.drop(df[df.meta_time < START].index, inplace=True)
# No need because they work fine actually!

# Drop questions that aren't relevant data:
# Questions for guiding form user flow
df = df.loc[:, df.columns.str.contains("_")]

# Sort columns by name
df = df.reindex(sorted(df.columns), axis=1)

# Replace text responses with a scale from 0 to 1
df = df.replace(RESPONSE_ALIASES)

# Fill in columns that have default options
df.loc[:, df.columns.str.contains("w_core_")] = \
    df.loc[:, df.columns.str.contains("w_core_")].replace({np.nan: 1.0})
df.loc[:, df.columns.str.contains("w_obsc_")] = \
    df.loc[:, df.columns.str.contains("w_obsc_")].replace({np.nan: 0.0})

# Delete rows that erroneously report using fake words
df = df.drop(df[(df.w_obsc_mejuse > 0) | (df.w_obsc_nujosi > 0)].index)

# Try deleting rows that are too recent
# df = df.drop(df[(df.meta_xp == "0-3 months")].index)

# Try deleting rows that don't identify themselves
# df = df.drop(df[(df.meta_name == "")].index)

# Build df with scores.
# Easily expandable for other kinds of scoring

scores = pd.DataFrame({
    "use: yes": countif(df, 1),
    "use: mostly yes": countif(df, 2/3),
    "use: mostly no": countif(df, 1/3),
    "use: no": countif(df, 0),
    PREV: get_last_year(),
    YEAR: get_scores(df),
    "time: > 5 years": get_scores(df.query('meta_xp==">5 years"')),
    "time: > 2 years": get_scores(df.query('meta_xp=="2-5 years"')),
    "time: > 6 months": get_scores(df.query('meta_xp=="1-2 years"')),
    "time: > 3 months": get_scores(df.query('meta_xp=="3-6 months"')),
    "time: < 3 months": get_scores(df.query('meta_xp=="0-3 months"')),
    "dict-readers": get_scores(df.query(
        'meta_source=="nimi.li" | meta_source=="linku.la"'
    )),
    "sunoers": get_scores(df.query('meta_source=="suno pi toki pona"')),
    "redditors": get_scores(df.query('meta_source=="Reddit"')),
    "discorders": get_scores(df.query(
        'meta_source=="Discord (ma pona)"'
        '| meta_source=="Discord (kama pona)"'
        '| meta_source=="Discord (any other server)"'
    )),
}).sort_values(PREV, ascending=False).sort_values(YEAR, ascending=False)

# Highlight words that passed a threshold
scores[f"{PREV}_cat"] = scores[PREV].apply(get_category)
scores[f"{YEAR}_cat"] = scores[YEAR].apply(get_category)
scores["cat_changed"] = scores.apply(
    lambda x: x[f"{YEAR}_cat"] != x[f"{PREV}_cat"],
    axis=1,
)

scores.to_csv("scores-2024.csv", sep="\t")
