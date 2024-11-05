import numpy as np
import math


def calculate_dcpa_tcpa(x_os, y_os, sog_os, cog_os, x_ts, y_ts, sog_ts, cog_ts):
    """
    计算两船的DCPA和TCPA
    :param x_os: 自船的 x 坐标
    :param y_os: 自船的 y 坐标
    :param sog_os: 自船的航速
    :param cog_os: 自船的航向
    :param x_ts: 他船的 x 坐标
    :param y_ts: 他船的 y 坐标
    :param sog_ts: 他船的航速
    :param cog_ts: 他船的航向
    :return: (dcpa, tcpa)
    """
    dx = x_ts - x_os
    dy = y_ts - y_os

    # 计算速度分量
    d_vx = sog_ts * math.sin(math.radians(cog_ts)) - sog_os * math.sin(math.radians(cog_os))
    d_vy = sog_ts * math.cos(math.radians(cog_ts)) - sog_os * math.cos(math.radians(cog_os))

    a = d_vx ** 2 + d_vy ** 2
    if math.isclose(a, 0.0):
        # 两船速度和方向相同
        dcpa = math.sqrt(dx ** 2 + dy ** 2)
        tcpa = float('inf')
        return dcpa, tcpa

    b = d_vx * dx + d_vy * dy
    c = dx ** 2 + dy ** 2

    # 计算时间
    t = -b / a

    if t < 0:
        # DCPA 就是当前的距离，TCPA 已经过了
        dcpa = math.sqrt(c)
        tcpa = 0
        return dcpa, tcpa

    dcpa_sq = c - b ** 2 / a
    dcpa_sq = max(dcpa_sq, 0)  # 确保 dcpa_sq 不小于 0

    dcpa = math.sqrt(dcpa_sq)
    tcpa = t
    return dcpa, tcpa


def radius_aft(v_ts, ts_ship_length):
    """
    计算船舶领域半径
    :param v_ts:
    :param ts_ship_length:
    :return:
    """
    k_ad = 10 ** (0.3591 * math.log10(v_ts/0.51444) + 0.0952)  # 航速单位是米，转化为海里/h
    k_dt = 10 ** (0.5441 * math.log10(v_ts/0.51444) - 0.0795)
    r_aft = (1 + 0.67 * math.sqrt(k_ad ** 2 + (k_dt / 2) ** 2)) * ts_ship_length * 1.5  # 本船船舶领域的后侧半径
    return r_aft


def takeover_waypoint(cog_os, ang_vp_ot, distance_ot, safe_dcpa,  x_os,  y_os):
    """
    计算追越场景下本船的路径带你
    :param cog_os: 本船航向
    :param ang_vp_ot: 目标船相对于本船的位置角度
    :param distance_ot: 本船和目标船之间的距离
    :param safe_dcpa: dcpa安全阈值
    :param x_os: 本船x坐标
    :param y_os: 本船y坐标
    :return:
    """
    d_x = abs(distance_ot * math.sin(math.radians(ang_vp_ot)))
    d_y = abs(distance_ot * math.cos(math.radians(ang_vp_ot)))  # 本船和目标船之间的距离在本船航向上的分量
    distance_waypoint_right = math.sqrt((1.5 * safe_dcpa + d_x) ** 2 + d_y ** 2)  # 计算本船到路径点之间的距离
    distance_waypoint_left = math.sqrt((1.5 * safe_dcpa - d_x) ** 2 + d_y ** 2)

    # 计算夹角（以度数表示）
    angle_a_rad_right = math.asin((1.5 * safe_dcpa + d_x) / distance_waypoint_right)  # 使用 atan2 函数防止除以零
    angle_a_deg_right = math.degrees(angle_a_rad_right)  # 转换为度数

    # print(angle_a_deg_right)
    angle_a_rad_left = math.asin((1.5 * safe_dcpa - d_x) / distance_waypoint_left)  # 使用 atan2 函数防止除以零
    angle_a_deg_left = math.degrees(angle_a_rad_left)  # 转换为度数

    # print(angle_a_deg_left)
    cog_waypoint_right = angle_a_deg_right + cog_os
    cog_waypoint_left = angle_a_deg_left + cog_os  # 路径点和正北方向上的实际夹角

    waypoint_right = [x_os + distance_waypoint_right * math.sin(math.radians(cog_waypoint_right)),
                      y_os + distance_waypoint_right * math.cos(math.radians(cog_waypoint_right))]
    waypoint_left = [x_os + distance_waypoint_left * math.sin(math.radians(cog_waypoint_left)),
                     y_os + distance_waypoint_left * math.cos(math.radians(cog_waypoint_left))]  # 对遇场景路径点
    return waypoint_right, waypoint_left


