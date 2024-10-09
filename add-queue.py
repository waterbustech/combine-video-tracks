import pika
import json

# RabbitMQ connection parameters
rabbitmq_host = 'localhost'
rabbitmq_port = 5672
rabbitmq_user = 'guest'
rabbitmq_password = 'guest'

credentials = pika.PlainCredentials(rabbitmq_user, rabbitmq_password)
parameters = pika.ConnectionParameters(host=rabbitmq_host, port=rabbitmq_port, credentials=credentials)

# Connect to RabbitMQ
connection = pika.BlockingConnection(parameters)
channel = connection.channel()

# Declare the processing queue (sending queue)
channel.queue_declare(queue='processing', durable=True)

# Declare the results queue (receiving queue)
channel.queue_declare(queue='results', durable=True)

# Example message for 'processing' queue
message = {
    "record_id": "record_12345",
    "meeting_start_time": "2024-10-07T10:00:00",
    "participants": [
        {
            "name": "Alice",
            "start_time": "2024-10-07T10:00:00",
            "end_time": "2024-10-07T10:10:00",
            "video_file_path": "examples/video1.webm"
        },
        {
            "name": "Bob",
            "start_time": "2024-10-07T10:02:00",
            "end_time": "2024-10-07T10:12:00",
            "video_file_path": "examples/video2.webm"
        },
        {
            "name": "Charlie",
            "start_time": "2024-10-07T10:04:00",
            "end_time": "2024-10-07T10:14:00",
            "video_file_path": "examples/video3.webm"
        },
        {
            "name": "Charlie1",
            "start_time": "2024-10-07T10:05:00",
            "end_time": "2024-10-07T10:11:00",
            "video_file_path": "examples/video3.webm"
        },
        {
            "name": "Eve",
            "start_time": "2024-10-07T10:06:00",
            "end_time": "2024-10-07T10:16:00",
            "video_file_path": "examples/video4.webm"
        },
    ]
}

# Publish the message to 'processing' queue
channel.basic_publish(
    exchange='',
    routing_key='processing',
    body=json.dumps(message),
    properties=pika.BasicProperties(
        delivery_mode=2,  # Make message persistent
    )
)

print("Sent message to 'processing' queue.")

# Callback function to handle messages from 'results' queue
def on_result_message(ch, method, properties, body):
    result = json.loads(body)
    print(f"Received result: {result}")

    # Acknowledge the message
    ch.basic_ack(delivery_tag=method.delivery_tag)

# Set up the consumer to listen to the 'results' queue
channel.basic_consume(queue='results', on_message_callback=on_result_message)

print("Waiting for messages from 'results' queue...")
channel.start_consuming()

# Close the connection (this won't be reached because start_consuming is blocking)
# connection.close()
