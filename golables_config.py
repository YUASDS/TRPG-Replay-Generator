import re
import sys
import os
import pandas as pd
from exception import ParserError
from loguru import logger

system_terminated = print


# 正则表达式定义
class RE:
    RE_dialogue = re.compile(
        r"^\[([\ \w\.\;\(\)\,]+)\](<[\w\=\d]+>)?:(.+?)(<[\w\=\d]+>)?({.+})?$"
    )
    RE_background = re.compile(r"^<background>(<[\w\=]+>)?:(.+)$")
    RE_setting = re.compile(r"^<set:([\w\_]+)>:(.+)$")
    RE_characor = re.compile(r"([\w\ ]+)(\(\d*\))?(\.\w+)?")
    RE_modify = re.compile(r"<(\w+)(=\d+)?>")
    RE_sound = re.compile(r"({.+?})")
    RE_asterisk = re.compile(
        r"(\{([^\{\}]*?[,;])?\*([\w\.\,，]*)?\})"
    )  # v 1.7.3 修改匹配模式以匹配任何可能的字符（除了花括号）
    RE_hitpoint = re.compile(
        r"<hitpoint>:\((.+?),(\d+),(\d+),(\d+)\)"
    )  # a 1.6.5 血条预设动画
    RE_dice = re.compile(r"\((.+?),(\d+),([\d]+|NA),(\d+)\)")  # a 1.7.5 骰子预设动画，老虎机
    # RE_asterisk = re.compile('\{\w+[;,]\*(\d+\.?\d*)\}') # 这种格式对于{path;*time的}的格式无效！
    # RE_asterisk = re.compile('(\{([\w\.\\\/\'\":]*?[,;])?\*([\w\.\,，]*)?\})') # a 1.4.3 修改了星标的正则（和ss一致）,这种对于有复杂字符的路径无效！


class args:
    MediaObjDefine: str = (
        r"C:\Users\Administrator\Desktop\1\TRPG-Replay-Generator\toy\MediaObject.txt"
    )
    CharacterTable: str = (
        r"C:\Users\Administrator\Desktop\1\TRPG-Replay-Generator\toy\CharactorTable.csv"
    )
    LogFile: str = (
        r"C:\Users\Administrator\Desktop\1\TRPG-Replay-Generator\toy\LogFile.txt"
    )
    OutputPath: str = r"C:\Users\Administrator\Desktop\1\TRPG-Replay-Generator\toy"
    Width = 1920
    Height = 1080
    FramePerSecond = 30
    Zorder = "BG3,BG2,BG1,Am3,Am2,Am1,Bb"
    AccessKey = "Your_AccessKey"
    AccessKeySecret = "Your_AccessKey_Secret"
    Appkey = "Your_Appkey"
    Quality = 24
    ExportXML = False
    ExportVideo = False
    SynthesisAnyway = False
    FixScreenZoom = False


# 绝对的全局变量

python3 = sys.executable.replace(r"\\", "/")  # 获取python解释器的路径

cmap = {
    "black": (0, 0, 0, 255),
    "white": (255, 255, 255, 255),
    "greenscreen": (0, 177, 64, 255),
}
# render_arg = ['BG1','BG1_a','BG2','BG2_a','BG3','BG3_a','Am1','Am1_a','Am2','Am2_a','Am3','Am3_a','Bb','Bb_main','Bb_header','Bb_a']
# render_arg = ['BG1','BG1_a','BG2','BG2_a','BG3','BG3_a','Am1','Am1_a','Am2','Am2_a','Am3','Am3_a','Bb','Bb_main','Bb_header','Bb_a','BGM','Voice','SE']
render_arg = [
    "BG1",
    "BG1_a",
    "BG1_p",
    "BG2",
    "BG2_a",
    "BG2_p",
    "BG3",
    "BG3_a",
    "BG3_p",
    "Am1",
    "Am1_t",
    "Am1_a",
    "Am1_p",
    "Am2",
    "Am2_t",
    "Am2_a",
    "Am2_p",
    "Am3",
    "Am3_t",
    "Am3_a",
    "Am3_p",
    "Bb",
    "Bb_main",
    "Bb_header",
    "Bb_a",
    "Bb_p",
    "BGM",
    "Voice",
    "SE",
]
# 1.6.3 Am的更新，再新增一列，动画的帧！
# 被占用的变量名 # 1.7.7
occupied_variable_name = (
    open("./media/occupied_variable_name.list", "r", encoding="utf8").read().split("\n")
)

# 可以<set:keyword>动态调整的全局变量


class GlobalVariable:
    am_method_default = "<replace=0>"  # 默认切换效果（立绘）
    am_dur_default = 10  # 默认切换效果持续时间（立绘）

    bb_method_default = "<replace=0>"  # 默认切换效果（文本框）
    bb_dur_default = 10  # 默认切换效果持续时间（文本框）

    bg_method_default = "<replace=0>"  # 默认切换效果（背景）
    bg_dur_default = 10  # 默认切换效果持续时间（背景）

    tx_method_default = "<all=0>"  # 默认文本展示方式
    tx_dur_default = 5  # 默认单字展示时间参数

    speech_speed = 220  # 语速，单位word per minute
    # formula = linear  # 默认的曲线函数
    asterisk_pause = 20  # 星标音频的句间间隔 a1.4.3，单位是帧，通过处理delay


