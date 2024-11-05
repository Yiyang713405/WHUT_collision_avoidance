import queue
import numpy as np
import matplotlib.pyplot as plt
from Tools import EvaluationFunction
from Tools import convert_latlon_to_xy
from Tools import Encounter_scenario_decision_making
from Tools import shipmodle
from Tools import PointDelete
from service.tanker_VLCC8_L333 import VLCC8L333
from PlanningAlgorithm import PotentialFieldPlanning
from PlanningAlgorithm import bezier_path
from PlanningAlgorithm import a_star
import matplotlib.patches as patches
import producer_rabbitmq
import math
import time
import pika
import threading
import json


ship_param = VLCC8L333()


class ShipData:
    def __init__(self):
        self.os_data = []  # OS 数据
        self.ts_data = []  # TS 数据

    def update_data(self, data):
        # 更新 OS 数据
        os_dyn_data = data.get('os_ship', {}).get('osDynData', {})
        self.os_data = [
            os_dyn_data.get('shipPosLon', None),  # 船舶纬度
            os_dyn_data.get('shipPosLat', None),  # 船舶经度
            os_dyn_data.get('shipSpd', None),     # 船舶速度
            os_dyn_data.get('shipCos', None),     # 船舶航向
        ]

        # 更新 TS 数据
        ts_data_list = data.get('ts_ship', {}).get('tsData', [])
        self.ts_data = [
            [
                ship.get('shipPosLon', None),   # 船舶纬度
                ship.get('shipPosLat', None),   # 船舶经度
                ship.get('shipSpd', None),      # 船舶速度
                ship.get('shipCos', None),      # 船舶航向
                ship.get('shipLength', None),   # 船舶长度
                ship.get('aisShipMmsi', None),  # 船舶 MMSI
                ship.get('shipName', None)      # 船舶名称
            ] for ship in ts_data_list
        ]


def process_ship_data(message, ship_data):
    # 处理 OS 数据
    if 'os_ship' in message:
        ship_data.update_data(message)

    # 处理 TS 数据
    if 'ts_ship' in message:
        ship_data.update_data(message)


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
    计算贝塞尔曲线在起点，中间点和终点的和航向
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


lock = threading.Lock()


def callback(ch, method, properties, body, ship_data, stop_event, queue_name, data_queue):
    with lock:  # 使用锁保护共享资源
        # 处理消息的逻辑
        pass
    message = json.loads(body)
    process_ship_data(message, ship_data)

    os_data = ship_data.os_data
    ts_data = ship_data.ts_data

    if os_data and ts_data:
        # 增加计数器
        stop_event.set()  # 第二次接收到 os_ship 时停止接收
        ts_ships = []  # 定于空列表存放目标船数据
        os_ship = convert_latlon_to_xy.ship_latlon_to_xy(os_data)
        reference_point_x = os_ship[0]
        reference_point_y = os_ship[1]
        os_ship[2] = os_ship[2] * 0.51444
        sog_os_min = 0.5 * os_ship[2]
        ts_ships_length = []  # 定义空列表存放目标船船长
        ts_ships_mmsi = []  # 定义空列表存放目标船mmsi
        ts_ships_name = []  # 定义空列表存放目标船船名
        history_trajectory_os = []
        history_trajectory_ts = []

        for i in range(len(ts_data)):
            ts_ships.append([])
            history_trajectory_ts.append([])

        for i in range(len(ts_ships)):
            ts_ships_length.append(ts_data[i][-3])
            ts_ships_mmsi.append(ts_data[i][-2])
            ts_ships_name.append(ts_data[i][-1])
            ts_data[i] = ts_data[i][:-3]
            ts_ships[i] = convert_latlon_to_xy.ship_latlon_to_xy(ts_data[i])
            ts_ships[i][2] = ts_ships[i][2] * 0.51444
            # # roll_os = 0.1
        time_interval = 1
        t = 1

        for i in range(len(ts_ships)):
            ts_ships[i][0] = ts_ships[i][0] - os_ship[0]
            ts_ships[i][1] = ts_ships[i][1] - os_ship[1]

        os_ship[0] = 0
        os_ship[1] = 0

        # 如果已经停止接收数据，执行后续操作
        while True:
            update_ship_state(os_ship, time_interval)
            history_trajectory_os.append((os_ship[0],
                                          os_ship[1]))
            for i in range(len(ts_ships)):
                history_trajectory_ts[i].append((ts_ships[i][0], ts_ships[i][1]))
        #     # =====================================================================
        #     # 转换坐标系
            for i in range(len(ts_ships)):
                update_ship_state(ts_ships[i], time_interval)
        #     # =====================================================================
        #     # 调用路径点决策函数
            (waypoint, cpa, avoid_ship_label, colAvoShipCount, colAvoNegShipCount, colAvoEmgShipCount, osAvoResp,
             shipMeetProp, shipColAvoProp, shipDCPA, shipTCPA, shipBearing, shipDistance) \
                = (Encounter_scenario_decision_making.multi_ship_scenario_waypoint(
                 os_ship, ts_ships, 1, 20, sog_os_min, ts_ships_length))
            data_queue.put((os_ship, ts_ships, waypoint, cpa, avoid_ship_label, history_trajectory_os,
                            history_trajectory_ts, colAvoShipCount, colAvoNegShipCount, colAvoEmgShipCount,
                            osAvoResp, ts_ships_mmsi, ts_ships_name, shipMeetProp, shipColAvoProp, shipDCPA, shipTCPA,
                            shipBearing, shipDistance, reference_point_x, reference_point_y))
            t += 1
            time.sleep(time_interval)

    ch.basic_ack(delivery_tag=method.delivery_tag)