def headon_waypoint(cog_os, ang_vp_ot, distance_ot, safe_dcpa,  x_os,  y_os):
    d_x = abs(distance_ot * math.sin(math.radians(ang_vp_ot)))
    d_y = abs(distance_ot * math.cos(math.radians(ang_vp_ot)))
    distance_waypoint_right = math.sqrt((1.5 * safe_dcpa - d_x) ** 2 + d_y ** 2)
    distance_waypoint_left = math.sqrt((1.5 * safe_dcpa - d_x) ** 2 + d_y ** 2)
    # 计算夹角（以度数表示）
    angle_a_rad_right = math.asin((1.5 * safe_dcpa - d_x) / distance_waypoint_right)  # 使用 atan2 函数防止除以零
    angle_a_deg_right = math.degrees(angle_a_rad_right)  # 转换为度数
    # print(angle_a_deg_right)
    angle_a_rad_left = math.asin((1.5 * safe_dcpa - d_x) / distance_waypoint_left)  # 使用 atan2 函数防止除以零
    angle_a_deg_left = math.degrees(angle_a_rad_left)  # 转换为度数
    # print(angle_a_deg_left)
    cog_waypoint_right = cog_os - angle_a_deg_right
    cog_waypoint_left = cog_os + angle_a_deg_left

    waypoint_right = [x_os + distance_waypoint_right * math.sin(math.radians(cog_waypoint_right)),
                      y_os + distance_waypoint_right * math.cos(math.radians(cog_waypoint_right))]
    waypoint_left = [x_os + distance_waypoint_left * math.sin(math.radians(cog_waypoint_left)),
                     y_os + distance_waypoint_left * math.cos(math.radians(cog_waypoint_left))]
    return waypoint_right, waypoint_left


def angle_of_vector(v_os, v_ts):
    """
    计算向量间的夹角
    :param v_os:向量
    :param v_ts: 向量
    :return:夹角
    """
    with np.errstate(invalid='ignore'):
        vector_prod = v_os[0] * v_ts[0] + v_os[1] * v_ts[1]
        length_prod = math.sqrt(pow(v_os[0], 2) + pow(v_os[1], 2)) * math.sqrt(pow(v_ts[0], 2) + pow(v_ts[1], 2))
        cos = vector_prod/length_prod
        cos = max(-1, min(1, cos))  # 限制 cos 的范围在 -1 到 1 之间
        angle = math.acos(cos)
        ang = angle * 180/np.pi
    return ang


def calculate_distance(x_os, y_os, x_ts, y_ts):
    """
    计算两船之间的距离
    :param x_os:
    :param y_os:
    :param x_ts:
    :param y_ts:
    :return:
    """
    # 计算水平距离和垂直距离
    horizontal_distance = abs(x_ts - x_os)
    vertical_distance = abs(y_ts - y_os)
    # 计算斜边距离（两点之间的直线距离）
    distance = math.sqrt(horizontal_distance ** 2 + vertical_distance ** 2)
    return distance


def cross_product(vector_a, vector_b):
    return [
        vector_a[1] * vector_b[2] - vector_a[2] * vector_b[1],  # i component
        vector_a[2] * vector_b[0] - vector_a[0] * vector_b[2],  # j component
        vector_a[0] * vector_b[1] - vector_a[1] * vector_b[0],  # k component
    ]


