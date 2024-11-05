import pika
import json
import time
import redis


def setup_fanout_exchange_and_queue(rabbitmq_host, rabbitmq_port, rabbitmq_username, rabbitmq_password, vhost, exchange_name, queue_name, dead_letter_exchange='dead_letter_exchange', message_ttl=60000):
    credentials = pika.PlainCredentials(rabbitmq_username, rabbitmq_password)
    parameters = pika.ConnectionParameters(
        host=rabbitmq_host,
        port=rabbitmq_port,
        virtual_host=vhost,
        credentials=credentials
    )

    connection = pika.BlockingConnection(parameters)
    channel = connection.channel()

    # 声明 Dead Letter Exchange
    channel.exchange_declare(exchange=dead_letter_exchange, exchange_type='fanout', durable=False)

    # 声明 fanout 交换机
    channel.exchange_declare(exchange=exchange_name, exchange_type='fanout', durable=False)

    # 声明队列,并设置 x-dead-letter-exchange 和 x-message-ttl 参数
    channel.queue_declare(queue=queue_name, durable=False, arguments={
        'x-dead-letter-exchange': dead_letter_exchange,
        'x-dead-letter-routing-key': 'dead',
        'x-message-ttl': 2000
    })

    # 绑定队列到交换机
    channel.queue_bind(exchange=exchange_name, queue=queue_name)

    print(f"Queue '{queue_name}' is now bound to exchange '{exchange_name}'.")

    connection.close()


def send_message_to_fanout_exchange(rabbitmq_host, rabbitmq_port, rabbitmq_username, rabbitmq_password, vhost, exchange_name, message):
    """
    往交换机发送数据
    :param rabbitmq_host:
    :param rabbitmq_port:
    :param rabbitmq_username:
    :param rabbitmq_password:
    :param vhost:
    :param exchange_name:
    :param message:
    :return:
    """
    credentials = pika.PlainCredentials(rabbitmq_username, rabbitmq_password)
    parameters = pika.ConnectionParameters(
        host=rabbitmq_host,
        port=rabbitmq_port,
        virtual_host=vhost,
        credentials=credentials
    )

    connection = pika.BlockingConnection(parameters)
    channel = connection.channel()

    # Declare a fanout exchange with durable set to False
    channel.exchange_declare(
        exchange=exchange_name,
        exchange_type='fanout',
        durable=False,  # Set durable to False
        arguments={'x-message-ttl': 2000}
    )

    # Publish a message to the fanout exchange
    channel.basic_publish(
        exchange=exchange_name,
        routing_key='',  # routing_key is ignored for fanout exchanges
        body=json.dumps(message).encode('utf-8'),  # Encode message
        properties=pika.BasicProperties(
            delivery_mode=1,  # Make message transient (not persistent). 2 means persistent.
        )
    )

    # print(f"Message sent to fanout exchange '{exchange_name}': {message}")

    connection.close()


def purge_queue(rabbitmq_host, rabbitmq_port, rabbitmq_username, rabbitmq_password, vhost, queue_name):
    credentials = pika.PlainCredentials(rabbitmq_username, rabbitmq_password)
    parameters = pika.ConnectionParameters(host=rabbitmq_host, port=rabbitmq_port, virtual_host=vhost,credentials=credentials)

    connection = pika.BlockingConnection(parameters)
    channel = connection.channel()

    # 声明队列
    channel.queue_declare(queue=queue_name, durable=False, arguments={
        'x-message-ttl': 2000
    })

    # 清空队列
    channel.queue_purge(queue=queue_name)
    # print(f"队列 '{queue_name}' 已被清空。")

    connection.close()


def continuously_send_messages(rabbitmq_host, rabbitmq_port, rabbitmq_username, rabbitmq_password, vhost, os_ship, ts_ships):
    """
    定义数据
    :param rabbitmq_host:
    :param rabbitmq_port:
    :param rabbitmq_username:
    :param rabbitmq_password:
    :param vhost:
    :return:
    """
    while True:
        # Construct custom message
        # Send data
        send_message_to_fanout_exchange(rabbitmq_host, rabbitmq_port, rabbitmq_username, rabbitmq_password, vhost,
                                        exchange_name='os_ship_exchange',
                                        message=os_ship
                                        )
        send_message_to_fanout_exchange(rabbitmq_host, rabbitmq_port, rabbitmq_username, rabbitmq_password, vhost,
                                        exchange_name='ts_ship_exchange',
                                        message=ts_ships
                                        )
        # send_message_to_fanout_exchange(rabbitmq_host, rabbitmq_port, rabbitmq_username, rabbitmq_password, vhost,
        #                                 exchange_name='OTHER_TO_COLAVO_EXCHANGE',
        #                                 message=ts_ships
        #                                 )
        # send_message_to_fanout_exchange(rabbitmq_host, rabbitmq_port, rabbitmq_username, rabbitmq_password, vhost,
        #                                 exchange_name='OWNER_TO_COLAVO_EXCHANGE',
        #                                 message=os_ship
        #                                 )
        time.sleep(2)  # Sleep for 1 second before sending the next message