def plot_data(data_queue):
    plt.ion()
    fig, axes = plt.subplots()
    plt.gcf().canvas.mpl_connect('key_release_event', lambda event: [exit(0) if event.key == 'escape' else None])
    while True:
        try:
            (os_ship, ts_ships, waypoint, cpa, avoid_ship_label, history_trajectory_os,
             history_trajectory_ts, colAvoShipCount, colAvoNegShipCount, colAvoEmgShipCount,
             osAvoResp, ts_ships_mmsi, ts_ships_name, shipMeetProp, shipColAvoProp, shipDCPA, shipTCPA, shipBearing,
             shipDistance, reference_point_x, reference_point_y) \
                = data_queue.get(timeout=1)
            # 提取数据
            obstacles_y = []
            obstacles_x = []
            # 处理绘图逻辑
            m = 1852  # 1 海里 = 1852 米
            x_os, y_os, sog_os, cog_os = os_ship
            for i in range(len(ts_ships)):
                obstacles_x.append(ts_ships[i][0])
                obstacles_y.append(ts_ships[i][1])
            start_point = [os_ship[0], os_ship[1]]
            start_x = start_point[0]
            start_y = start_point[1]
            end_point = waypoint
            goal_x = end_point[0]
            goal_y = end_point[1]

            '''---------------------APF---start------------------------------'''
            # grid_size = 0.1  # Resolution of the potential rho (m)
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
            '''---------------------bezier_path---start------------------------------'''
            rx = rx_bezier
            ry = ry_bezier
            rxfinal, ryfinal = PointDelete.pd(rx, ry)
            angles = calculate_angles(rx, ry)
            # ========================================================
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
            # ==========================================================================================================
            # 计算参数输出
            colAvoData = {
                        "colAvoShipCount": colAvoShipCount,
                        "colAvoNegShipCount": colAvoNegShipCount,
                        "colAvoEmgShipCount": colAvoEmgShipCount
                         }
            colAvoCosSpdData = {
                                "shipColAvoCos": shipColAvoCos,
                                "shipColAvoSpd": sog_os / 0.5144,
                                "fastColAvoCos1": angles[0],
                                "fastColAvoCos2": angles[1],
                                "fastColAvoCos3": angles[2],
                                "osAvoResp": osAvoResp
                                }
            colAvoPathData_keys = ['fastShipPosLon', 'fastShipPosLat']
            colAvoPathData_value = fastShipPos
            colAvoPathData = [dict(zip(colAvoPathData_keys, values)) for values in colAvoPathData_value]
            colAvoShipData_keys = ['shipMMSIID', 'shipName', 'shipMeetProp', 'shipColAvoProp', 'shipDCPA',
                                   'shipTCPA', 'shipBearing', 'shipDistance']
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
                        "msg": "请求成功",
                        "colAvoData": colAvoData,
                        "colAvoCosSpdData": colAvoCosSpdData,
                        " colAvoPathData": colAvoPathData,
                        "colAvoShipData": colAvoShipData
                        }
            # print(send_data)
            # ==========================================================================================================
            # 将字典转换成json格式，不亲给上传到rabbitmq
            producer_rabbitmq.send_message(rabbitmq_host, rabbitmq_port, rabbitmq_username, rabbitmq_password, vhost,
                                           'calculate_result', send_data)

            # ==========================================================================================================
            # 绘图
            axes.clear()  # 清空当前 Axes
            # 绘制自己船只的位置
            axes.scatter(x_os/m, y_os/m, color='g', label='Own Ship', s=10)
            # 绘制目标船只
            for x, y, sog, cog in ts_ships:
                ship_shape = shipmodle.ship_model(x/m, y/m, sog, cog)  # 使用 shipmodle 创建船只形状
                patch = patches.PathPatch(ship_shape, facecolor='black', edgecolor='black', lw=2)
                axes.add_patch(patch)
                # 绘制自己的船只
            ship_shape = shipmodle.ship_model(x_os/m, y_os/m, sog_os, cog_os)
            patch = patches.PathPatch(ship_shape, facecolor='g', edgecolor='g', lw=2)
            axes.add_patch(patch)
            # 绘制目标点和 CPA
            plt.scatter(waypoint[0]/m, waypoint[1]/m, s=50, marker='*', color='r', label='Waypoint')
            plt.scatter(cpa[0]/m, cpa[1]/m, s=50, marker='*', color='black', label='CPA')
            if avoid_ship_label != 1000:
                plt.plot([ts_ships[avoid_ship_label][0]/m, cpa[0]/m], [ts_ships[avoid_ship_label][1]/m, cpa[1]/m],
                         color="grey", linestyle="--")
            # 绘制轨迹
            trajectory_os_x = [element[0]/m for element in history_trajectory_os]
            trajectory_os_y = [element[1]/m for element in history_trajectory_os]
            trajectory_ts_x = []
            trajectory_ts_y = []
            for i in range(len(history_trajectory_ts)):
                trajectory_ts_x.append([])
                trajectory_ts_y.append([])

            for i in range(len(history_trajectory_ts)):
                trajectory_ts_x[i] = [element[0]/m for element in history_trajectory_ts[i]]
                trajectory_ts_y[i] = [element[1]/m for element in history_trajectory_ts[i]]

            plt.plot(trajectory_os_x, trajectory_os_y, color="r", linestyle="-", label="Ship Trajectory")
            color_set = ['b', 'g', 'black']
            for i in range(len(trajectory_ts_x)):
                plt.plot(trajectory_ts_x[i], trajectory_ts_y[i], color=color_set[i], linestyle="-", label="Ship Trajectory")
            plt.plot(rx/m, ry/m, color="g", linestyle="-", label="Planned Path")

            # 绘制圆圈（1000米）示意
            circle_radius = 1000 / m  # 转换为海里
            circle = plt.Circle((x_os/m, y_os/m), circle_radius, color='r', fill=False, linewidth=2, linestyle='--',
                                label="1000 meters radius")
            axes.add_artist(circle)

            # 绘制安全域 / 四元船舶领域
            for theta in np.linspace(0, 2 * np.pi, 100):  # 圆周角度
                rx = circle_radius * np.cos(theta)
                ry = circle_radius * np.sin(theta)
                plt.plot(x_os/m + rx/m, y_os/m + ry/m, color='r', alpha=0.5)  # 绘制船舶周围的领域

            axes.grid()
            axes.set_xlabel('X (n mile)')
            axes.set_ylabel('Y (n mile)')
            axes.set_title('Ship Path Planning Visualization')
            axes.axis('equal')
            plt.pause(0.4)  # 暂停一段时间以便观察
        # #
        except queue.Empty:
            break  # 退出循环


