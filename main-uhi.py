import socket
import traceback
from pynput import keyboard
import TargetShipSet
import time
import numpy as np
import matplotlib.pyplot as plt
from Tools import convert_latlon_to_xy
from Tools import Encounter_scenario_decision_making
import path_planning_plot
import invariant_waypoint_update
from global_land_mask import globe
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

# 初始化通信地址和端口
me_listening_socket = None
remote_ip = ('127.0.0.1')
me_listening_port = 8090  # 本脚本（控制器）监听的端口号
remote_port = int(8080)  # 远端程序（模拟器）监听的端口号
# me_listening_port = 60001  # 本脚本（控制器）监听的端口号
# remote_port = int(60000)  # 远端程序（模拟器）监听的端口号
me_sending_port = 50000  # 本demo发出数据使用的端口

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


def on_release(key):
    '松开按键时执行。'
    global r1, r2, t1, t2
    # global r1,t1
    # print('{0} released'.format(key))
    # FIXME 单桨单舵船舶，控制q和a是加减舵角，i和k是加减转速
    # FIXME 舵角范围是正负35度，转速是正负10
    if format(key.char) == 'q':
        r1 += 1
        print('Port Rudder', r1)
    elif format(key.char) == 'w':
        r2 += 1
        print('StarB Rudder', r2)
    elif format(key.char) == 'a':
        r1 -= 1
        print('Port Rudder', r1)
    elif format(key.char) == 's':
        r2 -= 1
        print('StarB Rudder', r2)
    elif format(key.char) == 'u':
        t1 += 1
        print('Port Tele', t1)
    elif format(key.char) == 'i':
        t2 += 1
        print('StarB Tele', t2)
    elif format(key.char) == 'j':
        t1 -= 1
        print('Port Tele', t1)
    elif format(key.char) == 'k':
        t2 -= 1
        print('StarB Tele', t2)
    else:
        print('nor')
    if key == keyboard.Key.esc:
        # Stop listener
        return False


def detect_change(previous_value, current_value):
    """检测值是否从 1 变为 2 或从 2 变为 1"""
    if previous_value == 1 and current_value == 2:
        return 2
    elif previous_value == 2 and current_value == 1:
        return 1
    return None  # 没有变化


