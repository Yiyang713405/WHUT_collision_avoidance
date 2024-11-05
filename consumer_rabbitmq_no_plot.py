import numpy as np
from Tools import convert_latlon_to_xy
from Tools import Encounter_scenario_decision_making
from Tools import PointDelete
from service.tanker_VLCC8_L333 import VLCC8L333
import invariant_waypoint_update
import os
from PlanningAlgorithm import bezier_path
from global_land_mask import globe
import traceback
import producer_rabbitmq
import math
import time
import pika
import threading
import json
import copy
# from PlanningAlgorithm import PotentialFieldPlanning
# from PlanningAlgorithm import a_star

ship_param = VLCC8L333()


data_queue = []  # 用于存放从两个队列中获取的数据


def callback(ch, method, properties, body):
    """
    :param ch: 用于和rabbitmq通信的通道
    :param method:传递给mq的队列交换机属性
    :param properties:消息属性以及类型等
    :param body:消息内容
    :return:
    """
    message = json.loads(body)
    data_queue.append(message)  # 将接收的消息添加到data_queue列表，因为算法需要同时传入本船和目标船数据，将接收到的两个队列的数据添加到列表中，传到新的队列方便算法提取使用
    ch.basic_ack(delivery_tag=method.delivery_tag)


def consume_queues(host, port, username, password):
    """
    :param host: 地址
    :param port:端口号
    :param username:用户名
    :param password:密码
    :return:
    """
    credentials = pika.PlainCredentials(username, password)  # 设置用户名和密码
    parameters = pika.ConnectionParameters(host=host, port=port, credentials=credentials)  # 建立连接地址，端口
    connection = pika.BlockingConnection(parameters)
    channel = connection.channel()  # 建立连接

    channel.queue_declare(queue=os_queue_name, durable=False, arguments={
        'x-dead-letter-exchange': dead_letter_exchange,
        'x-dead-letter-routing-key': 'dead',
        'x-message-ttl': 2000
    })
    channel.queue_declare(queue=os_queue_name, durable=False, arguments={
        'x-dead-letter-exchange': dead_letter_exchange,
        'x-dead-letter-routing-key': 'dead',
        'x-message-ttl': 2000
    })
    channel.basic_qos(prefetch_count=1)  # 一次从队列中提取一条消息

    channel.basic_consume(queue=os_queue_name, on_message_callback=callback, auto_ack=False)
    channel.basic_consume(queue=ts_queue_name, on_message_callback=callback, auto_ack=False)  # 开始消费提取队列中的数据

    print('Waiting for messages. To exit press CTRL+C')
    channel.start_consuming()


class ShipData:
    def __init__(self):
        self.os_data = []  # OS 数据
        self.ts_data = []  # TS 数据

    def update_data(self, data_type, data):
        """
        提取消息中算法需要用到的参数数据
        :param data_type: 消息数据的类型，可以理解为字典键值的键名
        :param data: 键值
        :return:
        """
        if data_type == 'os':
            self.os_data = [
                data.get('shipPosLon', None),
                data.get('shipPosLat', None),
                data.get('shipSpd', None),
                data.get('shipCos', None),
            ]
        elif data_type == 'ts':
            self.ts_data = [
                [
                    ship.get('shipPosLon', None),
                    ship.get('shipPosLat', None),
                    ship.get('shipSpd', None),
                    ship.get('shipCos', None),
                    ship.get('shipLength', None),
                    ship.get('aisShipMmsi', None),
                    ship.get('shipName', None)
                ] for ship in data
            ]


def process_ship_data(message, ship_data):
    """
    调用类中的提取函数提取消息中的数据
    :param message: mq传来的数据
    :param ship_data: message中的数据
    :return:
    """
    for i in range(len(message)):
        if 'osDynData' in message[i]:
            ship_data.update_data('os', message[i]['osDynData'])
        if 'tsData' in message[i]:
            ship_data.update_data('ts', message[i]['tsData'])


