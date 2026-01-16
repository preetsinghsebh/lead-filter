{\rtf1\ansi\ansicpg1252\cocoartf2822
\cocoatextscaling0\cocoaplatform0{\fonttbl\f0\fswiss\fcharset0 Helvetica;}
{\colortbl;\red255\green255\blue255;}
{\*\expandedcolortbl;;}
\paperw11900\paperh16840\margl1440\margr1440\vieww11520\viewh8400\viewkind0
\pard\tx720\tx1440\tx2160\tx2880\tx3600\tx4320\tx5040\tx5760\tx6480\tx7200\tx7920\tx8640\pardirnatural\partightenfactor0

\f0\fs24 \cf0 from fastapi import FastAPI, UploadFile, File\
import pandas as pd\
\
app = FastAPI()\
\
HOT_KEYWORDS = ["manager", "procurement", "purchasing", "director", "head"]\
COLD_KEYWORDS = ["student", "intern", "assistant", "trainee"]\
\
@app.post("/upload")\
async def upload(file: UploadFile = File(...)):\
    df = pd.read_csv(file.file, engine="python")\
\
    statuses = []\
    for title in df["Job Title"].fillna(""):\
        t = title.lower()\
        status = "Warm"\
        if any(w in t for w in HOT_KEYWORDS):\
            status = "Hot"\
        if any(w in t for w in COLD_KEYWORDS):\
            status = "Cold"\
        statuses.append(status)\
\
    df["Lead Status"] = statuses\
    df.to_csv("output.csv", index=False)\
    return \{"message": "Processed. output.csv created"\}}