def listen_channel_func():
    # ================================
    # 与目标端口建立通信
    # ================================
    try:
        # ====================================================================================================
        # 参数历史数据保存
        history_trajectory_os = []  # 记录历史轨迹
        history_trajectory_ts = []  # 记录历史轨迹
        pre_condition_num = [0]
        history_distance = []
        history_dcpa = []
        history_tcpa = []
        # =====================================================================================================
        print("建立监听,本地监听端口号是：%s" % (me_listening_port,))
        me_listening_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        me_listening_socket.bind(('', me_listening_port))
        # ================================================================================================
        # ================================================================================================
        # 首次接收数据
        receive_data, remote_address = me_listening_socket.recvfrom(1024)
        a = receive_data.decode('utf-8')
        # 获得本船首个位置
        # ================================================================================================
        (norx, hdsRudderPS, hdsRudderSB, hdsTelePS, hdsTeleSB, hdsThrBow, hdsThrStern, Latitude, Longitude,
         LateralSpeed, LongitudinalSpeed, Heading, NEDe, NEDn, Pitch, Roll, nory) = a.split(',')
        # os 数据获取
        lat_os_start = float(Latitude)
        lon_os_start = float(Longitude)
        lat_speed_start = float(LateralSpeed)
        lon_speed_start = float(LongitudinalSpeed)
        sog_os_start = np.sqrt(lat_speed_start ** 2 + lon_speed_start ** 2)
        cog_os_start = float(Heading)
        # ========================================================================
        # os数据转化
        os_ship_start = [lon_os_start, lat_os_start, sog_os_start, cog_os_start]
        os_ship_start = convert_latlon_to_xy.ship_latlon_to_xy(os_ship_start)
        reference_point_x = os_ship_start[0]
        reference_point_y = os_ship_start[1]
        # os_ship_start[2] = os_ship_start[2] * 0.51444 # 模拟器输出的航速是m/s
        sog_os_min = 0.5 * os_ship_start[2]
        # =========================================================================
        #  ts 数据获取转化
        ts_data = TargetShipSet.ship_ts(lon_os_start, lat_os_start)
        ts_ships = []  # 定于空列表存放目标船数据
        ts_ships_length = []  # 定义空列表存放目标船船长
        ts_ships_mmsi = []  # 定义空列表存放目标船mmsi
        ts_ships_name = []  # 定义空列表存放目标船船名
        for i in range(len(ts_data)):
            ts_ships.append([])
            history_trajectory_ts.append([])
            history_distance.append([])
            history_dcpa.append([])
            history_tcpa.append([])
        for i in range(len(ts_ships)):
            ts_ships_length.append(ts_data[i][-3])
            ts_ships_mmsi.append(ts_data[i][-2])
            ts_ships_name.append(ts_data[i][-1])
            ts_data[i] = ts_data[i][:-3]
            ts_ships[i] = convert_latlon_to_xy.ship_latlon_to_xy(ts_data[i])
            ts_ships[i][2] = ts_ships[i][2] * 0.51444
            if ts_ships[i][2] == 0:
                ts_ships[i][2] += 0.15
        for i in range(len(ts_ships)):
            ts_ships[i][0] = ts_ships[i][0] - os_ship_start[0]
            ts_ships[i][1] = ts_ships[i][1] - os_ship_start[1]
            # # roll_os = 0.1
        time_interval = 1
        m = 1852  # 1 海里 = 1852 米
        safe_tcpa = 10
        safe_dcpa = 0.5
        max_turn_angle = [10, 15]
        invariant_waypoint = []
        invariant_shipmeet = [0]
        invariant_index = [float('inf')]
        navigation_state = 'front'
        f1, f2, f3, f4, f5, f6 = [-6, 6, 67.5, 112.5, 180, -112.5]
        # 绘图窗口建立
        # =====================================================================================================
        plt.ion()
        # 创建一个包含 2x2 子图的图形
        fig, axes = plt.subplots(2, 3, figsize=(12, 8))
        plt.gcf().canvas.mpl_connect('key_release_event', lambda event: [exit(0) if event.key == 'escape' else None])
        while True:
            receive_data, remote_address = me_listening_socket.recvfrom(1024)
            a = receive_data.decode('utf-8')
            (norx, hdsRudderPS, hdsRudderSB, hdsTelePS, hdsTeleSB, hdsThrBow, hdsThrStern, Latitude, Longitude,
             LateralSpeed, LongitudinalSpeed, Heading, NEDe, NEDn, Pitch, Roll, nory) = a.split(',')
            lat_os = float(Latitude)
            lon_os = float(Longitude)
            cog_os = float(Heading)
            lat_speed = float(LateralSpeed)
            lon_speed = float(LongitudinalSpeed)
            roll_os = float(Roll)
            sog_os = np.sqrt(lat_speed ** 2 + lon_speed ** 2)
            # print(sog_os)
            # ================================================================================================
            # ================================================================================================
            #  本船与目标船数据获取与转换
            # ====================================================
            os_ship = [lon_os, lat_os, sog_os, cog_os]
            if sog_os == 0:
                continue
            os_ship = convert_latlon_to_xy.ship_latlon_to_xy(os_ship)
            os_ship[0] = os_ship[0] - os_ship_start[0]
            os_ship[1] = os_ship[1] - os_ship_start[1]
            # os_ship[2] = os_ship[2] * 0.51444  # 模拟器本船速度未
            for i in range(len(ts_ships)):
                TargetShipSet.update_ship_state(ts_ships[i], time_interval)
            start_time = time.time()
            # ===================================================================================================
            # 计算避碰算法参数
            (waypoint, cpa, avoid_ship_label, colAvoShipCount, colAvoNegShipCount, colAvoEmgShipCount, osAvoResp,
             shipMeetProp, shipColAvoProp, shipDCPA, shipTCPA, shipBearing, shipDistance, os_shipBearing, emg_situation)\
                = (Encounter_scenario_decision_making.multi_ship_scenario_waypoint(
                   os_ship, ts_ships, safe_dcpa, safe_tcpa, sog_os_min, ts_ships_length, max_turn_angle, m, f1, f2, f3, f4, f5, f6))
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
                                                                                       shipTCPA, shipDCPA, safe_dcpa, m,
                                                                                       safe_tcpa, cog_os_start,
                                                                                       navigation_state)
            navigation_state = navigation_state_pre
            print(invariant_waypoint)
            x_os, y_os, sog_os, cog_os = os_ship
            sog_vector_os = np.array(
                [sog_os * math.sin(math.radians(cog_os)), sog_os * math.cos(math.radians(cog_os)), 0])
            relative_invariant_vector = np.array(
                [invariant_waypoint[0][0] - x_os, invariant_waypoint[0][1] - y_os, 0])
            ang_invariant_waypoint = invariant_waypoint_update.angle_of_vector(sog_vector_os,
                                                                               relative_invariant_vector)
            print(ang_invariant_waypoint)
            if ang_invariant_waypoint > max_turn_angle[0]:
                invariant_waypoint[0] = [x_os + 2 * safe_dcpa * m * math.sin(math.radians(cog_os + max_turn_angle[0])),
                                         y_os + 2 * safe_dcpa * m * math.cos(math.radians(cog_os + max_turn_angle[0]))]
            elif ang_invariant_waypoint < -max_turn_angle[0]:
                invariant_waypoint[0] = [
                    x_os + 2 * safe_dcpa * m * math.sin(math.radians(cog_os - max_turn_angle[0])),
                    y_os + 2 * safe_dcpa * m * math.cos(math.radians(cog_os - max_turn_angle[0]))]
            print(navigation_state)
            print(invariant_waypoint)
            # ================================================================================================
            # 记录本船和目标船历史数据
            history_trajectory_os.append((os_ship[0], os_ship[1]))
            for i in range(len(ts_ships)):
                history_trajectory_ts[i].append((ts_ships[i][0], ts_ships[i][1]))
            for i in range(len(history_distance)):
                history_distance[i].append(shipDistance[i])
                history_dcpa[i].append(shipDCPA[i])
                history_tcpa[i].append(shipTCPA[i])
            # print(invariant_waypoint[0])
            # ==========================================================================================================
            path_planning_plot.path_planning_plot(invariant_waypoint[0], cpa, avoid_ship_label, colAvoShipCount,
                                                  colAvoNegShipCount, colAvoEmgShipCount, osAvoResp,
                                                  shipMeetProp, shipColAvoProp, shipDCPA, shipTCPA, shipBearing,
                                                  shipDistance, os_ship, ts_ships, reference_point_x, reference_point_y,
                                                  ts_ships_mmsi, ts_ships_name, history_trajectory_os, history_trajectory_ts,
                                                  history_distance, history_dcpa, history_tcpa, axes, os_shipBearing,
                                                  start_time, navigation_state)
    except Exception as e:
        print("建立监听失败，退出监听remote数据")
        print("错误信息:", str(e))  # 输出错误信息
        traceback.print_exc()  # 输出详细的错误堆栈信息
    finally:
        print("建立监听成功！")
        if me_listening_socket is not None:
            # me_listening_socket.close()
            me_listening_socket = None


if __name__ == "__main__":
    listen_channel_func()
    # ship_rpm = 10
    # delta_cmd_deg = [0]
    # for i in range(len(delta_cmd_deg)):
    #     send_channel_func(delta_cmd_deg[i], ship_rpm)



