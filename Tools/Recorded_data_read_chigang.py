import json
import numpy as np
import matplotlib.pyplot as plt
from Tools import shipmodle
import matplotlib.patches as patches
from matplotlib.patches import Circle


# 指定JSON文件的路径
# json_file_path = "D:\\AA船舶避碰\\ColAvoDataRecord\\三船场景32.json"
json_file_path = "D:\\A震兑\\ColAvoData\\ColData_10_29.json"
# 绘图窗口建立
# =====================================================================================================
plt.ion()
# 创建一个包含 2x2 子图的图形
fig, axes = plt.subplots(2, 3, figsize=(12, 8))
plt.gcf().canvas.mpl_connect('key_release_event', lambda event: [exit(0) if event.key == 'escape' else None])
history_trajectory_os = []
try:
    with open(json_file_path, 'r', encoding='utf-8') as file:
        data = json.load(file)
        for i in range(len(data)):
            os_ship = data[i]["os_ship"]
            ts_ships = data[i]["ts_ship"]
            os_shipBearing = data[i]["os_shipBearing"]
            path_point = data[i]["colAvoPathData"]
            coordinate_points = [[point["fastShipPosLon"], point["fastShipPosLat"]] for point in path_point]
            shipMeetProp = [data[i]["colAvoShipData"][index]["shipMeetProp"] for index in range(len(data[i]["colAvoShipData"]))]
            shipDcpa = [data[i]["colAvoShipData"][index]["shipDcpa"] for index in range(len(data[i]["colAvoShipData"]))]
            shipTcpa = [data[i]["colAvoShipData"][index]["shipTcpa"] for index in range(len(data[i]["colAvoShipData"]))]
            shipBearing = [data[i]["colAvoShipData"][index]["shipBearing"] for index in range(len(data[i]["colAvoShipData"]))]
            shipDistance = [data[i]["colAvoShipData"][index]["shipDistance"] for index in range(len(data[i]["colAvoShipData"]))]
            ts_ships_mmsi = [data[i]["colAvoShipData"][index]["shipMmssiId"] for index in range(len(data[i]["colAvoShipData"]))]
            indices_to_keep = [j for j in range(len(ts_ships)) if shipDistance[j] < 0.2]
            os_shipBearing = [os_shipBearing[j] for j in indices_to_keep]
            ts_ships = [ts_ships[j] for j in indices_to_keep]
            shipMeetProp = [shipMeetProp[j] for j in indices_to_keep]
            shipDcpa = [shipDcpa[j] for j in indices_to_keep]
            shipTcpa = [shipTcpa[j] for j in indices_to_keep]
            shipDistance = [shipDistance[j] for j in indices_to_keep]
            ts_ships_mmsi = [ts_ships_mmsi[j] for j in indices_to_keep]
            # shipBearing = [shipBearing[j] for j in indices_to_keep]
            x_os, y_os, sog_os, cog_os = os_ship
            invariant_waypoint = coordinate_points[-1]
            rx, ry = zip(*coordinate_points)
            rx = np.array(list(rx))
            ry = np.array(list(ry))
            m = 1852
            ts_num = len(ts_ships)
            # 记录本船历史数据
            history_trajectory_os.append((os_ship[0], os_ship[1]))
            trajectory_os_x = [element[0] / m for element in history_trajectory_os]
            trajectory_os_y = [element[1] / m for element in history_trajectory_os]
            # ==============================================================================================================
            # 绘图
            # 清空每个子图
            cmap = plt.get_cmap('viridis')  # 定义轨迹颜色
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
            axes[0, 0].scatter(invariant_waypoint[0] / m, invariant_waypoint[1] / m, s=20, marker='*', color='r',
                               label='Waypoint')
            axes[0, 0].plot(trajectory_os_x, trajectory_os_y, color="r", linestyle="-", label="Ship Trajectory")
            axes[0, 0].plot(rx / m, ry / m, color="r", linestyle="-", label="Planned Path", linewidth=1)
            # 绘制圆圈（1000米）示意
            circle_radius = 1000 / m
            circle = Circle((x_os / m, y_os / m), circle_radius, color='r', fill=False, linewidth=1, linestyle='--',
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

            x_fixed_position = 0  # 假设固定位置为1，所有柱子在这个 x 位置上
            offset = 0.5  # 设置柱子之间的间隔
            for i in range(len(shipDistance)):
                color = cmap(i / ts_num)
                axes[1, 0].bar(x_fixed_position + i * offset, shipDistance[i], color=color, width=0.2,
                               label=f"{ts_ships_mmsi[i]}")
                axes[1, 0].text(x_fixed_position + i * offset, shipDistance[i], f"{shipDistance[i]:.3f}", fontsize=9,
                                verticalalignment='bottom', horizontalalignment='center')
            alert_distance = 0.5  # 设置警戒线的值
            axes[1, 0].axhline(y=alert_distance, color='r', linestyle='--', linewidth=1.5, label='Alert Line')
            axes[1, 0].text(5, alert_distance, f'{alert_distance}', color='red', fontsize=10,
                            verticalalignment='bottom', horizontalalignment='right')

            for i in range(len(shipDcpa)):
                color = cmap(i / ts_num)
                axes[0, 1].bar(x_fixed_position + i * offset, shipDcpa[i], color=color, width=0.2,
                               label=f"{ts_ships_mmsi[i]}")
                axes[0, 1].text(x_fixed_position + i * offset, shipDcpa[i], f"{shipDcpa[i]:.3f}", fontsize=9,
                                verticalalignment='bottom', horizontalalignment='center')
            alert_dcpa = 0.5  # 设置警戒线的值
            axes[0, 1].axhline(y=alert_dcpa, color='r', linestyle='--', linewidth=1.5, label='Alert Line')
            axes[0, 1].text(5, alert_dcpa, f'{alert_dcpa}', color='red', fontsize=10,
                            verticalalignment='bottom', horizontalalignment='right')

            for i in range(len(shipTcpa)):
                color = cmap(i / ts_num)
                axes[1, 1].bar(x_fixed_position + i * offset, shipTcpa[i], color=color, width=0.2,
                               label=f"{ts_ships_mmsi[i]}")
                axes[1, 1].text(x_fixed_position + i * offset, shipTcpa[i], f"{shipTcpa[i]:.3f}", fontsize=9,
                                verticalalignment='bottom', horizontalalignment='center')
            alert_tcpa = 10  # 设置警戒线的值
            axes[1, 1].axhline(y=alert_tcpa, color='r', linestyle='--', linewidth=1.5, label='Alert Line')
            axes[1, 1].text(5, alert_tcpa, f'{alert_tcpa}', color='red', fontsize=10,
                            verticalalignment='bottom', horizontalalignment='right')
            # 更新坐标轴范围

            # def update_axes():
            #     for i in [1, 3, 4]:  # 1, 2, 3对应第二、第三、第四个子图
            #         ax = axes.flatten()[i]
            #         x_data = ax.get_lines()[0].get_xdata()  # 获取 x 数据
            #         y_data = np.concatenate([line.get_ydata() for line in ax.get_lines()])  # 获取所有 y 数据
            #         ax.set_xlim(0, len(x_data))  # 根据 x 数据更新 xlim
            #         ax.set_ylim(y_data.min() - 1, y_data.max() + 1)  # 根据 y 数据更新 ylim
            #
            #
            # update_axes()  # 更新坐标轴范围
            # # 更新图例
            # axes[0, 0].legend()

            axes[0, 1].set_xlabel('t [s]')
            axes[0, 1].set_ylabel('DCPA [kn]')
            axes[0, 1].set_title('DCPA to risk_ship')
            axes[0, 1].set_xlim(-5, 5)
            axes[0, 1].set_ylim(0, 6)
            axes[0, 1].grid()

            axes[1, 0].set_xlabel('t [s]')
            axes[1, 0].set_ylabel('Distance [kn]')
            axes[1, 0].set_title('Distance to risk_ship')
            axes[1, 0].set_xlim(-5, 5)
            axes[1, 0].set_ylim(0, 6)
            axes[1, 0].grid()

            axes[1, 1].set_xlabel('t [s]')
            axes[1, 1].set_ylabel('TCPA [min]')
            axes[1, 1].set_title('TCPA to risk_ship')
            axes[1, 1].set_xlim(-5, 5)
            axes[1, 1].set_ylim(0, 20)
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

            # axes[0, 1].legend(loc='upper left')
            # axes[1, 0].legend(loc='upper left')
            # axes[1, 1].legend(loc='upper left')
            # axes[0, 2].legend(loc='upper left')
            # axes[1, 2].legend(loc='upper left')

            plt.tight_layout()
            plt.pause(0.1)  # 暂停一段时间以便观察

except FileNotFoundError:
    print(f"文件未找到：{json_file_path}")
except json.JSONDecodeError:
    print(f"文件格式错误，无法解析为JSON：{json_file_path}")
except Exception as e:
    print(f"读取文件时发生错误：{e}")