def calculate_angles(rx, ry):
    """
    计算贝叶斯曲线在起点，中间点和终点的和航向
    :param rx: 轨迹x坐标
    :param ry: 轨迹y坐标
    :return: 三个点的切线角度
    """
    angles = []
    n = len(rx)

    # 起点切线方向
    if n > 1:
        start_tangent = np.array([rx[1] - rx[0], ry[1] - ry[0]])
        start_tangent /= np.linalg.norm(start_tangent)  # 标准化
        angle = np.degrees(np.arctan2(start_tangent[0], start_tangent[1]))  # 以y轴正方向为0°
        angles.append(angle)

        # 中间点切线方向
    if n > 2:
        mid_index = n // 2
        mid_tangent = np.array([rx[mid_index + 1] - rx[mid_index - 1], ry[mid_index + 1] - ry[mid_index - 1]])
        mid_tangent /= np.linalg.norm(mid_tangent)  # 标准化
        angle = np.degrees(np.arctan2(mid_tangent[0], mid_tangent[1]))  # 以y轴正方向为0°
        angles.append(angle)

        # 终点切线方向
    if n > 1:
        end_tangent = np.array([rx[-1] - rx[-2], ry[-1] - ry[-2]])
        end_tangent /= np.linalg.norm(end_tangent)  # 标准化
        angle = np.degrees(np.arctan2(end_tangent[0], end_tangent[1]))  # 以y轴正方向为0°
        angles.append(angle)
    for i in range(len(angles)):
        if angles[i] < 0:
            angles[i] += 360
        if angles[i] == 360:
            angles[i] = 0
    return angles


def append_dict_to_json(file_path, new_data):
    """
    将新的字典数据追加到JSON文件中。
    :param file_path: 存放JSON的文件路径
    :param new_data: 要追加的字典数据
    """
    data_list = []
    # 如果文件存在，读取其内容并反序列化为列表
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as file:
            try:
                data_list = json.load(file)
                if not isinstance(data_list, list):
                    data_list = []
            except json.JSONDecodeError:
                pass
    data_list.append(new_data)
    # 将更新后的列表序列化为JSON格式并写入文件
    with open(file_path, 'w', encoding='utf-8') as file:
        json.dump(data_list, file, ensure_ascii=False, indent=4)
    print(f"新数据已追加到文件：{file_path}")


