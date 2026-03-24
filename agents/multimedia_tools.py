import os
import base64
import cv2
from typing import Dict, Any
from openai import OpenAI
from django.conf import settings
from agents.control import ToolDefinition


def recognize_image_tool(args: Dict[str, Any]) -> str:
    """Use GPT-5.4 vision to recognize contents of an image (jpg, png)."""
    path = args.get('path', '')
    prompt = args.get('prompt', 'What is in this image? Provide a detailed description.')

    if not path or not os.path.exists(path):
        return f"Error: File '{path}' not found."

    try:
        # Read and encode image to base64
        with open(path, "rb") as image_file:
            base64_image = base64.b64encode(image_file.read()).decode('utf-8')

        client = OpenAI(api_key=settings.OPENAI_API_KEY)
        response = client.chat.completions.create(
            model="gpt-5.4",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{base64_image}"
                            }
                        },
                    ],
                }
            ],
            max_tokens=500,
        )

        return response.choices[0].message.content
    except Exception as e:
        return f"Error during image recognition: {str(e)}"


def recognize_video_tool(args: Dict[str, Any]) -> str:
    """Use GPT-5.4 vision to recognize contents of a video (mp4) by extracting frames."""
    path = args.get('path', '')
    prompt = args.get('prompt', 'These are frames from a video. What is happening? Provide a summary and details.')
    max_frames = args.get('max_frames', 10)

    if not path or not os.path.exists(path):
        return f"Error: File '{path}' not found."

    try:
        video = cv2.VideoCapture(path)
        total_frames = int(video.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = video.get(cv2.CAP_PROP_FPS)

        if total_frames <= 0:
            return "Error: Could not read frames from video."

        # Sample frames evenly
        interval = max(1, total_frames // max_frames)
        base64_frames = []

        count = 0
        while video.isOpened():
            success, frame = video.read()
            if not success or len(base64_frames) >= max_frames:
                break

            if count % interval == 0:
                _, buffer = cv2.imencode(".jpg", frame)
                base64_frames.append(base64.b64encode(buffer).decode("utf-8"))

            count += 1

        video.release()

        if not base64_frames:
            return "Error: No frames extracted from video."

        client = OpenAI(api_key=settings.OPENAI_API_KEY)

        content = [{"type": "text", "text": prompt}]
        for base64_frame in base64_frames:
            content.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/jpeg;base64,{base64_frame}"
                }
            })

        response = client.chat.completions.create(
            model="gpt-5.4",
            messages=[
                {
                    "role": "user",
                    "content": content,
                }
            ],
            max_tokens=1000,
        )

        return response.choices[0].message.content
    except Exception as e:
        return f"Error during video recognition: {str(e)}"


def recognize_audio_tool(args: Dict[str, Any]) -> str:
    """Use GPT-5.4 to analyze and summarize an audio file, including speech, music, and sounds."""
    path = args.get('path', '')
    prompt = args.get('prompt', 'Analyze this audio file. Describe everything you hear: transcribe any speech, identify any music (genre, instruments, mood), and note any ambient or other sounds.')

    SUPPORTED_FORMATS = ('.wav', '.mp3', '.ogg', '.flac', '.webm', '.m4a', '.mp4', '.aac', '.wma', '.opus')

    if not path or not os.path.exists(path):
        return f"Error: File '{path}' not found."

    ext = os.path.splitext(path)[1].lower()
    if ext not in SUPPORTED_FORMATS:
        return f"Error: Unsupported audio format '{ext}'. Supported formats: {', '.join(SUPPORTED_FORMATS)}"

    converted_path = None
    try:
        # GPT-5.4 audio input only accepts wav and mp3; convert other formats
        if ext in ('.wav', '.mp3'):
            audio_path = path
            audio_format = ext[1:]  # strip the leading dot
        else:
            from pydub import AudioSegment
            audio_segment = AudioSegment.from_file(path)
            converted_path = os.path.splitext(path)[0] + '_temp_converted.wav'
            audio_segment.export(converted_path, format='wav')
            audio_path = converted_path
            audio_format = 'wav'

        with open(audio_path, "rb") as f:
            base64_audio = base64.b64encode(f.read()).decode('utf-8')

        client = OpenAI(api_key=settings.OPENAI_API_KEY)
        response = client.chat.completions.create(
            model="gpt-5.4-audio-preview",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "input_audio",
                            "input_audio": {
                                "data": base64_audio,
                                "format": audio_format
                            }
                        }
                    ],
                }
            ],
            max_tokens=1000,
        )

        return response.choices[0].message.content
    except Exception as e:
        return f"Error during audio recognition: {str(e)}"
    finally:
        if converted_path and os.path.exists(converted_path):
            os.remove(converted_path)


RECOGNIZE_IMAGE_DEFINITION = ToolDefinition(
    name="recognize_image",
    description="Analyze the contents of an image (jpg, png) using GPT-5.4 vision. Provide a path and optional prompt.",
    parameters={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "The path to the image file."
            },
            "prompt": {
                "type": "string",
                "description": "What you want to know about the image."
            }
        },
        "required": ["path"]
    },
    function=recognize_image_tool
)


RECOGNIZE_VIDEO_DEFINITION = ToolDefinition(
    name="recognize_video",
    description="Analyze the contents of a video (mp4) using GPT-5.4 vision by extracting frames. Provide a path and optional prompt.",
    parameters={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "The path to the video file."
            },
            "prompt": {
                "type": "string",
                "description": "What you want to know about the video."
            },
            "max_frames": {
                "type": "integer",
                "description": "Maximum number of frames to extract and analyze (default 10)."
            }
        },
        "required": ["path"]
    },
    function=recognize_video_tool
)


RECOGNIZE_AUDIO_DEFINITION = ToolDefinition(
    name="recognize_audio",
    description="Analyze an audio file (wav, mp3, ogg, flac, webm, m4a, mp4, aac, wma, opus) using GPT-5.4. Identifies and summarizes speech, music, and ambient sounds in the file.",
    parameters={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "The path to the audio file."
            },
            "prompt": {
                "type": "string",
                "description": "What you want to know about the audio. Default analyzes speech, music, and sounds."
            }
        },
        "required": ["path"]
    },
    function=recognize_audio_tool
)
