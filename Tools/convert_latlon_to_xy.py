import pyproj


def ship_latlon_to_xy(ship):  # 单位 ：m
    """
    经纬度转换
    :param ship: 包含经纬度和其他信息的元组 (lat, lon, sog, cog)
    :return: 转换后的坐标和其他信息
    """
    # 定义 EPSG 坐标系
    src_epsg = 'EPSG:4326'  # WGS84 经纬度坐标系
    dst_epsg = 'EPSG:3857'  # Web Mercator

    lon, lat, sog, cog = ship

    # 检查纬度和经度的有效性
    if not (-90 <= lat <= 90):
        raise ValueError(f"纬度必须在 -90 到 90 之间, 输入值: {lat}")
    if not (-180 <= lon <= 180):
        raise ValueError(f"经度必须在 -180 到 180 之间, 输入值: {lon}")

        # 创建转换器
    proj = pyproj.Transformer.from_crs(src_epsg, dst_epsg, always_xy=True)

    # 转换经纬度
    try:
        x, y = proj.transform(lon, lat)  # 经度，纬度的顺序
    except Exception as e:
        raise RuntimeError(f"坐标转换失败: {e}")

    # 返回转换后的结果
    return list((x, y, sog, cog))


def ship_xy_to_latlon(x_list, y_list):  # 单位：m
    """
    x, y 坐标列表转换为经纬度列表
    :param x_list: 包含 x 坐标的列表
    :param y_list: 包含 y 坐标的列表
    :return: 转换后的经纬度列表
    """
    # 定义 EPSG 坐标系
    src_epsg = 'EPSG:3857'  # Web Mercator
    dst_epsg = 'EPSG:4326'  # WGS84 经纬度坐标系

    # 创建转换器
    proj = pyproj.Transformer.from_crs(src_epsg, dst_epsg, always_xy=True)

    # 经纬度结果列表
    latlon_list = []

    # 确保 x 和 y 列表长度一致
    if len(x_list) != len(y_list):
        raise ValueError("x_list 和 y_list 的长度必须相同。")

    # 转换每对 x, y 坐标
    for x, y in zip(x_list, y_list):
        try:
            lon, lat = proj.transform(x, y)  # x, y 的顺序
            latlon_list.append([lon, lat])  # 将结果添加到列表中
        except Exception as e:
            raise RuntimeError(f"坐标转换失败: {e}")

    # 返回转换后的经纬度列表
    return latlon_list


# lat = 31
# lon = 121
# sog = 10
# cog = 0
# ship = [lon, lat, sog, cog]
# x0, y0, sog, cog = ship_latlon_to_xy(ship)
# print(x0, y0)
# x = [x0]
# y = [y0]
# latlon_list = ship_xy_to_latlon(x, y)
# print(latlon_list)