def real_angle(x_os, y_os, sog_os, cog_os, x_ts, y_ts, sog_ts, cog_ts):
    """
    计算向量的实际夹角，因为夹角计算函数得到的是向量夹角的绝对值，要转换为实际值
    :param x_os:
    :param y_os:
    :param sog_os:
    :param cog_os:
    :param x_ts:
    :param y_ts:
    :param sog_ts:
    :param cog_ts:
    :return:
    """
    sog_vector_os = np.array([sog_os * math.sin(math.radians(cog_os)), sog_os * math.cos(math.radians(cog_os)), 0])
    sog_vector_ts = np.array([sog_ts * math.sin(math.radians(cog_ts)), sog_ts * math.cos(math.radians(cog_ts)), 0])
    relative_position_vector = np.array([x_ts - x_os, y_ts - y_os, 0])

    angle_vp_ot = angle_of_vector(sog_vector_os, relative_position_vector)
    angle_v_ot = angle_of_vector(sog_vector_os, sog_vector_ts)

    # 计算二维向量叉积的标量值
    position_angle_cr = cross_product(sog_vector_os, relative_position_vector)[2]  # 根据叉乘得到的数值判断夹角的正负
    sog_angle_cr = cross_product(sog_vector_os, sog_vector_ts)[2]
    # position_angle_cr = round(position_angle_cr, 2)
    # sog_angle_cr = round(sog_angle_cr, 2)

    # 只考虑叉积在z轴上的分量
    if position_angle_cr > 0:
        angle_vp_ot = -angle_vp_ot
    # elif position_angle_cr == 0:
    #     angle_vp_ot = 0
    else:
        angle_vp_ot = angle_vp_ot

    if sog_angle_cr > 0:
        angle_v_ot = -angle_v_ot
    # elif sog_angle_cr == 0:
    #     angle_v_ot = 180
    else:
        angle_v_ot = angle_v_ot

    return angle_vp_ot, angle_v_ot


