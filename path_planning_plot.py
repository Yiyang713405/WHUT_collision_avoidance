import socket
import json
import traceback
from pynput import keyboard
import TargetShipSet
import os
import time
import numpy as np
import matplotlib.pyplot as plt
from Tools import convert_latlon_to_xy
from Tools import Encounter_scenario_decision_making
from Tools import shipmodle
import matplotlib.patches as patches
from matplotlib.patches import Circle
from Tools import PointDelete
from service import ip_MFAC
from service import ip_guidance
import threading
from service import ip_controller
from Tools import ip_controller
from service.tanker_VLCC8_L333 import VLCC8L333
from PlanningAlgorithm import PotentialFieldPlanning
from PlanningAlgorithm import a_star
from PlanningAlgorithm import bezier_path
import math
import time
import producer_rabbitmq

# 初始化通信地址和端口
me_listening_socket = None
remote_ip = ('127.0.0.1')
me_listening_port = 8090  # 本脚本（控制器）监听的端口号
remote_port = int(8080)  # 远端程序（模拟器）监听的端口号
# me_listening_port = 60001  # 本脚本（控制器）监听的端口号
# remote_port = int(60000)  # 远端程序（模拟器）监听的端口号
me_sending_port = 50000  # 本demo发出数据使用的端口
rabbitmq_host = '172.16.2.198'
rabbitmq_port = 5672
rabbitmq_username = 'guest'
rabbitmq_password = 'guest'
vhost = '/'
# --------------------
norx = ''  # 帧头
nory = ''  # 帧尾
hdsRudderPS = ''
hdsRudderSB = ''
hdsTelePS = ''
hdsTeleSB = ''
hdsThrBow = ''
hdsThrStern = ''

# --------------------
# 单独定义本测试对象所需要数据变量
# --------------------
Latitude = ''
Longitude = ''
LateralSpeed = ''
LongitudinalSpeed = ''
# R_Yawrate = ''
Heading = ''
NEDe = ''
NEDn = ''
Pitch = ''
Roll = ''

t = time.ctime()
# --------------------
# 单独定义本测试其余变量
# --------------------

# 坐标列表写出及开启画图窗口
l = 27.4
L = 16.4
w = 11.5
List_e = []  # 定义一个 东向位移 的空列表用来接收动态的数据
List_n = []  # 定义一个 北向位移 的空列表用来接收动态的数据
plt.ion()  # 开启一个hold on的窗口
r1 = 0
r2 = 0
t1 = 0
t2 = 0

ship_param = VLCC8L333()


def send_channel_func(delta_cmd_deg, rpm):
    # ================================
    # sending part for send data
    # ================================
    global remote_ip
    global remote_port
    global me_sending_port

    me_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    me_socket.bind(('', me_sending_port))

    # ================================
    # 代入端口接受格式
    # ================================
    msg = ('$LUPWM,' + str(delta_cmd_deg) + ',' + str(r2) + ',' + str(t1) + ',' + str(rpm) + '\x0a')  # 控拖轮
    # msg = ('$LUPWM,' + str(r1) + ',' + str(t1) + '\x0a')
    # print(msg)
    me_socket.sendto(msg.encode("utf-8"), (remote_ip, remote_port))

    if me_socket is not None:
        me_socket.close()
        me_socket = None


def calculate_direction_angle(X1, Y1, X2, Y2):
    vec_AB = (X2 - X1, Y2 - Y1)

    angle_rad = math.atan2(vec_AB[0], vec_AB[1])
    angle_deg = math.degrees(angle_rad)

    if angle_deg < 0:
        angle_deg += 360

    return angle_deg


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