def process_data():
    """
    数据处理函数，负责将从mq里提取的数据进行处理，算法调用，得出算法计算的结果发送给交互界面
    :return:
    """
    # =================================================================================================================
    # 初始化参数
    combin_message = []  # 用于接收融合两个队列的数据
    invariant_waypoint = []  # 用于存储本船的固定路径点，即实际上本船接下来建议到达的路径点
    m = 1852  # 1 海里 = 1852 米
    invariant_index = [float('inf')]  # 产生固定路径点的风险船索引值，没有风险时索引是inf
    invariant_shipmeet = [0]  # 产生固定路径点的风险船的会遇态势，没有风险时态势为0，会遇态势参照避让算法中的定义，Encounter_scenario_decision_making.py
    navigation_state = 'front'  # 本船当前的航行状态，初始化为直航，根据状态转变为右转或者左转，用来避面轨迹建议轨迹跳变
    os_start_num = 0  # 用来判断是否记录了本船的初始数据，用作后续的船舶数据转换
    os_ship_start = []  # 储存本船的初始位置数据
    last_send_time = time.time()
    while True:
        if data_queue:
            start_time = time.time()  # 记录程序运行开始时间
            message = data_queue.pop(0)  # 获取数据
            combin_message.append(message)  # 添加数据
            if len(combin_message) == 2:  # 列表里有两条数据时开始处理
                ship_data = ShipData()
                process_ship_data(combin_message, ship_data)
                os_ship_data = ship_data.os_data
                ts_ship_data = ship_data.ts_data  # 提取数据中算法需要的数据
                if ts_ship_data and os_ship_data:  # 判断接收的两条数据是否同时包含本船和目标船数据
                    if os_start_num == 0:
                        os_ship_start = os_ship_data
                        os_start_num += 1   # 记录初始状态数据
                    os_data = copy.deepcopy(os_ship_data)
                    ts_data = copy.deepcopy(ts_ship_data)
                    os_start = copy.deepcopy(os_ship_start)  # 复制本船和目标船相关数据，防止循环计算过程中对原始数据的影响
                    # ==========================================================================================================
                    # 获取第一次接收的队列数据作为本船的初始状态
                    os_start = convert_latlon_to_xy.ship_latlon_to_xy(os_start)  # 经纬度转换
                    reference_point_x = os_start[0]
                    reference_point_y = os_start[1]  # 本船的初始状态数据作为参照点
                    os_start[2] = os_start[2] * 0.51444  # 单位转换
                    sog_os_min = 0.5 * os_start[2]  # 本船减速时的最小值
                    x_os_start, y_os_start, sog_os_start, cog_os_start = os_start  # 参数赋值
                    # =====================================================================================================
                    # 读取本船数据
                    os_ship = convert_latlon_to_xy.ship_latlon_to_xy(os_data)
                    os_ship[0] = os_ship[0] - os_start[0]
                    os_ship[1] = os_ship[1] - os_start[1]
                    os_ship[2] = os_ship[2] * 0.51444  # 本船航速以节为单位
                    x_os, y_os, sog_os, cog_os = os_ship
                    if sog_os == 0:
                        combin_message.clear()
                        print("本船航速为0，算法重启中...")
                        continue
                    # ==============================================================================================================
                    # 读取目标船数据
                    ts_ships = []  # 定于空列表存放目标船数据
                    ts_ships_length = []  # 定义空列表存放目标船船长
                    ts_ships_mmsi = []  # 定义空列表存放目标船mmsi
                    ts_ships_name = []  # 定义空列表存放目标船船名
                    for i in range(len(ts_data)):
                        ts_ships.append([])
                    for i in range(len(ts_ships)):
                        if ts_data[i][-3] is not None:
                            ts_ships_length.append(ts_data[i][-3])
                        else:
                            ts_ships_length.append(100)
                        ts_ships_mmsi.append(ts_data[i][-2])
                        ts_ships_name.append(ts_data[i][-1])
                        ts_data[i] = ts_data[i][:-3]
                        ts_ships[i] = convert_latlon_to_xy.ship_latlon_to_xy(ts_data[i])
                        ts_ships[i][2] = ts_ships[i][2] * 0.51444
                        if ts_ships[i][2] == 0:  # 周围目标船风险为0时，手动赋予目标船航速，用以避让，当做静态障碍物避让
                            ts_ships[i][2] += 0.001
                        # # roll_os = 0.1
                    for i in range(len(ts_ships)):  # 转换成相对于初始参考点的位置
                        ts_ships[i][0] = ts_ships[i][0] - os_start[0]
                        ts_ships[i][1] = ts_ships[i][1] - os_start[1]
                    # ===================================================================================================
                    # 计算避碰算法参数
                    (waypoint, cpa, avoid_ship_label, colAvoShipCount, colAvoNegShipCount, colAvoEmgShipCount,
                     osAvoResp, shipMeetProp, shipColAvoProp, shipDCPA, shipTCPA, shipBearing, shipDistance,
                     os_shipBearing, emg_situation) \
                        = (Encounter_scenario_decision_making.multi_ship_scenario_waypoint(
                           os_ship, ts_ships, safe_dcpa, safe_tcpa, sog_os_min, ts_ships_length, max_turn_angle, m, f1, f2, f3, f4, f5, f6))
                    # ==========================================================================================================
                    # 固定路径点，在船舶有风险时路径点随风险情况改变，无风险时路径点锁定锁定
                    # 判断路径点是否在水里
                    if len(invariant_waypoint) == 0:
                        invariant_waypoint.append(waypoint)
                    invariant_waypoint, navigation_state_pre = invariant_waypoint_update.waypoint_choose(
                        invariant_waypoint, waypoint, os_ship, avoid_ship_label, shipMeetProp, emg_situation,
                        invariant_index, invariant_shipmeet, shipTCPA, shipDCPA, safe_dcpa, m, safe_tcpa, cog_os_start,
                        navigation_state)
                    navigation_state = navigation_state_pre
                    sog_vector_os = np.array(
                        [sog_os * math.sin(math.radians(cog_os)), sog_os * math.cos(math.radians(cog_os)), 0])
                    relative_invariant_vector = np.array(
                        [invariant_waypoint[0][0] - x_os, invariant_waypoint[0][1] - y_os, 0])
                    ang_invariant_waypoint = invariant_waypoint_update.angle_of_vector(sog_vector_os,
                                                                                       relative_invariant_vector)
                    if ang_invariant_waypoint > max_turn_angle[0]:
                        invariant_waypoint[0] = [x_os + 2 * safe_dcpa * math.sin(math.radians(cog_os + max_turn_angle[0])),
                                                 y_os + 2 * safe_dcpa * math.cos(math.radians(cog_os + max_turn_angle[0]))]
                    elif ang_invariant_waypoint < -max_turn_angle[0]:
                        invariant_waypoint[0] = [
                            x_os + 2 * safe_dcpa * math.sin(math.radians(cog_os - max_turn_angle[0])),
                            y_os + 2 * safe_dcpa * math.cos(math.radians(cog_os - max_turn_angle[0]))]
                    # 判断是否将固定路径点更新为计算的路径点
                    # ==========================================================================================================
                    # 本船当前位置到固定路径点的轨迹规划
                    obstacles_y = []
                    obstacles_x = []  # 添加障碍船位置或者障碍物位置
                    for i in range(len(ts_ships)):
                        obstacles_x.append(ts_ships[i][0])
                        obstacles_y.append(ts_ships[i][1])
                    start_point = [os_ship[0], os_ship[1]]
                    start_x = start_point[0]
                    start_y = start_point[1]
                    # 判断是否更新路径点
                    end_point = invariant_waypoint[0]
                    goal_x = end_point[0]
                    goal_y = end_point[1]
                    '''---------------------APF---start------------------------------'''
                    # grid_size = 0.1  # Resolution of the potential rho (m)

                    # area_radius = 0.5  # Potential area radius (m)

                    # area_radius = 0.05  # Potential area radius (m)

                    # rx_apf, ry_apf = PotentialFieldPlanning.potential_field_planning(start_x, start_y, goal_x, goal_y,
                    #                                                                  obstacles_x,
                    #                                                               obstacles_y, grid_size, area_radius)
                    '''---------------------APF---end---------------------------------'''
                    '''---------------------AStar---start-----------------------------'''
                    # ox=[]
                    # oy=[]
                    # for i in range(-500, 6000):
                    #     ox.append(i)
                    #     oy.append(-1000.0)
                    # for i in range(-500, 6000):
                    #     ox.append(i)
                    #     oy.append(1000.0)
                    # grid_size = 200  # Resolution of the potential rho (m)
                    # area_radius = 50  # Potential area radius (m)
                    # ASPlanner = a_star.AStarPlanner(ox, oy, grid_size, area_radius)
                    # rx_astar, ry_astar = ASPlanner.planning(start_x, start_y, goal_x, goal_y)
                    '''---------------------AStar---end-----------------------------'''
                    '''---------------------bezier_path---start------------------------------'''
                    angle_trans = (360 - cog_os) % 360
                    angle_trans = (angle_trans + 90) % 360  # 将顺时针纵轴向上为0°的角度数据转化为逆时针横轴向右为0°的角度数据
                    start_yaw = np.radians(angle_trans)
                    end_yaw = start_yaw
                    path, control_points = bezier_path.calc_4points_bezier_path(start_x, start_y, start_yaw, goal_x,
                                                                                goal_y, end_yaw, offset=3)

                    rx_bezier = path.T[0]
                    ry_bezier = path.T[1]
                    '''---------------------bezier_path---end------------------------------'''
                    rx = rx_bezier
                    ry = ry_bezier
                    rxfinal, ryfinal = PointDelete.pd(rx, ry)
                    angles = calculate_angles(rx, ry)
                    path_point = [[x, y] for x, y in zip(rx, ry)]
                    # ==========================================================================================================
                    # 取轨迹上等间隔的十分之的点作为样本点
                    num_points = len(rx_bezier) // 10
                    # 等间隔取出十分之一的点
                    if num_points > 0:
                        indices = np.linspace(0, len(rx_bezier) - 1, num_points, dtype=int)
                        sampled_rx = rx_bezier[indices]
                        sampled_ry = ry_bezier[indices]
                    else:
                        # 如果 rx_bezier 中的点少于10个，直接取所有点
                        sampled_rx = rx_bezier
                        sampled_ry = ry_bezier
                    # ==========================================================================================================
                    # 转化成经纬度
                    sampled_rx = [element + reference_point_x for element in sampled_rx]
                    sampled_ry = [element + reference_point_y for element in sampled_ry]
                    fastShipPos = convert_latlon_to_xy.ship_xy_to_latlon(sampled_rx, sampled_ry)
                    on_land_signal = False
                    for i in range(len(fastShipPos)):
                        print(fastShipPos[i])
                        on_land = globe.is_land(fastShipPos[i][1], fastShipPos[i][0])
                        if on_land:
                            print("在陆地上：", on_land)
                            on_land_signal = True  # 如果计算路径点在陆地上，那么实际建议路径点为本船正前方的点
                        else:
                            print("在水域中：", on_land)
                    if on_land_signal is True:
                        combin_message.clear()
                        print("正在重新计算建议路径，请保持航向！")
                        continue
                    # ==========================================================================================================
                    # 计算建议航向
                    shipColAvoCos = np.arctan((rxfinal[1] - rxfinal[0]) / (ryfinal[1] - ryfinal[0]))
                    shipColAvoCos = np.degrees(shipColAvoCos)
                    if shipColAvoCos < 0:
                        shipColAvoCos = shipColAvoCos + 360
                    if shipColAvoCos == 360:
                        shipColAvoCos = 0
                    # ==========================================================================================================
                    # 计算参数输出
                    colAvoData = {
                        "colAvoShipCount": colAvoShipCount,
                        "colAvoNegShipCount": colAvoNegShipCount,
                        "colAvoEmgShipCount": colAvoEmgShipCount,
                    }
                    colAvoCosSpdData = {
                        "shipColAvoCos": shipColAvoCos,
                        "shipColAvoSpd": sog_os / 0.5144,
                        "fastColAvoCos1": angles[0],
                        "fastColAvoCos2": angles[1],
                        "fastColAvoCos3": angles[2],
                        "osAvoResp": osAvoResp
                    }
                    colAvoPathData_keys = ["fastShipPosLon", "fastShipPosLat"]
                    colAvoPathData_value = fastShipPos
                    colAvoPathData = [dict(zip(colAvoPathData_keys, values)) for values in colAvoPathData_value]
                    path_point_data = [dict(zip(colAvoPathData_keys, values)) for values in path_point]
                    colAvoShipData_keys = ["shipMmssiId", "shipName", "shipMeetProp", "shipColAvoProp", "shipDcpa",
                                           "shipTcpa", "shipBearing", "shipDistance"]
                    colAvoShipData_value = []
                    for i in range(len(ts_ships)):
                        if shipColAvoProp[i] != 3:
                            parameter_list = [ts_ships_mmsi[i], ts_ships_name[i], shipMeetProp[i], shipColAvoProp[i],
                                              shipDCPA[i] / m, shipTCPA[i] / 60, shipBearing[i], shipDistance[i] / m]
                            colAvoShipData_value.append(parameter_list)
                    colAvoShipData = [dict(zip(colAvoShipData_keys, values)) for values in colAvoShipData_value]
                    send_data = {
                        "code": 200,
                        "colAvoCosSpdData": colAvoCosSpdData,
                        "colAvoData": colAvoData,
                        "colAvoPathData": colAvoPathData,
                        "colAvoShipData": colAvoShipData,
                        "msg": "请求成功"
                    }
                    ship_data = {
                        "os_ship": os_ship,
                        "ts_ship": ts_ships,
                        "os_shipBearing": os_shipBearing,
                        "colAvoCosSpdData": colAvoCosSpdData,
                        "colAvoData": colAvoData,
                        "colAvoPathData": path_point_data,
                        "colAvoShipData": colAvoShipData,
                    }
                    print(send_data)
                    current_time = time.time()
                    # ==========================================================================================================
                    # 将决策数据发送到交换机
                    # producer_rabbitmq.setup_fanout_exchange_and_queue(
                    #     rabbitmq_host,
                    #     rabbitmq_port,
                    #     rabbitmq_username,
                    #     rabbitmq_password,
                    #     vhost,
                    #     exchange_name='COLAVO_TO_IVS_EXCHANGE',
                    #     queue_name='COLAVO_TO_IVS_QUEUE'
                    #
                    # if current_time - last_send_time >= 10:
                    if colAvoShipData:
                        producer_rabbitmq.send_message_to_fanout_exchange(rabbitmq_host, rabbitmq_port, rabbitmq_username,
                                                                  rabbitmq_password, vhost,
                                                                  exchange_name=send_message_to_exchange_name,
                                                                  message=send_data
                                                                  )
                        last_send_time = current_time
                    # ==========================================================================================================
                    # 存储船舶会遇数据
                    end_time = time.time()
                    CalTime = round(end_time - start_time, 5)
                    print(CalTime)
                    # if avoid_ship_label != float('inf') or (
                    #         navigation_state_pre == 'right' or navigation_state_pre == 'left'):
                    #     append_dict_to_json(data_record_path, ship_data)
                    combin_message.clear()
                else:
                    print('缺少数据传入！')
                    combin_message.clear()
            elif len(combin_message) > 2:
                combin_message.clear()
                continue


