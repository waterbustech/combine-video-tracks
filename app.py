from dotenv import load_dotenv
import os
import json
from flask import Flask, send_from_directory, jsonify, request
from threading import Thread
import pika
from moviepy.editor import (
    VideoFileClip,
    clips_array,
    concatenate_videoclips,
    ColorClip,
    TextClip,
    CompositeVideoClip,
)
from datetime import datetime
import uuid
import numpy as np
from PIL import Image

load_dotenv()

rabbitmq_host = os.getenv('RABBITMQ_HOST', 'localhost')
rabbitmq_port = int(os.getenv('RABBITMQ_PORT', 5672))
rabbitmq_user = os.getenv('RABBITMQ_USER', 'guest')
rabbitmq_password = os.getenv('RABBITMQ_PASSWORD', 'guest')
flask_port = int(os.getenv('FLASK_PORT', 5986))
domain_name = os.getenv('DOMAIN_NAME', 'http://localhost:5986')

app = Flask(__name__)

output_dir = os.path.abspath("output_videos")
temp_dir = os.path.abspath("temp")

os.makedirs(temp_dir, exist_ok=True)


@app.route('/uploads', methods=['POST'])
def upload_videos():
    """Handle multiple video file uploads and save them with UUID names in .webm format."""
    if 'files' not in request.files:
        return jsonify({"error": "No files provided"}), 400

    uploaded_files = request.files.getlist('files')
    saved_files = []

    for uploaded_file in uploaded_files:
        if uploaded_file.filename == '':
            continue

        # Generate a unique UUID for each file and save it with a .webm extension
        unique_filename = f"{uuid.uuid4()}.webm"
        save_path = os.path.join(temp_dir, unique_filename)

        try:
            uploaded_file.save(save_path)
            saved_files.append(
                {"original_name": uploaded_file.filename, "saved_name": unique_filename})
        except Exception as e:
            print(f"Error saving file {uploaded_file.filename}: {e}")
            return jsonify({"error": f"Failed to save file {uploaded_file.filename}"}), 500

    return jsonify({"files": saved_files}), 200


@app.route('/video/<filename>')
def serve_video(filename):
    """Serve the processed video file by URL."""
    return send_from_directory(output_dir, filename)


@app.route('/thumbnail/<filename>')
def serve_thumbnail(filename):
    """Serve the generated thumbnail by URL."""
    return send_from_directory(output_dir, filename)


class ParticipantTrack:
    def __init__(self, videoPath, startTime, endTime, name):
        self.videoPath = videoPath
        self.startTime = startTime
        self.endTime = endTime
        self.name = name


def determine_layout(num_tracks):
    """Determine the layout based on the number of video tracks."""
    if num_tracks == 0:
        return []
    elif num_tracks == 1:
        return [[0]]
    elif num_tracks == 3:
        return [[0, 1, 2]]
    elif num_tracks <= 4:
        return [[0, 1], [2, 3]]
    elif num_tracks <= 9:
        return [[0, 1, 2], [3, 4, 5], [6, 7, 8]]
    elif num_tracks <= 16:
        return [
            [0, 1, 2, 3],
            [4, 5, 6, 7],
            [8, 9, 10, 11],
            [12, 13, 14, 15],
        ]
    else:
        return [
            [0, 1, 2, 3, 4],
            [5, 6, 7, 8, 9],
            [10, 11, 12, 13, 14],
            [15, 16, 17, 18, 19],
        ]


def create_text_clip(text, fontsize=24, color='white', padding=10):
    text_clip = TextClip(text, fontsize=fontsize,
                         color=color, font='Arial-Bold')
    text_width, text_height = text_clip.size
    background = ColorClip(
        size=(text_width + 2 * padding, text_height + 2 * padding),
        color=(0, 0, 0),
    ).set_duration(text_clip.duration)
    text_clip = text_clip.set_position((padding, padding))
    return CompositeVideoClip([background, text_clip])


def combine_tracks(participant_tracks, output_path):
    clips = []
    max_end_time = max(track.endTime for track in participant_tracks)
    placeholder_clip = ColorClip(size=(640, 480), color=(0, 0, 0), duration=1)

    preloaded_clips = {}
    for track in participant_tracks:
        if track.videoPath not in preloaded_clips:
            try:
                preloaded_clips[track.videoPath] = VideoFileClip(
                    track.videoPath).resize(newsize=(640, 480))
            except Exception as e:
                print(f"Error loading video {track.videoPath}: {e}")
                preloaded_clips[track.videoPath] = placeholder_clip

    for current_time in range(max_end_time + 1):
        current_clips = []

        for track in participant_tracks:
            if track.startTime <= current_time <= track.endTime:
                subclip_start = current_time - track.startTime
                subclip_end = subclip_start + 1
                video_duration = preloaded_clips[track.videoPath].duration
                if subclip_end > video_duration:
                    subclip_end = video_duration
                try:
                    clip = preloaded_clips[track.videoPath].subclip(
                        subclip_start, subclip_end)
                except Exception as e:
                    print(f"Error creating subclip for {track.videoPath}: {e}")
                    clip = placeholder_clip

                text_clip = create_text_clip(track.name).set_position(
                    ('left', 'bottom')).set_duration(clip.duration)
                clip_with_text = CompositeVideoClip([clip, text_clip])
                current_clips.append(clip_with_text)

        if not current_clips:
            current_clips.append(placeholder_clip)

        layout = determine_layout(len(current_clips))
        arranged_clips = []

        for row in layout:
            arranged_row_clips = [current_clips[i]
                                  for i in row if i < len(current_clips)]
            if arranged_row_clips:
                arranged_clips.append(arranged_row_clips)

        max_row_length = max(len(row) for row in layout) if layout else 0
        for i in range(len(arranged_clips)):
            while len(arranged_clips[i]) < max_row_length:
                arranged_clips[i].append(placeholder_clip)

        if arranged_clips:
            final_frame = clips_array(arranged_clips).set_duration(1)
            clips.append(final_frame)

    try:
        final_video = concatenate_videoclips(clips, method="compose")
        final_video.write_videofile(output_path, codec='libx264')
    except Exception as e:
        print(f"Error during video concatenation: {e}")
    finally:
        for clip in preloaded_clips.values():
            clip.close()

    return float(final_video.duration)