def consume_from_queue(queue_name, rabbitmq_host, rabbitmq_port, rabbitmq_username, rabbitmq_password, vhost, ship_data, data_queue, stop_event):
    credentials = pika.PlainCredentials(rabbitmq_username, rabbitmq_password)
    parameters = pika.ConnectionParameters(host=rabbitmq_host, port=rabbitmq_port, virtual_host=vhost, credentials=credentials)

    try:
        connection = pika.BlockingConnection(parameters)
        channel = connection.channel()

        channel.queue_declare(queue=queue_name, durable=True)
        channel.basic_qos(prefetch_count=1)

        channel.basic_consume(queue=queue_name,
                              on_message_callback=lambda ch, method, properties, body: callback(ch, method, properties, body, ship_data, stop_event, queue_name, data_queue),
                              auto_ack=False)

        print(f'{queue_name} 正在等待消息...')
        while not stop_event.is_set():
            channel.connection.process_data_events()  # 处理连接中的消息事件

    except pika.exceptions.StreamLostError:
        print(f"{queue_name} 的连接丢失，正在尝试重新连接...")
        time.sleep(5)

    except Exception as e:
        print(f"在处理 {queue_name} 时发生错误: {str(e)}")
        time.sleep(5)

    finally:
        connection.close()


def receive_messages(rabbitmq_host, rabbitmq_port, rabbitmq_username, rabbitmq_password, vhost):
    ship_data = ShipData()
    queue_name = 'all_ship'  # 只使用一个队列

    data_queue = queue.Queue()
    stop_event = threading.Event()

    # 启动线程从指定队列消费消息
    consumer_thread = threading.Thread(target=consume_from_queue, args=(
        queue_name, rabbitmq_host, rabbitmq_port, rabbitmq_username, rabbitmq_password, vhost, ship_data, data_queue, stop_event))

    consumer_thread.start()

    return data_queue  # 返回数据队列和停止事件


if __name__ == "__main__":
    data_queue = receive_messages('172.16.2.198', 5672, 'guest', 'guest', '/')
    # 在这里您可以根据需要决定是否调用绘图函数
    rabbitmq_host = '172.16.2.198'
    rabbitmq_port = 5672
    rabbitmq_username = 'guest'
    rabbitmq_password = 'guest'
    vhost = '/'
    plot_data(data_queue)