def path_planning_plot(invariant_waypoint, cpa, avoid_ship_label, colAvoShipCount, colAvoNegShipCount, colAvoEmgShipCount,
                       osAvoResp, shipMeetProp, shipColAvoProp, shipDCPA, shipTCPA, shipBearing, shipDistance,
                       os_ship, ts_ships, reference_point_x, reference_point_y, ts_ships_mmsi, ts_ships_name,
                       history_trajectory_os, history_trajectory_ts, history_distance,
                       history_dcpa, history_tcpa, axes, os_shipBearing, start_time, navigation_state):
    m = 1852
    obstacles_y = []
    obstacles_x = []
    # 处理绘图逻辑
    x_os, y_os, sog_os, cog_os = os_ship
    for i in range(len(ts_ships)):
        obstacles_x.append(ts_ships[i][0])
        obstacles_y.append(ts_ships[i][1])
    start_point = [os_ship[0], os_ship[1]]
    start_x = start_point[0]
    start_y = start_point[1]
    # ========================================================================================================
    # 判断是否更新路径点
    end_point = invariant_waypoint
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
    angles = TargetShipSet.calculate_angles(rx, ry)
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
    # if avoid_ship_label != float('inf') or (navigation_state == 'right' or navigation_state == 'left'):
    #     append_dict_to_json("D:\\AA船舶避碰\\ColAvoDataRecord\\三船场景54.json", ship_data)
    # # ==========================================================================================================
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
    # =========================================================================================================
    # 发送控制指令
    target_heading = calculate_direction_angle(x_os, y_os, invariant_waypoint[0], invariant_waypoint[1])
    s_psi_cmd_deg = target_heading
    if s_psi_cmd_deg > 360:
        s_psi_cmd_deg = s_psi_cmd_deg - 360
    if s_psi_cmd_deg < cog_os - 180:
        s_psi_cmd_deg = s_psi_cmd_deg + 360
    if cog_os < s_psi_cmd_deg - 180:
        s_psi_cmd_deg = s_psi_cmd_deg - 360
    target_angle = s_psi_cmd_deg
    ship_rpm = 10
    # 控制模块输出——>>船舶操纵模型（虚拟）/舵机（实船）：
    delta_cmd_deg = (
        # ip_controller.PID(kp=0.5, ki=0.2, kd=0.02, output_min=-30, output_max=30).solve(cog_os, target_angle))
        ip_controller.PID(kp=2, ki=0.2, kd=0.02, output_min=-15, output_max=15).solve(cog_os, target_angle))
    # print(delta_cmd_deg)
    send_channel_func(delta_cmd_deg, ship_rpm)
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
    color_set = ['b', 'g', 'black']
    # ==========================================================================================================
    # 绘图
    # 清空每个子图
    for ax in axes.flat:
        ax.clear()
        # 绘制自己船只的位置
    axes[0, 0].scatter(x_os / m, y_os / m, color='g', label='Own Ship', s=10)
    # 绘制目标船只
    for i, (x, y, sog, cog) in enumerate(ts_ships):
        axes[0, 0].text((x / m)+0.1, y / m, f'{shipMeetProp[i]}', fontsize=12, color='r')
        ship_shape = shipmodle.ship_model(x / m, y / m, sog, cog)
        patch = patches.PathPatch(ship_shape, facecolor='black', edgecolor='black', lw=2)
        axes[0, 0].add_patch(patch)
        # 绘制自己的船只
    ship_shape = shipmodle.ship_model(x_os / m, y_os / m, sog_os, cog_os)
    patch = patches.PathPatch(ship_shape, facecolor='r', edgecolor='r', lw=2)
    axes[0, 0].add_patch(patch)
    # 绘制目标点和 CPA
    axes[0, 0].scatter(invariant_waypoint[0] / m, invariant_waypoint[1] / m, s=20, marker='*', color='r', label='Waypoint')
    axes[0, 0].scatter(cpa[0] / m, cpa[1] / m, s=20, marker='*', color='black', label='CPA')
    if avoid_ship_label != float('inf'):
        axes[0, 0].plot([ts_ships[int(avoid_ship_label)][0] / m, cpa[0] / m],
                        [ts_ships[int(avoid_ship_label)][1] / m, cpa[1] / m], color="grey", linestyle="--")
        # 绘制轨迹
    axes[0, 0].plot(trajectory_os_x, trajectory_os_y, color="r", linestyle="-", label="Ship Trajectory", linewidth=1)
    for i in range(len(trajectory_ts_x)):
        axes[0, 0].plot(trajectory_ts_x[i], trajectory_ts_y[i], color=color_set[i], linestyle="-",
                        label="Ship Trajectory")
    axes[0, 0].plot(rx / m, ry / m, color="r", linestyle="-", label="Planned Path", lw=1)
    # print(type(rx), rx)
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
        axes[1, 0].plot(range(len(distance[i])), distance[i], color=color_set[i], linestyle="-",
                        label=f"{ts_ships_mmsi[i]}")
    for i in range(len(dcpa)):
        axes[0, 1].plot(range(len(dcpa[i])), dcpa[i], color=color_set[i], linestyle="-",
                        label=f"{ts_ships_mmsi[i]}")
    for i in range(len(tcpa)):
        axes[1, 1].plot(range(len(tcpa[i])), tcpa[i], color=color_set[i], linestyle="-",
                        label=f"{ts_ships_mmsi[i]}")
        # 更新坐标轴范围

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
        theta = np.radians(90 - angle)  # 转换为弧度并调整为正北方向
        x = np.cos(theta)
        y = np.sin(theta)
        axes[0, 2].quiver(0, 0, x, y, angles='xy', scale_units='xy', scale=1, color=color_set[i], label=f'{angle:.2f}°')
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
        theta = np.radians(90 - angle)  # 转换为弧度并调整为正北方向
        x = np.cos(theta)
        y = np.sin(theta)
        axes[1, 2].quiver(0, 0, x, y, angles='xy', scale_units='xy', scale=1, color=color_set[i], label=f'{angle:.2f}°')
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
    plt.pause(0.1)   # 暂停一段时间以便观察