def send_ships_to_redis_as_strings(redis_host, redis_port, redis_password, db_ts_index, db_os_index, ts_ships_data, os_ship_data):
    """
    将每艘船的数据字典存储为单独的键值对在 Redis 中以 `other:<ship_id>` 命名。

    参数:
    - redis_host: Redis 服务器的地址
    - redis_port: Redis 服务器的端口
    - redis_password: Redis 服务器的密码
    - db_index: 指定的 Redis 数据库索引（例如，10）
    - ships_data: 包含船数据的字典
    """
    try:
        # 连接到 Redis 服务器
        client_ts = redis.StrictRedis(
            host=redis_host,
            port=redis_port,
            password=redis_password,
            db=db_ts_index,  # 使用指定的数据库索引
            decode_responses=True  # 确保返回值为字符串而不是字节
        )
        client_os = redis.StrictRedis(
            host=redis_host,
            port=redis_port,
            password=redis_password,
            db=db_os_index,  # 使用指定的数据库索引
            decode_responses=True  # 确保返回值为字符串而不是字节
        )

        for ship_id, ship_data in ts_ships_data.items():
            client_ts.set(f"other:{ship_id}", json.dumps(ship_data))
            print(f"数据为船只 {ship_id} 已插入/更新")
        for key, value in os_ship_data.items():
            client_os.set(f"{key}", value)

    except redis.RedisError as e:
        print(f"Redis error: {e}")


