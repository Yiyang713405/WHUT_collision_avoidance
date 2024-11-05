import Encounter_scenario_decision_making
import numpy as np
import math


def cross_product(vector_a, vector_b):
    return [
        vector_a[1] * vector_b[2] - vector_a[2] * vector_b[1],  # i component
        vector_a[2] * vector_b[0] - vector_a[0] * vector_b[2],  # j component
        vector_a[0] * vector_b[1] - vector_a[1] * vector_b[0],  # k component
    ]


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
        position_angle_cr = cross_product(v_os, v_ts)[2]
        position_angle_cr = round(position_angle_cr, 2)
        if position_angle_cr > 0:
            angle_vp = -ang
        else:
            angle_vp = ang
    return angle_vp


def waypoint_choose(invariant_waypoint, waypoint, os_ship, avoid_ship_label, shipMeetProp, emg_situation,
                    invariant_index, invariant_shipmeet, shipTCPA, shipDCPA, safe_dcpa, m, safe_tcpa, cog_os_start, navigation_state):
    x_os, y_os, sog_os, cog_os = os_ship
    sog_vector_os = np.array([sog_os * math.sin(math.radians(cog_os)), sog_os * math.cos(math.radians(cog_os)), 0])
    relative_waypoint_pre_vector = np.array([invariant_waypoint[0][0] - x_os, invariant_waypoint[0][1] - y_os, 0])
    relative_waypoint_now_vector = np.array([waypoint[0] - x_os, waypoint[1] - y_os, 0])
    # ang_vp_pre = angle_of_vector(sog_vector_os, relative_waypoint_pre_vector)
    ang_vp_now = angle_of_vector(sog_vector_os, relative_waypoint_now_vector)
    navigation_state_pre = navigation_state
    navigation_state_now = 'front'
    direct_waypoint = [os_ship[0] + sog_os * math.sin(math.radians(cog_os)) * safe_tcpa * 60,
                       os_ship[1] + sog_os * math.cos(math.radians(cog_os)) * safe_tcpa * 60]
    distance_to_waypoint = (Encounter_scenario_decision_making.calculate_distance
                            (os_ship[0], os_ship[1], invariant_waypoint[0][0], invariant_waypoint[0][1]))
    # 本船和路径点的距离
    os_invariant_waypoint_vector = [invariant_waypoint[0][0] - os_ship[0],  # 本船当前位置和固定路径点的向量
                                    invariant_waypoint[0][1] - os_ship[1]]
    # 本船当前位置和固定路径点的向量
    v_os = np.array(
        [sog_os * math.sin(math.radians(cog_os)), sog_os * math.cos(math.radians(cog_os))])  # 本船的速度向量
    angle_os_invariant_waypoint = Encounter_scenario_decision_making.angle_of_vector(v_os,
                                                                                     os_invariant_waypoint_vector)  # 本船速度向量与本船和路径点连线的向量夹角
    if cog_os_start > 180:  # cog_os_start可以修改为设定的航向或者牵引点航向，用来引导船在避让结束之后回到原航向上
        cog_os_start = cog_os_start - 360
    if cog_os > 180:
        cog_os = cog_os - 360
    # print('invariant_index', invariant_index[0])
    if ang_vp_now < 0:
        navigation_state_now = 'left'
    if ang_vp_now == 0:
        navigation_state_now = navigation_state
    if ang_vp_now > 0:
        navigation_state_now = 'right'
    # ==========================================================================================================
    # if abs(ang_vp_pre) < 4:   # 当本船航向与建议航向之间夹角小于1°，此时认为转到建议航向
    #     ang_vp_pre = 0
    if (avoid_ship_label != float('inf') and (
            shipMeetProp[avoid_ship_label] == 4 or shipMeetProp[avoid_ship_label] == 5)
            and emg_situation[avoid_ship_label] == 1):
            # and not
            # (avoid_ship_label == invariant_index[0] and shipMeetProp[avoid_ship_label] == invariant_shipmeet[0])):
        # 判断路径点是否需要变化
        # if (ang_vp_pre <= 0 and ang_vp_now < 0) or (ang_vp_pre >= 0 and ang_vp_now > 0) or invariant_shipmeet[0] == 0:
        if (navigation_state_pre == 'front' or (navigation_state_pre == 'left' and navigation_state_now == 'left') or
                (navigation_state_pre == 'right' and navigation_state_now == 'right')):
            invariant_waypoint[0] = waypoint
            invariant_shipmeet[0] = shipMeetProp[avoid_ship_label]
            invariant_index[0] = avoid_ship_label
            navigation_state_pre = navigation_state_now
    if ((avoid_ship_label != float('inf') and not (shipMeetProp[avoid_ship_label] == 4 or
                                                   shipMeetProp[avoid_ship_label] == 5 or shipMeetProp[
                                                       avoid_ship_label] == 0) and
         waypoint != invariant_waypoint[0] and waypoint != direct_waypoint)):
            #      and not
    # (avoid_ship_label == invariant_index[0] and shipMeetProp[avoid_ship_label] == invariant_shipmeet[0])):
        # if (ang_vp_pre <= 0 and ang_vp_now < 0) or (ang_vp_pre >= 0 and ang_vp_now > 0) or invariant_shipmeet[0] == 0:
        if (navigation_state_pre == 'front' or (navigation_state_pre == 'left' and navigation_state_now == 'left') or
                (navigation_state_pre == 'right' and navigation_state_now == 'right')):
            invariant_waypoint[0] = waypoint
            invariant_shipmeet[0] = shipMeetProp[avoid_ship_label]
            invariant_index[0] = avoid_ship_label
            navigation_state_pre = navigation_state_now
    # ==========================================================================================================
    elif distance_to_waypoint < 150 or angle_os_invariant_waypoint > 90:
        # 判断是否到达路径点,何时回到原航向
        if shipTCPA:
            if not (max(abs(value) for value in shipTCPA) == 0 and abs(os_ship[0]) >= 1.5 * safe_dcpa * m):
                invariant_waypoint.clear()
                invariant_waypoint.append(waypoint)
        else:
            invariant_waypoint.clear()
            invariant_waypoint.append(waypoint)
    # if avoid_ship_label == float('inf') and (max(abs(value) for value in shipTCPA) == 0 and
    #                                          abs(os_ship[0]) >= 1.5 * safe_dcpa * m) or abs(
    #     cog_os - cog_os_start) > 80:
    if avoid_ship_label == float('inf') and (max(abs(value) for value in shipTCPA) == 0
                                    or (len(shipDCPA) > 1 and min(abs(value) for value in shipDCPA)) > safe_dcpa * m):
        towing_point = [
            os_ship[0] + os_ship[2] * math.sin(math.radians(cog_os_start)) * safe_tcpa * 60,
            os_ship[1] + os_ship[2] * math.cos(math.radians(cog_os_start)) * safe_tcpa * 60]
        invariant_waypoint[0] = towing_point
        invariant_shipmeet[0] = [0]
        invariant_index[0] = float('inf')
        navigation_state_pre = 'front'
    return invariant_waypoint, navigation_state_pre


# 添加场景判断，如果是从初始无风险场景切换到有风险场景，则需要更新固定路径点
# 转到建议航向之后保持固定
# 转到建议航向之后如果发生对遇场景，就继续更新路径点
# 对前一时刻的转向进行记录
