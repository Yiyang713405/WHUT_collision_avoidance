import pika


# 定义处理函数
def process_messages(ch, method, properties, body1, body2):
    # 在这里处理从两个队列取出的数据
    print(body1, body2)
    # 处理完成后,手动确认消息已经消费
    ch.basic_ack(delivery_tag=method.delivery_tag)


# 从两个队列中同时取数据,并调用处理函数
def consume_messages():
    def callback1(ch, method, properties, body):
        process_messages(ch, method, properties, body, None)

    def callback2(ch, method, properties, body):
        process_messages(ch, method, properties, None, body)

    channel.basic_consume(queue='os_ship', on_message_callback=callback1, auto_ack=False)
    channel.basic_consume(queue='ts_ship', on_message_callback=callback2, auto_ack=False)

    print('Waiting for messages. To exit press CTRL+C')
    channel.start_consuming()


if __name__ == "__main__":
    # 连接RabbitMQ
    credentials = pika.PlainCredentials('guest', 'guest')
    connection = pika.BlockingConnection(pika.ConnectionParameters('172.16.2.198', 5672, '/', credentials))
    channel = connection.channel()
    # 声明两个队列
    channel.queue_declare(queue='os_ship')
    channel.queue_declare(queue='ts_ship')
    consume_messages()
