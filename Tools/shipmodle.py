import matplotlib.patches as patches
import matplotlib.path as mpath
import matplotlib.transforms as transforms


def ship_model(x, y, sog, cog, scale=0.01):  # 添加缩放因子
    # 自定义船形路径
    Path = mpath.Path
    ship_path = Path(
        [[-1 * scale, 0], [-1 * scale, 3 * scale], [0, 6 * scale], [1 * scale, 3 * scale], [1 * scale, 0], [0, 0]],
        [Path.MOVETO, Path.LINETO, Path.CURVE3, Path.CURVE3, Path.LINETO, Path.CLOSEPOLY]
    )

    # 将路径旋转并位移到指定位置
    transform = transforms.Affine2D().rotate_deg(-cog).translate(x, y)
    transformed_path = ship_path.transformed(transform)

    return transformed_path

#
# if __name__ == "__main__":
#     ships = [
#         [3, 5, 0, 0],  # 第一条船的坐标和航向
#         [4, 6, 0, 45],  # 第二条船
#         [0, 0, 0, 190]
#     ]
#     fig, ax = plt.subplots()
#     ax.set_xlim(0, 10)
#     ax.set_ylim(0, 10)
#     ax.set_xlabel('x')
#     ax.set_ylabel('y')
#     ax.grid(True, color='black', linestyle='--', linewidth=0.3, alpha=0.3)
#
#     # 绘制自定义船舶图标
#     for x, y, cog, sog in ships:
#         ship_shape = ship_model(x, y, cog, sog, scale=0.1)  # 设置缩放因子为0.1
#         patch = patches.PathPatch(ship_shape, facecolor='none', edgecolor='black', lw=2)
#         ax.add_patch(patch)
#
#     plt.show()