def main():
    # Replace with your RabbitMQ connection parameters
    rabbitmq_host = '172.16.2.198'
    rabbitmq_port = 5672
    rabbitmq_username = 'guest'
    rabbitmq_password = 'guest'
    vhost = '/'
    # Replace with your Redis connection parameters
    redis_host = '172.16.2.198'
    redis_port = 6379
    redis_password = 'zdiai@123'
    db_ts_index = 10
    db_os_index = 2
    setup_fanout_exchange_and_queue(
        rabbitmq_host,
        rabbitmq_port,
        rabbitmq_username,
        rabbitmq_password,
        vhost,
        exchange_name='os_ship_exchange',
        queue_name='os_ship'
    )
    setup_fanout_exchange_and_queue(
        rabbitmq_host,
        rabbitmq_port,
        rabbitmq_username,
        rabbitmq_password,
        vhost,
        exchange_name='ts_ship_exchange',
        queue_name='ts_ship'
    )
    # =================================================================================================================
    # 设置船舶动态参数
    # 数据传入，经度、纬度、
    os = [113.8471524081029, 22.091319518529886, 10, 0]
    ts1 = [os[0] + 0.04, os[1] + 0.035, 14.7, -90]
    ts2 = [os[0] + 0.012, os[1] - 0.01, 18, -20]
    ts3 = [os[0] + 0.021, os[1] - 0.01, 10, 0]
    ts5 = [os[0] - 0.02, os[1] - 0.015, 8, 20]
    ts6 = [os[0] + 0.02, os[1] - 0.015, 8, -40]
    # =================================================================================================================
    # redis 上传数据
    os_ship_data = {"Hdt": os[3], "Lat": os[1], "Lat_AIS": os[1], "Lon": os[0], "Lon_AIS": os[0], "SPEED_KNOTS": os[2],
                    "TtlCargo": 172715.6, "cog_AIS": os[3], "fuelConsumperNM": 0, "heading_AIS": os[3],
                    "ivsRunningTime": 300, "meCond": -1, "rot_AIS": 1.3, "shipingCond": -1, "speed_AIS": os[2],
                    "timestamp_AIS": 1726206666}
    ts_ships_data = {
        "420000002": {"mmsi": 420000002, "heading": ts2[3], "sog": ts2[2], "Lon": ts2[0],
                      "speed": ts2[2], "rot": 0.0, "cog": ts2[3], "t1": 1727956689, "Lat": ts2[1],
                      "status": 15, "BCR": 0.7258277748824671, "BCT": 5.378858231659014, "CPA": 0.42238717801529624,
                      "BRG": 258.5635957639443, "TCPA": 3.359442119072459, "RNG": 0.6196090777308249,
                      "shipname": "TestShip2"},
        # "420000003": {"mmsi": 420000003, "heading": ts3[3], "sog": ts3[2], "Lon": ts3[0],
        #               "speed": ts3[2], "rot": 0.0, "cog": ts3[3], "t1": 1727956689, "Lat": ts3[1],
        #               "status": 15, "BCR": 0.7258277748824671, "BCT": 5.378858231659014, "CPA": 0.42238717801529624,
        #               "BRG": 258.5635957639443, "TCPA": 3.359442119072459, "RNG": 0.6196090777308249,
        #               "shipname": "TestShip3"},
        # "420000001": {"mmsi": 420000001, "heading": ts1[3], "sog": ts1[2], "Lon": ts1[0],
        #               "speed": ts1[2], "rot": 0.0, "cog": ts1[3], "t1": 1727956689, "Lat": ts1[1],
        #               "status": 15, "BCR": 0.7258277748824671, "BCT": 5.378858231659014, "CPA": 0.42238717801529624,
        #               "BRG": 258.5635957639443, "TCPA": 3.359442119072459, "RNG": 0.6196090777308249,
        #               "shipname": "TestShip1"},
        # "420000005": {"mmsi": 420000005, "heading": ts5[3], "sog": ts5[2], "Lon": ts5[0],
        #               "speed": ts5[2], "rot": 0.0, "cog": ts5[3], "t1": 1727956689, "Lat": ts5[1],
        #               "status": 15, "BCR": 0.7258277748824671, "BCT": 5.378858231659014, "CPA": 0.42238717801529624,
        #               "BRG": 258.5635957639443, "TCPA": 3.359442119072459, "RNG": 0.6196090777308249,
        #               "shipname": "TestShip5"},
        # "420000006": {"mmsi": 420000006, "heading": ts6[3], "sog": ts6[2], "Lon": ts6[0],
        #               "speed": ts6[2], "rot": 0.0, "cog": ts6[3], "t1": 1727956689, "Lat": ts6[1],
        #               "status": 15, "BCR": 0.7258277748824671, "BCT": 5.378858231659014, "CPA": 0.42238717801529624,
        #               "BRG": 258.5635957639443, "TCPA": 3.359442119072459, "RNG": 0.6196090777308249,
        #               "shipname": "TestShip6"}
    }
    # =================================================================================================================
    # rabbitmq上传数据
    os_ship = {"osDynData": {"maxRPM": 0, "orderRPM": 0, "orderRudder": 0, "shipCos": os[3], "shipHdg": os[3],
                             "shipPosLat": os[1], "shipPosLon": os[0], "shipRot": 0, "shipSpd": os[2]},
               "osStaData": {"shipBreadth": 40, "shipLength": 60, "shipDraft": 5, "shipTn_S": 100, "shipTn_P": 100}
               }
    ts_ships = {
                "tsData": [
                           {"aisShipMmsi": 420000002, "shipName": "YinHe2", "shipLength": 100, "shipCos": ts2[3],
                            "shipHdg": ts2[3], "shipPosLat": ts2[1], "shipPosLon": ts2[0], "shipSpd": ts2[2]},
                           {"aisShipMmsi": 420000003, "shipName": "YinHe3", "shipLength": 100, "shipCos": ts3[3],
                            "shipHdg": ts3[3], "shipPosLat": ts3[1], "shipPosLon": ts3[0], "shipSpd": ts3[2]},
                           {"aisShipMmsi": 420000001, "shipName": "YinHe1", "shipLength": 100, "shipCos": ts1[3],
                            "shipHdg": ts1[3], "shipPosLat": ts1[1], "shipPosLon": ts1[0], "shipSpd": ts1[2]},
                           {"aisShipMmsi": 420000005, "shipName": "YinHe5", "shipLength": 100, "shipCos": ts5[3],
                            "shipHdg": ts5[3], "shipPosLat": ts5[1], "shipPosLon": ts5[0], "shipSpd": ts5[2]},
                           {"aisShipMmsi": 420000006, "shipName": "YinHe6", "shipLength": 100, "shipCos": ts6[3],
                            "shipHdg": ts6[3], "shipPosLat": ts6[1], "shipPosLon": ts6[0], "shipSpd": ts6[2]}
                           ]
                }
    # ==================================================================================================================
    # 发送数据
    # send_ships_to_redis_as_strings(redis_host, redis_port, redis_password, db_ts_index, db_os_index, ts_ships_data, os_ship_data)
    continuously_send_messages(rabbitmq_host, rabbitmq_port, rabbitmq_username, rabbitmq_password, vhost, os_ship, ts_ships)
    # purge_queue(rabbitmq_host, rabbitmq_port, rabbitmq_username, rabbitmq_password, vhost,
    #             queue_name="ts_ship"
    #             )
    purge_queue(rabbitmq_host, rabbitmq_port, rabbitmq_username, rabbitmq_password, vhost,
                queue_name="os_ship"
                )


if __name__ == "__main__":
    main()