def single_ship_scenario_waypoint(ship_os, ship_ts, ts_ship_length, safe_dcpa, safe_tcpa, max_turn_angle,
                                  m, f1, f2, f3, f4, f5, f6):
    """
    计算两船的路径点
    :param ship_os: 船舶状态参数元组
    :param ship_ts:
    :param ts_ship_length: 船长
    :param safe_dcpa: 安全dcpa
    :param safe_tcpa: 安全tcpa
    :param max_turn_angle: 对遇场景转角
    :return:
    """
    # -------------------------------------------------------------------------------------------------------
    # 单位转换，经纬度转换
    safe_dcpa = safe_dcpa * m
    safe_tcpa = safe_tcpa * 60
    emg_num = 0
    x_os, y_os, sog_os, cog_os = ship_os
    x_ts, y_ts, sog_ts, cog_ts = ship_ts
    sog_os_y = abs(sog_os * math.cos(math.radians(cog_os)))
    sog_ts_y = abs(sog_ts * math.cos(math.radians(cog_ts)))  # 船舶航速在y方向上的分量
    # 计算目标船的领域半径
    r_aft = radius_aft(sog_ts, ts_ship_length)  # 单位米
    # 计算两船的dcpa和tcpa
    dcpa, tcpa = calculate_dcpa_tcpa(x_os, y_os, sog_os, cog_os, x_ts, y_ts, sog_ts, cog_ts)
    dcpa = round(dcpa, 2)
    tcpa = round(tcpa, 2)
    shipmeetprop = 0  # 他船会遇属性（0：初始状态，1：被追越，2：右前方船， 3：有横后方船， 4：后方来船， 5：左舷来船， 6：对遇）
    # -------------------------------------------------------------------------------------------------------
    # 判断两船距离是否在6海里范围内
    distance_os_ts = calculate_distance(x_os, y_os, x_ts, y_ts)
    waypoint = [x_os + sog_os * math.sin(math.radians(cog_os)) * safe_tcpa,
                y_os + sog_os * math.cos(math.radians(cog_os)) * safe_tcpa]
    angle_vp_ot, angle_v_ot = real_angle(x_os, y_os, sog_os, cog_os, x_ts, y_ts, sog_ts, cog_ts)
    angle_vp_to, angle_v_to = real_angle(x_ts, y_ts, sog_ts, cog_ts, x_os, y_os, sog_os, cog_os)
    headon_waypoint_right, headon_waypoint_left = headon_waypoint(cog_os, angle_vp_ot, distance_os_ts, safe_dcpa, x_os, y_os)
    takeover_waypoint_right, takeover_waypoint_left = takeover_waypoint(cog_os, angle_vp_ot, distance_os_ts, safe_dcpa, x_os,  y_os)
    if dcpa <= safe_dcpa and 0 < tcpa <= safe_tcpa:  # 有风险的情况下判断会遇态势
        # 判断两船相遇场景
        #  给出路径点，然后船舶按照路径点航行直到dcpa和tcpa到安全范围，回到原航向，继续航行，直到两船错过，回到原航线
        #  1、追越场景--------------------------------------------------------------
        if (f1 <= angle_v_ot <= f2) and (sog_os_y > sog_ts_y) and (-90 < angle_vp_ot < 90):     # 与本船航速夹角-6到6，在本船前方，速度小于本船
            if dcpa == 0 or angle_vp_ot < 0:
                waypoint = takeover_waypoint_left
                shipmeetprop = 1
            else:
                waypoint = takeover_waypoint_right
                shipmeetprop = 1
        if (f1 <= angle_vp_ot <= f2) and (-30 < angle_v_ot < 30):  # 在本船前方-6到6的区域内，与本船航速夹角-90到90
            if angle_vp_ot < 0:
                waypoint = takeover_waypoint_left
                shipmeetprop = 1
            else:
                waypoint = takeover_waypoint_right
                shipmeetprop = 1
        if f4 < angle_vp_to < f5 and f2 <= angle_v_ot < f3:
            headon_waypoint_right, headon_waypoint_left = headon_waypoint(cog_os, angle_vp_ot, distance_os_ts,
                                                                          safe_dcpa, x_os, y_os)
            waypoint = takeover_waypoint_left
            shipmeetprop = 1
        if -f5 < angle_vp_to < f6 and -f3 <= angle_v_ot < f1:
            waypoint = takeover_waypoint_right
            shipmeetprop = 1
        #  2、计算对遇场景路径点-----------------------------------------------------------
        if (-f5 <= angle_v_ot <= (-f5 + f2) or (f5 - f2) <= angle_v_ot <= f5) and (-90 < angle_vp_ot < 90):
            if dcpa == 0 or angle_vp_ot < 0:
                waypoint = headon_waypoint_left
                shipmeetprop = 6
            else:
                waypoint = headon_waypoint_right
                shipmeetprop = 6
        if (f1 <= angle_vp_ot <= f2) and (-f5 <= angle_v_ot <= (-f5 + 30) or (f5 - 30) <= angle_v_ot <= f5):
            # 在本船前方-6到6的区域内，与本船航速夹角
            if angle_vp_ot < 0:
                waypoint = headon_waypoint_left
                shipmeetprop = 6
            else:
                waypoint = headon_waypoint_right
                shipmeetprop = 6
        #  4、计算交叉会遇场景路径点-----------------------------------------------------------
        if not (-f5 < angle_vp_to < f6 or f4 < angle_vp_to < f5):
            if (f2 < angle_vp_ot <= f3) and ((-f5 + f2) < angle_v_ot < f1):
                cpa = ([x_ts + (sog_ts * math.sin(math.radians(cog_ts)) * tcpa),
                        y_ts + (sog_ts * math.cos(math.radians(cog_ts)) * tcpa), 0])
                waypoint_crossing = [cpa[0] - r_aft * math.sin(math.radians(cog_ts)),
                                     cpa[1] - r_aft * math.cos(math.radians(cog_ts))]
                angle_vp_cpa, angle_v_cpa = real_angle(x_os, y_os, sog_os, cog_os, waypoint_crossing[0],
                                                       waypoint_crossing[1], sog_ts, cog_ts)
                distance_cpa = calculate_distance(x_os, y_os, waypoint_crossing[0], waypoint_crossing[1])
                distance_waypoint = math.sqrt(distance_cpa ** 2 + safe_dcpa ** 2)
                ang_waypoint = math.asin(safe_dcpa / distance_waypoint)  # 使用 atan2 函数防止除以零
                ang_waypoint_deg = math.degrees(ang_waypoint)  # 转换为度数
                cog_waypoint = cog_os + angle_vp_cpa + ang_waypoint_deg
                waypoint = [x_os + distance_waypoint * math.sin(math.radians(cog_waypoint)),
                            y_os + distance_waypoint * math.cos(math.radians(cog_waypoint))]
                shipmeetprop = 2
            # ---------------------------------------------------
            # 特殊情况，本船右转或者减速
            elif f3 <= angle_vp_ot <= f4 and f6 <= angle_v_ot < 0:
                if cog_ts > 180:
                    cog_ts = cog_ts - 360
                if f6 <= cog_ts < -f3:
                    waypoint = [x_os + 3 * safe_dcpa * math.sin(math.radians(cog_os - max_turn_angle[0])),
                                y_os + 3 * safe_dcpa * math.cos(math.radians(cog_os - max_turn_angle[0]))]
                if -f3 <= cog_ts < 0:
                    if abs(x_os - x_ts) >= 1.1 * safe_dcpa:
                        waypoint = [x_os + 2 * safe_dcpa * math.sin(math.radians(cog_ts)),
                                    y_os + 2 * safe_dcpa * math.cos(math.radians(cog_ts))]
                    else:
                        waypoint = [x_os + 2 * safe_dcpa * math.sin(math.radians(cog_ts - max_turn_angle[0])),
                                    y_os + 2 * safe_dcpa * math.cos(math.radians(cog_ts - max_turn_angle[0]))]
                shipmeetprop = 3
        # 5、 目标船在本船112.5°到-112.5°
        if not (-f5 < angle_vp_to < f6 or f4 < angle_vp_to < f5):
            if f4 <= angle_vp_ot <= f5 or -f5 <= angle_vp_ot < f6:
                waypoint = [x_os + sog_os * math.sin(math.radians(cog_os)) * safe_tcpa,
                            y_os + sog_os * math.cos(math.radians(cog_os)) * safe_tcpa]
                if ((0 < tcpa < 0.8 * safe_tcpa) and (0 < dcpa < safe_dcpa) and (f4 <= angle_vp_ot < f5)
                        and (-f3 < angle_v_ot < 0)):
                    if abs(x_os - x_ts) > 1.1 * safe_dcpa:
                        waypoint = [x_os + 2 * safe_dcpa * math.sin(math.radians(cog_ts)),
                                    y_os + 2 * safe_dcpa * math.cos(math.radians(cog_ts))]   # 左转到指定位置
                    else:
                        waypoint = [x_os + 2 * safe_dcpa * math.sin(math.radians(cog_ts - max_turn_angle[0])),
                                    y_os + 2 * safe_dcpa * math.cos(math.radians(cog_ts - max_turn_angle[0]))]
                    emg_num = 1
                elif (0 < tcpa < 0.8 * safe_tcpa) and (0 < dcpa < safe_dcpa) and (-f5 <= angle_vp_ot < f6)\
                        and (0 < angle_v_ot < f3):
                    if abs(x_os - x_ts) > 1.1 * safe_dcpa:
                        waypoint = [x_os + 2 * safe_dcpa * math.sin(math.radians(cog_ts)),
                                    y_os + 2 * safe_dcpa * math.cos(math.radians(cog_ts))]
                    else:
                        waypoint = [x_os + 2 * safe_dcpa * math.sin(math.radians(cog_ts + max_turn_angle[0])),
                                    y_os + 2 * safe_dcpa * math.cos(math.radians(cog_ts + max_turn_angle[0]))]
                    emg_num = 1
                shipmeetprop = 4
            if f6 <= angle_vp_ot < f1 and not (f1 <= angle_v_ot <= f2 or -f5 <= angle_v_ot <= (-f5 + f2) or
                                               (f5 - f2) <= angle_v_ot <= f5):
                waypoint = [x_os + sog_os * math.sin(math.radians(cog_os)) * safe_tcpa,
                            y_os + sog_os * math.cos(math.radians(cog_os)) * safe_tcpa]
                if 0 < tcpa < 0.8 * safe_tcpa and 0 < dcpa < safe_dcpa:
                    waypoint = [x_os + 2 * safe_dcpa * math.sin(math.radians(cog_os + max_turn_angle[0])),
                                y_os + 2 * safe_dcpa * math.cos(math.radians(cog_os + max_turn_angle[0]))]   # 右转到指定位置
                    emg_num = 1  # 紧急避碰参数
                shipmeetprop = 5
    else:
        waypoint = [x_os + sog_os * math.sin(math.radians(cog_os)) * safe_tcpa,
                    y_os + sog_os * math.cos(math.radians(cog_os)) * safe_tcpa]
    return waypoint, dcpa, tcpa, shipmeetprop, angle_vp_ot, distance_os_ts, angle_vp_to, emg_num