media_obj = args.MediaObjDefine  # 媒体对象定义文件的路径
char_tab = args.CharacterTable  # 角色和媒体对象的对应关系文件的路径
stdin_log = args.LogFile  # log路径
output_path = args.OutputPath  # 保存的时间轴，断点文件的目录

screen_size = (args.Width, args.Height)  # 显示的分辨率
frame_rate = args.FramePerSecond  # 帧率 单位fps
zorder = args.Zorder.split(",")  # 渲染图层顺序

AKID = args.AccessKey
AKKEY = args.AccessKeySecret
APPKEY = args.Appkey

crf = args.Quality  # 导出视频的质量值

exportXML = args.ExportXML  # 导出为XML
exportVideo = args.ExportVideo  # 导出为视频
synthfirst = args.SynthesisAnyway  # 是否先行执行语音合成
fixscreen = args.FixScreenZoom  # 是否修复窗体缩放


# 载入od文件
print("[replay generator]: Loading media definition file.")
with open(media_obj, "r", encoding="utf-8") as f:
    object_define_text = f.read().split("\n")

object_define_text = open(media_obj, "r", encoding="utf-8").read().split("\n")
if object_define_text[0][0] == "\ufeff":  # 139 debug
    print(
        "->[33m[warning]:->[0m",
        "UTF8 BOM recognized in MediaDef, it will be drop from the begin of file!",
    )
    object_define_text[0] = object_define_text[0][1:]

# 载入ct文件
print("[replay generator]: Loading charactor table.")
try:
    if char_tab.split(".")[-1] in ["xlsx", "xls"]:
        charactor_table = pd.read_excel(char_tab, dtype=str)  # 支持excel格式的角色配置表
    else:
        charactor_table = pd.read_csv(char_tab, sep="\t", dtype=str)
    charactor_table.index = charactor_table["Name"] + "." + charactor_table["Subtype"]
    if ("Animation" not in charactor_table.columns) | (
        "Bubble" not in charactor_table.columns
    ):  # 139debug
        raise SyntaxError("missing necessary columns.")
except Exception as E:
    logger.exception(E)


# 载入log文件 parser()
print("[replay generator]: Parsing Log file.")
try:
    stdin_text = open(stdin_log, "r", encoding="utf8").read().split("\n")
except UnicodeDecodeError as E:
    logger.exception(E)

if stdin_text[0][0] == "\ufeff":  # 139 debug
    print(
        "->[33m[warning]:->[0m",
        "UTF8 BOM recognized in Logfile, it will be drop from the begin of file!",
    )
    stdin_text[0] = stdin_text[0][1:]

# render_timeline, break_point, bulitin_media = "", "", ""


def parsersr(stdin_text: list[str]):
    from func import parser

    try:
        global render_timeline, break_point, bulitin_media
        render_timeline, break_point, bulitin_media = parser(
            stdin_text,
            render_arg,
            charactor_table,
        )
        # print(1, render_timeline)
        # print(2, break_point, bulitin_media)
        # print(3, bulitin_media)
        return render_timeline, break_point, bulitin_media
    except ParserError as E:
        logger.exception(E)
        print(E)
        print("Error")


try:
    for path in [stdin_log, media_obj, char_tab]:
        if path is None:
            raise OSError(
                "->[31m[ArgumentError]:->[0m Missing principal input argument!"
            )
        if not os.path.isfile(path):
            raise OSError("->[31m[ArgumentError]:->[0m Cannot find file " + path)

    if output_path is None:
        if (synthfirst) | (exportXML) | (exportVideo):
            raise OSError(
                "->[31m[ArgumentError]:->[0m Some flags requires output path, but no output path is specified!"
            )
    elif not os.path.isdir(output_path):
        raise OSError(
            "->[31m[ArgumentError]:->[0m Cannot find directory " + output_path
        )
    else:
        output_path = output_path.replace("\\", "/")

    # FPS
    if frame_rate <= 0:
        raise ValueError(
            "->[31m[ArgumentError]:->[0m Invalid frame rate:" + str(frame_rate)
        )
    elif frame_rate > 30:
        print(
            "->[33m[warning]:->[0m",
            "FPS is set to "
            + str(frame_rate)
            + ", which may cause lag in the display!",
        )

    if (screen_size[0] <= 0) | (screen_size[1] <= 0):
        raise ValueError(
            "->[31m[ArgumentError]:->[0m Invalid resolution:" + str(screen_size)
        )
    if screen_size[0] * screen_size[1] > 3e6:
        print(
            "->[33m[warning]:->[0m",
            "Resolution is set to more than 3M, which may cause lag in the display!",
        )
except Exception as E:
    print(E)
    system_terminated("Error")
