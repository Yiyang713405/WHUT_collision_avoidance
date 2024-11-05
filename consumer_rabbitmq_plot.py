import queue
import numpy as np
import matplotlib.pyplot as plt
from Tools import convert_latlon_to_xy
from Tools import Encounter_scenario_decision_making
from Tools import shipmodle
from Tools import PointDelete
from service.tanker_VLCC8_L333 import VLCC8L333
from PlanningAlgorithm import PotentialFieldPlanning
from PlanningAlgorithm import bezier_path
import invariant_waypoint_update
from global_land_mask import globe
import os
from PlanningAlgorithm import a_star
import matplotlib.patches as patches
from matplotlib.patches import Circle
import producer_rabbitmq
import math
import time
import pika
import threading
import json
import copy
import traceback


ship_param = VLCC8L333()


def consume_from_queue(queue_name, rabbitmq_host, rabbitmq_port, rabbitmq_username, rabbitmq_password, vhost, ship_data,
                       data_queue):
    credentials = pika.PlainCredentials(rabbitmq_username, rabbitmq_password)
    parameters = pika.ConnectionParameters(host=rabbitmq_host, port=rabbitmq_port, virtual_host=vhost,
                                           credentials=credentials)

    stop_event = threading.Event()

    try:
        connection = pika.BlockingConnection(parameters)
        channel = connection.channel()

        channel.queue_declare(queue=queue_name, durable=False)
        channel.basic_qos(prefetch_count=1)

        channel.basic_consume(queue=queue_name,
                              on_message_callback=lambda ch, method, properties, body: callback(ch, method, properties,
                                                                                                body, ship_data,
                                                                                                stop_event, queue_name,
                                                                                                data_queue),
                              auto_ack=False)

        print(f'{queue_name} 正在等待消息...')
        while not stop_event.is_set():
            channel.connection.process_data_events()  # 处理连接中的消息事件

            # 每两秒接收一次数据
            time.sleep(2)  # 设置间隔为2秒

    except pika.exceptions.StreamLostError:
        print(f"{queue_name} 的连接丢失，正在尝试重新连接...")
        time.sleep(5)

    except Exception as e:
        print(f"在处理 {queue_name} 时发生错误: {str(e)}")
        # 打印完整的异常堆栈信息
        traceback.print_exc()
        time.sleep(5)

    finally:
            connection.close()


def receive_messages(rabbitmq_host, rabbitmq_port, rabbitmq_username, rabbitmq_password, vhost):
    ship_data = ShipData()
    # os_queue_name = 'OWNER_TO_COLAVO_QUEUE'
    # ts_queue_name = 'OTHER_TO_COLAVO_QUEUE'
    os_queue_name = 'os_ship'
    ts_queue_name = 'ts_ship'

    data_queue = queue.Queue()

    os_thread = threading.Thread(target=consume_from_queue, args=(
        os_queue_name, rabbitmq_host, rabbitmq_port, rabbitmq_username, rabbitmq_password, vhost, ship_data,
        data_queue))

    ts_thread = threading.Thread(target=consume_from_queue, args=(
        ts_queue_name, rabbitmq_host, rabbitmq_port, rabbitmq_username, rabbitmq_password, vhost, ship_data,
        data_queue))
    os_thread.start()
    ts_thread.start()
    return data_queue  # 返回数据队列以供后续绘图使用


class ShipData:
    def __init__(self):
        self.os_data = []  # OS 数据
        self.ts_data = []  # TS 数据

    def update_data(self, data_type, data):
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
    if 'osDynData' in message:
        ship_data.update_data('os', message['osDynData'])
    if 'tsData' in message:
        ship_data.update_data('ts', message['tsData'])


def update_ship_state(ship, time_interval):
    # 从状态集合中提取位置、航速和航向
    x, y, sog, cog = ship
    # 将航向转换为弧度
    cog_rad = math.radians(cog)

    # 计算新的位置
    new_x = x + sog * math.sin(cog_rad) * time_interval
    new_y = y + sog * math.cos(cog_rad) * time_interval

    # 更新船舶位置
    ship[0] = new_x
    ship[1] = new_y


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