def multi_ship_scenario_waypoint(os_ship, ts_ships, safe_dcpa, safe_tcpa, sog_os_min, ts_ships_length, max_turn_angle, m, f1, f2, f3, f4, f5, f6):
    # 初始化参数
    single_dcpa = safe_dcpa
    single_tcpa = safe_tcpa
    safe_dcpa = safe_dcpa * m
    safe_tcpa = safe_tcpa * 60
    x_os, y_os, sog_os, cog_os = os_ship
    avoid_ship_label = float('inf')
    colAvoShipCount = 0   # 避让目标船数量
    colAvoNegShipCount = 0  # 协商避碰数量
    colAvoEmgShipCount = 0  # 紧急避碰数量
    osAvoResp = 0  # 本船避让属性
    shipColAvoProp = []  # 他船避碰属性(1：协商避碰， 2：紧急避碰， 3：无避碰)
    shipDCPA = []  # 记录所有他船的DCPA
    shipTCPA = []  # 记录所有他船的TCPA
    shipBearing = []  # 他船的相对方位
    emg_situation = []
    os_shipBearing = []  # 本船相对与他船的位置
    shipDistance = []  # 他船相对距离
    shipMeetProp = []  # 他船会遇属性
    # ===================================================
    # 定义两个避让区间，设定避让优先级
    risk_ship_dcpa_f = []
    risk_ship_tcpa_f = []
    risk_ship_waypoint_f = []
    risk_ship_index_f = []
    dcpa_f = float('inf')
    tcpa_f = float('inf')
    avoid_ship_label_f = float('inf')
    waypoint_f = [x_os + sog_os * math.sin(math.radians(cog_os)) * safe_tcpa,
                  y_os + sog_os * math.cos(math.radians(cog_os)) * safe_tcpa]
    # ====================================================================================================================
    # 本船左方，后方区间，本船的直航区间
    risk_ship_dcpa_b = []
    risk_ship_tcpa_b = []
    risk_ship_waypoint_b = []
    risk_ship_index_b = []
    dcpa_b = float('inf')
    tcpa_b = float('inf')
    avoid_ship_label_b = float('inf')
    waypoint_b = [x_os + sog_os * math.sin(math.radians(cog_os)) * safe_tcpa,
                  x_os + sog_os * math.cos(math.radians(cog_os)) * safe_tcpa]
    f_num = 0
    for i in range(len(ts_ships)):
        w, d, t, shipmeetprop, angle_vp_ot, distance_os_ts, angle_vp_to, emg_num \
            = single_ship_scenario_waypoint(os_ship, ts_ships[i], ts_ships_length[i], single_dcpa, single_tcpa, max_turn_angle, m, f1, f2, f3, f4, f5, f6)
        shipDCPA.append(d)
        shipTCPA.append(t)
        shipBearing.append(angle_vp_ot)
        os_shipBearing.append(angle_vp_to)
        shipDistance.append(distance_os_ts)
        shipMeetProp.append(shipmeetprop)
        emg_situation.append(emg_num)
        x, y, sog, cog = ts_ships[i]
        # angle_vp, angle_v = real_angle(x_os, y_os, sog_os, cog_os, x, y, sog, cog)
        if t < safe_tcpa and d < safe_dcpa and shipmeetprop != 4 and shipmeetprop != 5:  # 判断处于本船避让区间的风险目标船
            risk_ship_dcpa_f.append(d)
            risk_ship_tcpa_f.append(t)
            risk_ship_index_f.append(i)
            risk_ship_waypoint_f.append(w)
            colAvoShipCount += 1
            f_num += 1
            if 0 < t < 0.8 * safe_tcpa and 0 < d < safe_dcpa:
                colAvoEmgShipCount += 1
                shipColAvoProp.append(2)
            else:
                colAvoNegShipCount += 1
                shipColAvoProp.append(1)

        elif t < safe_tcpa and d < safe_dcpa and (shipmeetprop == 4 or shipmeetprop == 5):  # 处于本船直航区间的风险目标船
            risk_ship_dcpa_b.append(d)
            risk_ship_tcpa_b.append(t)
            risk_ship_index_b.append(i)
            risk_ship_waypoint_b.append(w)
            colAvoShipCount += 1
            if 0 < t < 0.8 * safe_tcpa and 0 < d < safe_dcpa:
                colAvoEmgShipCount += 1
                shipColAvoProp.append(2)
            else:
                colAvoNegShipCount += 1
                shipColAvoProp.append(1)
        else:
            shipColAvoProp.append(3)
    # ==========================================================================================================
    # 针对处于不同区间的目标船，计算各自区间风险最高的船
    # ==========================================================================================================
    # 本船避让区间
    if len(risk_ship_dcpa_f) != 0:
        for k in range(len(risk_ship_dcpa_f)):
            if 0 <= risk_ship_dcpa_f[k] < dcpa_f:  # 有风险的情况下d越小越紧急
                dcpa_f = risk_ship_dcpa_f[k]
                tcpa_f = risk_ship_tcpa_f[k]
                waypoint_f = risk_ship_waypoint_f[k]
                avoid_ship_label_f = risk_ship_index_f[k]
            elif risk_ship_dcpa_f[k] == dcpa_f and risk_ship_tcpa_f[k] < tcpa_f:  # 有风险d相等时，t越小越紧急（少数情况）
                dcpa_f = risk_ship_dcpa_f[k]
                tcpa_f = risk_ship_tcpa_f[k]
                waypoint_f = risk_ship_waypoint_f[k]
                avoid_ship_label_f = risk_ship_index_f[k]
    # 本船直航区间
    if len(risk_ship_dcpa_b) != 0 and len(risk_ship_dcpa_f) == 0:
        for j in range(len(risk_ship_dcpa_b)):
            if 0 <= risk_ship_dcpa_b[j] < dcpa_b:  # 有风险的情况下d越小越紧急
                dcpa_b = risk_ship_dcpa_b[j]
                tcpa_b = risk_ship_tcpa_b[j]
                waypoint_b = risk_ship_waypoint_b[j]
                avoid_ship_label_b = risk_ship_index_b[j]
            elif risk_ship_dcpa_b[j] == dcpa_b and risk_ship_tcpa_b[j] < tcpa_b:  # 有风险d相等时，t越小越紧急（少数情况）
                dcpa_b = risk_ship_dcpa_b[j]
                tcpa_b = risk_ship_tcpa_b[j]
                waypoint_b = risk_ship_waypoint_b[j]
                avoid_ship_label_b = risk_ship_index_b[j]
    # ===============================================================================================================
    # 判断两个区间的风险目标船，设定避让优先级：
    if dcpa_f < safe_dcpa and tcpa_f < safe_tcpa:
        osAvoResp = 1
        x, y, sog, cog = ts_ships[avoid_ship_label_f]
        # angle_vp, angle_v = real_angle(x_os, y_os, sog_os, cog_os, x, y, sog, cog)
        cpa = [x + sog * tcpa_f * math.sin(math.radians(cog)),
               y + sog * tcpa_f * math.cos(math.radians(cog))]
        waypoint = waypoint_f
        avoid_ship_label = avoid_ship_label_f
    elif f_num == 0 and (dcpa_b < safe_dcpa and tcpa_b < safe_tcpa):  # 可能存在问题
        x, y, sog, cog = ts_ships[int(avoid_ship_label_b)]
        cpa = [x + sog * tcpa_b * math.sin(math.radians(cog)),
               y + sog * tcpa_b * math.cos(math.radians(cog))]
        waypoint = waypoint_b
        avoid_ship_label = avoid_ship_label_b
    else:
        waypoint = [x_os + sog_os * math.sin(math.radians(cog_os)) * safe_tcpa,
                    y_os + sog_os * math.cos(math.radians(cog_os)) * safe_tcpa]
        cpa = [os_ship[0], os_ship[1]]
    return (waypoint, cpa, avoid_ship_label, colAvoShipCount, colAvoNegShipCount, colAvoEmgShipCount, osAvoResp,
            shipMeetProp, shipColAvoProp, shipDCPA, shipTCPA, shipBearing, shipDistance, os_shipBearing, emg_situation)


"""计算路径点"""
#
# if __name__ == '__main__':
#     ships = [
#         [31, 121.1, 15, 0],  # 第一条船的坐标和航向
#         [31.02, 121.105, 10, 190],  # 第二条船
#         [30.98, 121.2, 10, 0]
#             ]
#     ships_to_xy = []
#     for i in range(len(ships)):
#         ships_to_xy.append(convert_latlon_to_xy.ship_latlon_to_xy(ships[i]))
#     waypoint = Encounter_Scenario_Judgment_WaypointGet(ships_to_xy[0], ships_to_xy[1], 160, 1000, 600, 30)
#     print(waypoint)


