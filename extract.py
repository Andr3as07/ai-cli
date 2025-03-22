#!/usr/bin/env python
import os
import re
import sys
import urllib.request

import docx
import dotenv
import isodate
import pymupdf
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from markdownify import markdownify
from youtube_transcript_api import YouTubeTranscriptApi

from ai import get_client


def get_video_id(url):
    # Extract video ID from URL
    pattern = r"(?:https?:\/\/)?(?:www\.)?(?:youtube\.com\/(?:[^\/\n\s]+\/\S+\/|(?:v|e(?:mbed)?)\/|\S*?[?&]v=)|youtu\.be\/)([a-zA-Z0-9_-]{11})"
    match = re.search(pattern, url)
    return match.group(1) if match else None


def file_exists(filename):
    if not os.path.isfile(filename):
        sys.stderr.write(f"File '{filename}' not found\n")
        return False
    return True


def from_txt(filename):
    if not file_exists(filename):
        return None
    with open(filename, "r") as f:
        return f.read()


def from_pdf(filename):
    if not file_exists(filename):
        return None
    doc = pymupdf.open(filename)
    return "\n".join([page.get_text() for page in doc])


def from_doc(filename):
    if not file_exists(filename):
        return None
    import win32com.client

    word = win32com.client.Dispatch("Word.Application")
    word.visible = False
    wb = word.Documents.Open(os.path.abspath(filename))
    doc = word.ActiveDocument
    result = doc.Range().Text
    doc.Close(False)
    word.Quit()
    return result


def from_docx(filename):
    if not file_exists(filename):
        return None
    doc = docx.Document(filename)
    fullText = []
    for para in doc.paragraphs:
        fullText.append(para.text)
    return "\n".join(fullText)


def from_html(html):
    if file_exists(html):
        html = from_txt(html)
    return markdownify(
        html,
        strip=["script", "style"],
    )


def from_http(address):
    req = urllib.request.Request(address, headers={"User-Agent": "AI-CLI Client/1.0.0"})
    page = urllib.request.urlopen(req)
    if page.getcode() != 200:
        sys.stderr.write(f"HTTP error {page.getcode()}\n")
        return None
    return page.read().decode("utf-8")


def from_youtube(path):
    api_key = os.getenv("YOUTUBE_API_KEY")
    if not api_key:
        sys.stderr.write("YOUTUBE_API_KEY not set\n")
        return
    video_id = get_video_id(path)
    if video_id is None:
        sys.stderr.write(f"Failed to extract video ID from '{path}'\n")
        return None
    if not video_id:
        sys.stderr.write(f"Invalid video ID '{video_id}'\n")
        return None

    try:
        # Initialize the YouTube API client
        youtube = build("youtube", "v3", developerKey=api_key)

        # Call the YouTube API to get the transcript

        # Get video details
        video_response = (
            youtube.videos().list(id=video_id, part="contentDetails,snippet").execute()
        )

        # Extract video duration and convert to minutes
        duration_iso = video_response["items"][0]["contentDetails"]["duration"]
        duration_seconds = isodate.parse_duration(duration_iso).total_seconds()
        duration_minutes = round(duration_seconds / 60)

        # Get transcript
        try:
            transcript_list = YouTubeTranscriptApi.get_transcript(
                video_id,
                languages=["en", "de"],
            )
            transcript_text = " ".join([item["text"] for item in transcript_list])
        except Exception as e:
            sys.stderr.write(f"Failed to get transcript: {e}\n")
            return None

        result = f"{video_id}\n{duration_minutes}\n{transcript_text}"

        return result

    except HttpError as e:
        sys.stderr.write(f"Failed to initialize YouTube API: {e}\n")
        return None


def from_audio(path):
    client, error = get_client()
    if error:
        sys.stderr.write(f"Failed to create OpenAI client: {error}\n")
        return None

    audio_file = None
    try:
        audio_file = open(path, "rb")
    except:
        sys.stderr.write(f"Failed to read audio file: {path}\n")
        return None

    model = os.getenv("AI_TRANSCRIPTION_MODEL", "whisper-1")

    try:
        transcript = client.audio.transcriptions.create(
            model=model,
            file=audio_file,
        )
        return transcript.text
    except Exception as e:
        sys.stderr.write(f"Failed to transcribe audio: {e}\n")
        return None

    return None


def extract(path):
    try:
        ext = os.path.splitext(path)[1].lower()
        if get_video_id(path) is not None:
            return from_youtube(path)
        elif path.startswith("http://") or path.startswith("https://"):
            result = from_http(path)
            if "<!DOCTYPE html" in result or "<html" in result:
                result = from_html(result)
            return result
        if ext in [".txt", ".md", ".ini", ".csv", ".json", ".xml", ".yaml", ".yml"]:
            return from_txt(path)
        elif ext in [".html", ".htm"]:
            return from_html(path)
        elif ext in [".pdf"]:
            return from_pdf(path)
        elif ext in [".docx"]:
            return from_docx(path)
        elif ext in [".doc"]:
            return from_doc(path)
        elif ext in [
            ".flac",
            ".m4a",
            ".mp3",
            ".mp4",
            ".mpeg",
            ".mpga",
            ".oga",
            ".ogg",
            ".wav",
            ".webm",
        ]:
            return from_audio(path)
        else:
            sys.stderr.write(f"Unsupported file type '{path}'\n")
            return None
    except Exception as e:
        sys.stderr.write(f"Error: {e}\n")
        return None


def main():
    dotenv.load_dotenv(os.path.dirname(os.path.realpath(__file__)) + "/.env")

    if len(sys.argv) != 2:
        sys.stderr.write(f"Usage: {sys.argv[0]} <path>\n")
        exit(1)
    path = sys.argv[1]
    result = extract(path)
    if result is None:
        exit(1)
    print(result)


if __name__ == "__main__":
    main()
