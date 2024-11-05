import pika
import json
import time


def send_message(rabbitmq_host, rabbitmq_port, rabbitmq_username, rabbitmq_password, vhost, queue_name, message):
    credentials = pika.PlainCredentials(rabbitmq_username, rabbitmq_password)
    parameters = pika.ConnectionParameters(
        host=rabbitmq_host,
        port=rabbitmq_port,
        virtual_host=vhost,
        credentials=credentials
    )

    # Establish connection to RabbitMQ
    connection = pika.BlockingConnection(parameters)
    channel = connection.channel()

    # Declare the queue (this will not cause an error if the queue already exists)
    channel.queue_declare(queue=queue_name, durable=True)

    # Clear the queue before sending new messages
    channel.queue_purge(queue=queue_name)

    # Send the message to the queue
    channel.basic_publish(
        exchange='',
        routing_key=queue_name,
        body=json.dumps(message).encode('utf-8'),  # Encode the string to bytes
        properties=pika.BasicProperties(
            delivery_mode=2,  # Make the message persistent
        )
    )

    print(f"消息已发送到队列 {queue_name}: {message}")


def continuously_send_messages(rabbitmq_host, rabbitmq_port, rabbitmq_username, rabbitmq_password, vhost):
    while True:
        # Construct custom message
        os_test = {
            "osDynData": {
                "maxRPM": 0,
                "orderRPM": 0,
                "orderRudder": 0,
                "shipCos": 0,
                "shipHdg": 0,
                "shipPosLat": 31,
                "shipPosLon": 121,
                "shipRot": 0,
                "shipSpd": 15,  # n mile
            },
            "osStaData": {
                "shipBreadth": 40,
                "shipLength": 60,
                "shipDraft": 5,
                "shipTn_S": 100,  # s
                "shipTn_P": 100,  # s
            }
        }

        ts_test = {
            "tsData": [
                {
                    "aisShipMmsi": 420002933,
                    "shipName": "YinHe",
                    "shipLength": 160,
                    "shipCos": 250,
                    "shipHdg": 0,
                    "shipPosLat": 31.03,
                    "shipPosLon": 121.04,
                    "shipSpd": 23
                },
                # {
                #     "aisShipMmsi": 420002931,
                #     "shipName": "YinHe",
                #     "shipLength": 160,
                #     "shipCos": 315,
                #     "shipHdg": 0,
                #     "shipPosLat": 30.995,
                #     "shipPosLon": 121.04,
                #     "shipSpd": 20
                # },
                {
                    "aisShipMmsi": 420002932,
                    "shipName": "YinHe",
                    "shipLength": 160,
                    "shipCos": 180,
                    "shipHdg": 0,
                    "shipPosLat": 31.03,
                    "shipPosLon": 120.96,
                    "shipSpd": 15
                }
            ]
        }
        all_ship = {
            "os_ship": os_test,
            "ts_ship": ts_test
        }

        # os_test = json.dumps(os_test, ensure_ascii=False)
        # ts_test = json.dumps(ts_test, ensure_ascii=False)
        # Send data
        send_message(rabbitmq_host, rabbitmq_port, rabbitmq_username, rabbitmq_password, vhost, 'all_ship', all_ship)

        time.sleep(1)  # Sleep for 1 second before sending the next message


if __name__ == "__main__":
    # Replace with your RabbitMQ connection parameters
    rabbitmq_host = '172.16.2.198'
    rabbitmq_port = 5672
    rabbitmq_username = 'guest'
    rabbitmq_password = 'guest'
    vhost = '/'

    continuously_send_messages(rabbitmq_host, rabbitmq_port, rabbitmq_username, rabbitmq_password, vhost)