def generate_thumbnail(video_path, thumbnail_path, time=1):
    try:
        clip = VideoFileClip(video_path)
        frame = clip.get_frame(time)
        image = Image.fromarray(frame)
        image.save(thumbnail_path)
        clip.close()
        return thumbnail_path
    except Exception as e:
        print(f"Error generating thumbnail: {e}")
        return None


def convert_datetime_to_seconds(start_datetime, end_datetime, meeting_start_datetime):
    startTime = int(
        (start_datetime - meeting_start_datetime).total_seconds() / 60)
    endTime = int((end_datetime - meeting_start_datetime).total_seconds() / 60)
    return startTime, endTime


def create_participant_tracks(participant_data, meeting_start_datetime):
    tracks = []
    for participant in participant_data:
        try:
            name = participant['name']
            start_datetime = datetime.fromisoformat(participant['start_time'])
            end_datetime = datetime.fromisoformat(participant['end_time'])
            videoPath = participant['video_file_path']
            startTime, endTime = convert_datetime_to_seconds(
                start_datetime, end_datetime, meeting_start_datetime)
            tracks.append(ParticipantTrack(
                videoPath, startTime, endTime, name))
        except Exception as e:
            print(f"Error creating ParticipantTrack: {e}")
    return tracks


def process_record(record_id, participant_data, meeting_start_datetime, output_dir):
    try:
        tracks = create_participant_tracks(
            participant_data, meeting_start_datetime)
        output_dir = os.path.abspath(output_dir)
        output_video_path = os.path.join(output_dir, f"{record_id}.mp4")
        duration = combine_tracks(tracks, output_video_path)

        thumbnail_path = os.path.join(output_dir, f"{record_id}_thumbnail.png")
        generate_thumbnail(output_video_path, thumbnail_path)

        result = {
            "record_id": record_id,
            "duration": duration,
            "video_url": f"{domain_name}/video/{os.path.basename(output_video_path)}",
            "thumbnail_url": f"{domain_name}/thumbnail/{os.path.basename(thumbnail_path)}"
        }

        return result
    except Exception as e:
        print(f"Error processing record {record_id}: {e}")
        return None


def callback(ch, method, properties, body):
    try:
        message = json.loads(body)
        record_id = message['record_id']
        participant_data = message['participants']
        meeting_start_str = message['meeting_start_time']
        meeting_start_datetime = datetime.fromisoformat(meeting_start_str)

        # Construct the full video path for each participant by joining temp_dir and saved_name
        for participant in participant_data:
            participant['video_file_path'] = os.path.join(
                temp_dir, participant['video_file_path'])

        output_dir = "output_videos"
        os.makedirs(output_dir, exist_ok=True)

        result = process_record(
            record_id, participant_data, meeting_start_datetime, output_dir)

        if result:
            result_json = json.dumps(result)
            channel.basic_publish(
                exchange='',
                routing_key='results',
                body=result_json,
                properties=pika.BasicProperties(
                    delivery_mode=2,
                )
            )
            print(
                f"Processed record_id: {record_id} and sent to 'results' queue with URLs.")

            # After successfully processing the record, remove the files from temp_dir
            for participant in participant_data:
                video_file_path = participant['video_file_path']
                if os.path.exists(video_file_path):
                    os.remove(video_file_path)
                    print(f"Removed file: {video_file_path}")
        else:
            print(f"Failed to process record_id: {record_id}")

        ch.basic_ack(delivery_tag=method.delivery_tag)
    except Exception as e:
        print(f"Error in callback: {e}")
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)


def start_flask_server():
    app.run(host='0.0.0.0', port=flask_port)


if __name__ == "__main__":
    credentials = pika.PlainCredentials(rabbitmq_user, rabbitmq_password)
    parameters = pika.ConnectionParameters(
        host=rabbitmq_host, port=rabbitmq_port, credentials=credentials)

    flask_thread = Thread(target=start_flask_server)
    flask_thread.start()

    connection = pika.BlockingConnection(parameters)
    channel = connection.channel()

    channel.queue_declare(queue='processing', durable=True)
    channel.queue_declare(queue='results', durable=True)

    channel.basic_qos(prefetch_count=1)
    channel.basic_consume(queue='processing', on_message_callback=callback)

    print('Waiting for messages in "processing" queue. To exit press CTRL+C')
    try:
        channel.start_consuming()
    except KeyboardInterrupt:
        print('Interrupted')
        channel.stop_consuming()
    finally:
        connection.close()