if __name__ == "__main__":
    while True:
        try:
            # ==========================================================================================================
            # 连接参数
            rabbitmq_host = '172.16.2.198'
            rabbitmq_port = 5672
            rabbitmq_username = 'guest'
            rabbitmq_password = 'guest'
            vhost = '/'
            os_queue_name = "os_ship"
            ts_queue_name = "ts_ship"
            colavo_to_ivs_queue = "COLAVO_TO_IVS_QUEUE"
            send_message_to_exchange_name = "COLAVO_TO_IVS_EXCHANGE"
            dead_letter_exchange = 'dead_letter_exchange'
            data_record_path = "C:\\Users\\赤湾拖轮\\Desktop\\WHUT ColAvo Algorithm\\DataRecord\\ColData_10_30.json"
            safe_tcpa = 10  # tcpa安全阈值，单位min
            safe_dcpa = 0.2  # dcpa安全阈值，单位kn
            max_turn_angle = [10, 15]  # 紧急避让和特殊交叉会遇情况下的某些场景的最大转向角度
            f1, f2, f3, f4, f5, f6 = [-6, 6, 67.5, 112.5, 180, -112.5]
            consume_thread = threading.Thread(target=consume_queues,
                                              args=(rabbitmq_host, rabbitmq_port, rabbitmq_username, rabbitmq_password))
            consume_thread.start()
            process_thread = threading.Thread(target=process_data)
            process_thread.start()
            # 分线程完成数据的读取和处理
            # 等待两个线程完成
            consume_thread.join()
            process_thread.join()
            producer_rabbitmq.purge_queue(rabbitmq_host, rabbitmq_port, rabbitmq_username, rabbitmq_password, vhost,
                                          queue_name=ts_queue_name
                                          )
            producer_rabbitmq.purge_queue(rabbitmq_host, rabbitmq_port, rabbitmq_username, rabbitmq_password, vhost,
                                          queue_name=os_queue_name
                                          )
        except Exception as e:
            # 当程序执行发生错误时跳过当前循环重新运行程序
            print(f"出现异常: {e}")
            print("错误位置:")
            print(traceback.format_exc())
            print("正在重新启动程序...")
            continue

