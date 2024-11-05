# -------------------------------------------------------------------------------------
# import 此demo需要使用的包
# --------------------
import api_test_target
import time
import matplotlib.pyplot as plt

# -------------------------------------------------------------------------------------
# 初始化变量
# --------------------
# 初始化通信地址和端口
URL = 'http://127.0.0.1:6669'

# --------------------
# 单独定义本测试对象所需要数据变量
# --------------------

Target_Heading = 0.0
Target_Lat = 0.0
Target_Lon = 0.0
Target_Length = 0.0
Target_Width = 0.0
Target_Speed = 0.0
GPS_Target_current = [0.0, 0.0]

Tug_Heading = 0.0
Tug_Lat = 0.0
Tug_Lon = 0.0
Tug_Length = 0.0
Tug_Width = 0.0
GPS_Tug_current = [0.0, 0.0]
Tug_Yawrate = 0.0
Tug_Speed = 0.0

Target_x = 0.0
Target_y = 0.0
Tug_x = 0.0
Tug_y = 0.0
Virtual_tug_x = 0.0
Virtual_tug_y = 0.0
t = time.ctime()

# 坐标列表写出及开启画图窗口
List_e = []                    # 定义一个 东向位移 的空列表用来接收动态的数据
List_n = []                    # 定义一个 北向位移 的空列表用来接收动态的数据
plt.ion()                      # 开启一个hold on的窗口


def listen_channel_func():
    # ================================
    # 与目标端口建立通信
    # ================================
    try:
        while True:
            OS1_date = api_test_target.HttpAPI(URL, 'whut1001')
            Target_data = OS1_date.get_osdata()
            OS2_date = api_test_target.HttpAPI(URL, 'whut1002')
            Tug_data = OS2_date.get_osdata()

            Target_Heading = float(Target_data["data"]["hdg"])
            Target_Lat = float(Target_data["data"]["lat"])
            Target_Lon = float(Target_data["data"]["lon"])
            Target_Length = float(Target_data["data"]["length"])
            Target_Width = float(Target_data["data"]["width"])
            Target_Speed = float(Target_data["data"]["sog"])
            GPS_Target_current = [Target_Lat, Target_Lon]

            Tug_Heading = float(Tug_data["data"]["hdg"])
            Tug_Lat = float(Tug_data["data"]["lat"])
            Tug_Lon = float(Tug_data["data"]["lon"])
            Tug_Length = float(Tug_data["data"]["length"])
            Tug_Width = float(Tug_data["data"]["width"])
            Tug_Yawrate = float(Tug_data["data"]["rot"])
            Tug_Speed = float(Tug_data["data"]["sog"])
            GPS_Tug_current = [Tug_Lat, Tug_Lon]


            # ================================
            # 规划算法带入
            # ================================






            # ================================
            # 控制算法带入
            # ================================








            # ================================
            # 发送控制指令
            # ================================

            # 控制目标大船指令    （根据测试需求选择是否使用）
            # 函数参数为：舵模式、自动舵舵角（不适用自动舵默认0）、尾舵舵角（左负右正）、左车钟（百分比）、右车钟（单桨单舵左右车钟一致）、左侧推车钟、右侧推车钟（没有侧推默认值为0）
            OS1_date.post_ctrl_os_general('fu', 0, 0, 50, 50, 0, 0)


            # 控制拖轮指令
            # 函数参数为：舵模式、自动舵舵角（不适用自动舵默认0）、左推进器车钟（百分比）、左推进器角度（左负右正）、右推进器车钟、右推进器角度、左侧推车钟、右侧推车钟（没有侧推默认值为0）
            OS2_date.post_ctrl_os_azm('fu', 0, 20, 0, 20, 0, 0, 0)


            time.sleep(1)

    except:
        print("建立监听失败，退出监听remote数据")

    finally:
        print("程序结束！")


if __name__ == "__main__":
    start = listen_channel_func()