def callback(ch, method, properties, body, ship_data, stop_event, queue_name, data_queue):
    # 获取mq队列的数据
    global os_ship_start, first_message_received
    with lock:  # 使用锁保护共享资源
        # 处理消息的逻辑
        pass
    message = json.loads(body)
    process_ship_data(message, ship_data)
    os_data = ship_data.os_data
    ts_data = ship_data.ts_data
    if os_data and ts_data:
        if not first_message_received:
            os_ship_start = os_data  # 捕获第一次的 os_data
            first_message_received = True  # 设置标记，表示已接收到第一条消息
        data_queue.put((os_data, ts_data, os_ship_start))
    ch.basic_ack(delivery_tag=method.delivery_tag)


def data_process(data_queue):
    invariant_waypoint = []
    m = 1852  # 1 海里 = 1852 米
    safe_tcpa = 10
    safe_dcpa = 0.5
    invariant_index = []
    invariant_shipmeet = [0]
    max_turn_angle = [30, 60]
    navigation_state = 'front'
    # 获取一次数据初始化存储列表
    try:
        os_data, ts_data, os_ship_start = data_queue.get(timeout=10)  # 设置超时为 10 秒
    except queue.Empty:
        print("无法从队列中获得初始数据")
        return  # 或者采取其他处理措施，比如抛出异常
        # 检查 ts_data 中的列表个数
    history_trajectory_os = []  # 记录历史轨迹
    history_trajectory_ts = []  # 记录历史轨迹
    history_distance = []
    history_dcpa = []
    history_tcpa = []
    for i in range(len(ts_data)):
        history_trajectory_ts.append([])
        history_distance.append([])
        history_dcpa.append([])
        history_tcpa.append([])
        # 绘图窗口建立
        # =====================================================================================================
    plt.ion()
    # 创建一个包含 2x2 子图的图形
    fig, axes = plt.subplots(2, 3, figsize=(12, 8))
    plt.gcf().canvas.mpl_connect('key_release_event', lambda event: [exit(0) if event.key == 'escape' else None])
    while True:
        try:
            os_ship_data, ts_ship_data, os_ship_start = data_queue.get(timeout=2)
            os_data = copy.deepcopy(os_ship_data)
            ts_data = copy.deepcopy(ts_ship_data)
            os_start = copy.deepcopy(os_ship_start)
            # ==========================================================================================================
            # 获取第一次接收的队列数据作为本船的初始状态
            os_start = convert_latlon_to_xy.ship_latlon_to_xy(os_start)
            reference_point_x = os_start[0]
            reference_point_y = os_start[1]
            # os_ship_start[2] = os_ship_start[2] * 0.51444 # 模拟器输出的航速是m/s
            sog_os_min = 0.5 * os_ship_start[2]
            x_os_start, y_os_start, sog_os_start, cog_os_start = os_start
            # =====================================================================================================
            # 读取本船数据
            os_ship = convert_latlon_to_xy.ship_latlon_to_xy(os_data)
            os_ship[0] = os_ship[0] - os_start[0]
            os_ship[1] = os_ship[1] - os_start[1]
            os_ship[2] = os_ship[2] * 0.51444  # 模拟器本船速度未
            x_os, y_os, sog_os, cog_os = os_ship
            if sog_os == 0:
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
                # ts_ships_length.append(ts_data[i][-3])
                ts_ships_length.append(100)
                ts_ships_mmsi.append(ts_data[i][-2])
                ts_ships_name.append(ts_data[i][-1])
                ts_data[i] = ts_data[i][:-3]
                ts_ships[i] = convert_latlon_to_xy.ship_latlon_to_xy(ts_data[i])
                ts_ships[i][2] = ts_ships[i][2] * 0.51444
                if ts_ships[i][2] == 0:
                    ts_ships[i][2] += 0.15
                # # roll_os = 0.1
            for i in range(len(ts_ships)):
                ts_ships[i][0] = ts_ships[i][0] - os_start[0]
                ts_ships[i][1] = ts_ships[i][1] - os_start[1]
            start_time = time.time()
            # ===================================================================================================
            # 计算避碰算法参数
            (waypoint, cpa, avoid_ship_label, colAvoShipCount, colAvoNegShipCount, colAvoEmgShipCount, osAvoResp,
             shipMeetProp, shipColAvoProp, shipDCPA, shipTCPA, shipBearing, shipDistance, os_shipBearing, emg_situation) \
                = (Encounter_scenario_decision_making.multi_ship_scenario_waypoint(
                os_ship, ts_ships, safe_dcpa, safe_tcpa, sog_os_min, ts_ships_length, max_turn_angle, m))
            # ==========================================================================================================
            # 固定路径点，在船舶有风险时路径点随风险情况改变，无风险时路径点锁定锁定
            # 判断路径点是否在水里
            waypoint_latlon = convert_latlon_to_xy.ship_xy_to_latlon([waypoint[0] + reference_point_x],
                                                                     [waypoint[1] + reference_point_y])
            waypoint_lat = waypoint_latlon[0][1]
            waypoint_lon = waypoint_latlon[0][0]
            on_land = globe.is_land(waypoint_lat, waypoint_lon)
            if len(invariant_waypoint) == 0:
                if on_land:
                    waypoint = [os_ship[0] + sog_os * math.sin(math.radians(cog_os)) * safe_tcpa * 60,
                                os_ship[1] + sog_os * math.cos(math.radians(cog_os)) * safe_tcpa * 60]
                    invariant_waypoint.append(waypoint)
                else:
                    invariant_waypoint.append(waypoint)
            invariant_waypoint, navigation_state_pre = invariant_waypoint_update.waypoint_choose(invariant_waypoint,
                                                                                       waypoint, os_ship,
                                                                                       avoid_ship_label,
                                                                                       shipMeetProp,
                                                                                       emg_situation,
                                                                                       invariant_index,
                                                                                       invariant_shipmeet,
                                                                                       shipTCPA, safe_dcpa, m,
                                                                                       safe_tcpa, cog_os_start,
                                                                                       navigation_state)
            navigation_state = navigation_state_pre
            # ==========================================================================================================
            # 到达路径点轨迹规划
            obstacles_y = []
            obstacles_x = []
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
            #                                                                  obstacles_y, grid_size, area_radius)
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
            path, control_points = bezier_path.calc_4points_bezier_path(start_x, start_y, start_yaw, goal_x, goal_y,
                                                                        end_yaw, offset=3)

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
            # ==========================================================================================================
            # 计算建议航向
            shipColAvoCos = np.arctan((rxfinal[1] - rxfinal[0]) / (ryfinal[1] - ryfinal[0]))
            shipColAvoCos = np.degrees(shipColAvoCos)
            if shipColAvoCos < 0:
                shipColAvoCos = shipColAvoCos + 360
            if shipColAvoCos == 360:
                shipColAvoCos = 0
            end_time = time.time()
            CalTime = round((end_time - start_time) * 1000, 2)
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
                colAvoShipData_value.append([])
            for i in range(len(ts_ships)):
                parameter_list = [ts_ships_mmsi[i], ts_ships_name[i], shipMeetProp[i], shipColAvoProp[i],
                                  shipDCPA[i] / m, shipTCPA[i] / 60, shipBearing[i], shipDistance[i] / m]
                colAvoShipData_value[i].extend(parameter_list)
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
            # ==========================================================================================================
            # 存储船舶会遇数据
            if avoid_ship_label != float('inf') or (navigation_state_pre == 'right' or navigation_state_pre == 'left'):
                append_dict_to_json('D:\\A震兑\\测试视频\\test.json', ship_data)
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
            # )
            producer_rabbitmq.send_message_to_fanout_exchange(rabbitmq_host, rabbitmq_port, rabbitmq_username,
                                                              rabbitmq_password, vhost,
                                                              exchange_name='COLAVO_TO_IVS_EXCHANGE',
                                                              message=send_data
                                                              )
            # ================================================================================================
            # 记录本船和目标船历史数据
            history_trajectory_os.append((os_ship[0], os_ship[1]))
            for i in range(len(ts_ships)):
                history_trajectory_ts[i].append((ts_ships[i][0], ts_ships[i][1]))
            for i in range(len(history_distance)):
                history_distance[i].append(shipDistance[i])
                history_dcpa[i].append(shipDCPA[i])
                history_tcpa[i].append(shipTCPA[i])
            # 参数单位转换
            # ==========================================================================================================
            x_os, y_os, sog_os, cog_os = os_ship
            trajectory_os_x = [element[0] / m for element in history_trajectory_os]
            trajectory_os_y = [element[1] / m for element in history_trajectory_os]

            # 处理目标船舶轨迹
            trajectory_ts_x = [[element[0] / m for element in history_trajectory_ts[i]] for i in
                               range(len(history_trajectory_ts))]
            trajectory_ts_y = [[element[1] / m for element in history_trajectory_ts[i]] for i in
                               range(len(history_trajectory_ts))]
            distance = [[element / m for element in history_distance[i]] for i in range(len(history_distance))]
            dcpa = [[element / m for element in history_dcpa[i]] for i in range(len(history_dcpa))]
            tcpa = [[element / 60 for element in history_tcpa[i]] for i in range(len(history_dcpa))]
            ts_num = len(ts_ships)
            cmap = plt.get_cmap('viridis')  # 定义轨迹颜色
            # ==========================================================================================================
            # 绘图
            # 清空每个子图
            for ax in axes.flat:
                ax.clear()
                # 绘制自己船只的位置
            axes[0, 0].scatter(x_os / m, y_os / m, color='g', label='Own Ship', s=10)
            # 绘制目标船只
            for i, (x, y, sog, cog) in enumerate(ts_ships):
                axes[0, 0].text((x / m) + 0.1, y / m, f'{shipMeetProp[i]}', fontsize=12, color='r')
                ship_shape = shipmodle.ship_model(x / m, y / m, sog, cog)
                patch = patches.PathPatch(ship_shape, facecolor='black', edgecolor='black', lw=2)
                axes[0, 0].add_patch(patch)
                # 绘制自己的船只
            ship_shape = shipmodle.ship_model(x_os / m, y_os / m, sog_os, cog_os)
            patch = patches.PathPatch(ship_shape, facecolor='r', edgecolor='r', lw=2)
            axes[0, 0].add_patch(patch)
            # 绘制目标点和 CPA
            axes[0, 0].scatter(invariant_waypoint[0][0] / m, invariant_waypoint[0][1] / m, s=50, marker='*', color='r',
                               label='Waypoint')
            axes[0, 0].scatter(cpa[0] / m, cpa[1] / m, s=50, marker='*', color='black', label='CPA')
            if avoid_ship_label != float('inf'):
                axes[0, 0].plot([ts_ships[int(avoid_ship_label)][0] / m, cpa[0] / m],
                                [ts_ships[int(avoid_ship_label)][1] / m, cpa[1] / m], color="grey", linestyle="--")
                # 绘制轨迹
            axes[0, 0].plot(trajectory_os_x, trajectory_os_y, color="r", linestyle="-", label="Ship Trajectory")
            for i in range(len(trajectory_ts_x)):
                color = cmap(i / ts_num)
                axes[0, 0].plot(trajectory_ts_x[i], trajectory_ts_y[i], color=color, linestyle="-",
                                label="Ship Trajectory")
            axes[0, 0].plot(rx / m, ry / m, color="r", linestyle="-", label="Planned Path")
            # 绘制圆圈（1000米）示意
            circle_radius = 1000 / m
            circle = Circle((x_os / m, y_os / m), circle_radius, color='r', fill=False, linewidth=2, linestyle='--',
                            label="1000 meters radius")
            axes[0, 0].add_patch(circle)
            # 绘制安全域
            for theta in np.linspace(0, 2 * np.pi, 100):
                rx = circle_radius * np.cos(theta)
                ry = circle_radius * np.sin(theta)
                axes[0, 0].plot(x_os / m + rx / m, y_os / m + ry / m, color='r', alpha=0.5)
                # 设置第一个子图的标签和标题
            axes[0, 0].set_xlabel('(x [kn])')
            axes[0, 0].set_ylabel('(y [kn])')
            axes[0, 0].set_title('Ship collision path planning visualization')
            axes[0, 0].axis('equal')
            axes[0, 0].grid()

            for i in range(len(distance)):
                color = cmap(i / ts_num)
                axes[1, 0].plot(range(len(distance[i])), distance[i], color=color, linestyle="-",
                                label=f"{ts_ships_mmsi[i]}")
            for i in range(len(dcpa)):
                color = cmap(i / ts_num)
                axes[0, 1].plot(range(len(dcpa[i])), dcpa[i], color=color, linestyle="-",
                                label=f"{ts_ships_mmsi[i]}")
            for i in range(len(tcpa)):
                color = cmap(i / ts_num)
                axes[1, 1].plot(range(len(tcpa[i])), tcpa[i], color=color, linestyle="-",
                                label=f"{ts_ships_mmsi[i]}")
            #     # 更新坐标轴范围

            def update_axes():
                for i in [1, 3, 4]:  # 1, 2, 3对应第二、第三、第四个子图
                    ax = axes.flatten()[i]
                    x_data = ax.get_lines()[0].get_xdata()  # 获取 x 数据
                    y_data = np.concatenate([line.get_ydata() for line in ax.get_lines()])  # 获取所有 y 数据
                    ax.set_xlim(0, len(x_data))  # 根据 x 数据更新 xlim
                    ax.set_ylim(y_data.min() - 1, y_data.max() + 1)  # 根据 y 数据更新 ylim

            update_axes()  # 更新坐标轴范围
            # 更新图例
            # axes[0, 0].legend()

            axes[0, 1].set_xlabel('t [s]')
            axes[0, 1].set_ylabel('DCPA [kn]')
            axes[0, 1].set_title('DCPA to risk_ship')
            axes[0, 1].grid()

            axes[1, 0].set_xlabel('t [s]')
            axes[1, 0].set_ylabel('Distance [kn]')
            axes[1, 0].set_title('Distance to risk_ship')
            axes[1, 0].grid()

            axes[1, 1].set_xlabel('t [s]')
            axes[1, 1].set_ylabel('TCPA [min]')
            axes[1, 1].set_title('TCPA to risk_ship')
            axes[1, 1].grid()

            # 绘制目标船相对本船位置角度
            circle = plt.Circle((0, 0), 1, color='lightblue', fill=True)
            axes[0, 2].add_artist(circle)
            for i, angle in enumerate(shipBearing):
                color = cmap(i / ts_num)
                theta = np.radians(90 - angle)  # 转换为弧度并调整为正北方向
                x = np.cos(theta)
                y = np.sin(theta)
                axes[0, 2].quiver(0, 0, x, y, angles='xy', scale_units='xy', scale=1, color=color,
                                  label=f'{angle:.2f}°')
            # 设置子图的限制和标签
            axes[0, 2].set_xlim(-1.5, 1.5)
            axes[0, 2].set_ylim(-1.5, 1.5)
            axes[0, 2].set_aspect('equal', adjustable='box')
            axes[0, 2].axhline(0, color='black', linewidth=0.5, ls='--')
            axes[0, 2].axvline(0, color='black', linewidth=0.5, ls='--')
            axes[0, 2].set_title('Ts relative position angle')
            axes[0, 2].set_xlabel('X')
            axes[0, 2].set_ylabel('Y')
            axes[0, 2].grid()

            # 绘制本船相对目标船位置角度
            circle = plt.Circle((0, 0), 1, color='lightblue', fill=True)
            axes[1, 2].add_artist(circle)
            for i, angle in enumerate(os_shipBearing):
                color = cmap(i / ts_num)
                theta = np.radians(90 - angle)  # 转换为弧度并调整为正北方向
                x = np.cos(theta)
                y = np.sin(theta)
                axes[1, 2].quiver(0, 0, x, y, angles='xy', scale_units='xy', scale=1, color=color,
                                  label=f'{angle:.2f}°')
                # 设置子图的限制和标签
            axes[1, 2].set_xlim(-1.5, 1.5)
            axes[1, 2].set_ylim(-1.5, 1.5)
            axes[1, 2].set_aspect('equal', adjustable='box')
            axes[1, 2].axhline(0, color='black', linewidth=0.5, ls='--')
            axes[1, 2].axvline(0, color='black', linewidth=0.5, ls='--')
            axes[1, 2].set_title('Os relative position angle')
            axes[1, 2].set_xlabel('X')
            axes[1, 2].set_ylabel('Y')
            axes[1, 2].grid()

            axes[0, 1].legend(loc='upper left')
            axes[1, 0].legend(loc='upper left')
            axes[1, 1].legend(loc='upper left')
            axes[0, 2].legend(loc='upper left')
            axes[1, 2].legend(loc='upper left')

            plt.tight_layout()
            plt.show()
            plt.pause(0.4)  # 暂停一段时间以便观察

        except queue.Empty:
            break  # 退出循环


if __name__ == "__main__":
    lock = threading.Lock()
    first_message_received = False  # 全局变量，用于跟踪是否接收到第一条消息
    os_ship_start = None
    data_queue = receive_messages('172.16.2.198', 5672, 'guest', 'guest', '/')
    # 在这里您可以根据需要决定是否调用绘图函数
    rabbitmq_host = '172.16.2.198'
    rabbitmq_port = 5672
    rabbitmq_username = 'guest'
    rabbitmq_password = 'guest'
    vhost = '/'
    # =====================================================================================================
    data_process(data_queue)

