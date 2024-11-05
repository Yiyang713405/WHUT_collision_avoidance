import math
import numpy as np


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


def ship_ts(lon_os, lat_os):
    ts_dict = {
        "tsData": [
            {
                "aisShipMmsi": 420002931,
                "shipName": "YinHe",
                "shipLength": 160,
                "shipCos": -20,
                "shipHdg": 0,
                "shipPosLat": lat_os - 0.005,
                "shipPosLon": lon_os + 0.015,
                "shipSpd": 12
            },
            # {
            #     "aisShipMmsi": 420002932,
            #     "shipName": "YinHe",
            #     "shipLength": 160,
            #     "shipCos": 15,
            #     "shipHdg": 0,
            #     "shipPosLat": lat_os + 0.002,
            #     "shipPosLon": lon_os - 0.01,
            #     "shipSpd": 10
            # },
            # {
            #     "aisShipMmsi": 420002933,
            #     "shipName": "YinHe",
            #     "shipLength": 160,
            #     "shipCos": -15,
            #     "shipHdg": 0,
            #     "shipPosLat": lat_os + 0.002,
            #     "shipPosLon": lon_os + 0.010,
            #     "shipSpd": 10
            # }
        ]
    }

    ts_ships = [
                    [
                        ship.get('shipPosLon', None),
                        ship.get('shipPosLat', None),
                        ship.get('shipSpd', None),
                        ship.get('shipCos', None),
                        ship.get('shipLength', None),
                        ship.get('aisShipMmsi', None),
                        ship.get('shipName', None)
                    ] for ship in ts_dict['tsData']
                ]
    return ts_ships



