import os
import re
from typing import Union

from loguru import logger
import pandas as pd
import numpy as np
import pygame
import pygame.freetype

from golables_config import (
    args,
    RE,
    GlobalVariable,
    # object_define_text,
    occupied_variable_name,
)  
from exception import ParserError
from media_class import (
    Background,
    BuiltInAnimation,
    Text,
    StrokeText,
    Bubble,
    Animation,
    BGM,
    Audio,
)

am_method_default = GlobalVariable.am_method_default  # 默认切换效果（立绘）
am_dur_default = GlobalVariable.am_dur_default  # 默认切换效果持续时间（立绘）

bb_method_default = GlobalVariable.bb_method_default  # 默认切换效果（文本框）
bb_dur_default = GlobalVariable.bb_dur_default  # 默认切换效果持续时间（文本框）

bg_method_default = GlobalVariable.bg_method_default  # 默认切换效果（背景）
bg_dur_default = GlobalVariable.bg_dur_default  # 默认切换效果持续时间（背景）

tx_method_default = GlobalVariable.tx_method_default  # 默认文本展示方式
tx_dur_default = GlobalVariable.bg_dur_default  # 默认单字展示时间参数

speech_speed = GlobalVariable.speech_speed  # 语速，单位word per minute

asterisk_pause = GlobalVariable.asterisk_pause  # 星标音频的句间间隔 a1.4.3，单位是帧，通过处理delay

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


# 数学函数定义 formula

media_list: dict[
    str,
    Union[
        Text,
        str,
        BuiltInAnimation,
        Text,
        StrokeText,
        Bubble,
        Animation,
        BGM,
        Audio,
        Background,
    ],
] = {}  # 媒体对象字典


def instantiate_object(object_define_text: list[str]):  # 对象实例化
    for text in object_define_text:
        if text == "" or text[0] == "#":
            continue
        try:
            obj_name = text.split("=")[0]
            obj_name = obj_name.replace(" ", "")
            if obj_name in occupied_variable_name:
                raise SyntaxError("Obj name occupied")
            elif (len(re.findall(r"\w+", obj_name)) == 0) | (obj_name[0].isdigit()):
                raise SyntaxError("Invalid Obj name")
            # media_list[obj_name] = None

            exec(text, None, media_list)  # 对象实例化
            logger.debug(text)
        except Exception as E:
            logger.exception(E)
    # logger.debug(f"Media list: {media_list}")
    for media in media_list:
        try:
            media_list[media].convert()  # type: ignore
        except Exception as E:
            logger.exception(E)
    media_list["black"] = Background("black")
    media_list["white"] = Background("white")
    return media_list


def normalized(X):
    return (X - X.min()) / (X.max() - X.min()) if len(X) >= 2 else X / X


def linear(begin, end, dur):
    return np.linspace(begin, end, int(dur))


formula = linear  # 默认的曲线函数


def quadratic(begin, end, dur):
    return (np.linspace(0, 1, int(dur)) ** 2) * (end - begin) + begin


def quadraticR(begin, end, dur):
    return (1 - np.linspace(1, 0, int(dur)) ** 2) * (end - begin) + begin


def sigmoid(begin, end, dur, K=5):
    return (
        normalized(1 / (1 + np.exp(np.linspace(K, -K, int(dur))))) * (end - begin)
        + begin
    )


def right(begin, end, dur, K=4):
    return (
        normalized(1 / (1 + np.exp((quadratic(K, -K, int(dur)))))) * (end - begin)
        + begin
    )


def left(begin, end, dur, K=4):
    return (
        normalized(1 / (1 + np.exp((quadraticR(K, -K, int(dur)))))) * (end - begin)
        + begin
    )


def sincurve(begin, end, dur):  # alpha 1.8.4
    return (
        normalized(np.sin(np.linspace(-np.pi / 2, np.pi / 2, dur))) * (end - begin)
        + begin
    )


formula_available = {
    "linear": linear,
    "quadratic": quadratic,
    "quadraticR": quadraticR,
    "sigmoid": sigmoid,
    "right": right,
    "left": left,
    "sincurve": sincurve,
}


# 其他函数定义

# 解析对话行 []


def get_dialogue_arg(text: str):
    cr, cre, ts, tse, se = RE.RE_dialogue.findall(text)[0]
    this_duration = int(len(ts) / (speech_speed / 60 / frame_rate))
    this_charactor: list[list[str]] = RE.RE_characor.findall(cr)
    # 切换参数
    if cre == "":  # 没有指定 都走默认值
        am_method, am_dur = RE.RE_modify.findall(am_method_default)[0]
        bb_method, bb_dur = RE.RE_modify.findall(bb_method_default)[0]
    else:  # 有指定，变得相同
        am_method, am_dur = RE.RE_modify.findall(cre)[0]
        bb_method, bb_dur = am_method, am_dur
    am_dur = am_dur_default if am_dur == "" else int(am_dur.replace("=", ""))
    bb_dur = bb_dur_default if bb_dur == "" else int(bb_dur.replace("=", ""))
    # 文本显示参数
    if tse == "":
        tse = tx_method_default
    text_method, text_dur = RE.RE_modify.findall(tse)[0]  # <black=\d+>
    text_dur = tx_dur_default if text_dur == "" else int(text_dur.replace("=", ""))
    # 语音和音效参数
    this_sound = [] if se == "" else RE.RE_sound.findall(se)
    return (
        this_charactor,
        this_duration,
        am_method,
        am_dur,
        bb_method,
        bb_dur,
        ts,
        text_method,
        text_dur,
        this_sound,
    )


def get_background_arg(text: str) -> tuple[str, str, int]:
    bge, bgc = RE.RE_background.findall(text)[0]
    if bge == "":
        bge = bg_method_default
    method, method_dur = RE.RE_modify.findall(bge)[0]
    if method_dur == "":
        method_dur = bg_dur_default
    else:
        method_dur = int(method_dur.replace("=", ""))
    return (bgc, method, method_dur)


# 解释设置行 <set:>
def get_seting_arg(text: str) -> tuple[str, str]:
    target, args = RE.RE_setting.findall(text)[0]
    return (target, args)


# 截断字符串
def cut_str(str_, len_):
    return str_[: int(len_)]


UF_cut_str = np.frompyfunc(cut_str, 2, 1)


# 设定合理透明度范围
def alpha_range(x):
    return 100 if x > 100 else max(x, 0)


# UF : 将2个向量组合成"x,y"的形式
concat_xy = np.frompyfunc(lambda x, y: "%d" % x + "," + "%d" % y, 2, 1)


# 把拼接起来的修正位置分隔开
def split_xy(concated):
    x, y = concated.split(",")
    return int(x), int(y)


method_args = {
    "alpha": "replace",
    "motion": "static",
    "direction": "up",
    "scale": "major",
    "cut": "both",
}  # default
scale_dic = {"major": 0.3, "minor": 0.12, "entire": 1.0}
direction_dic = {"up": 0, "down": 180, "left": 90, "right": 270}  # up = 0 剩下的逆时针


def am_methods(method_name: str, method_dur, this_duration, i):
    def dynamic(scale, duration, balance, cut, enable):  # 动态(尺度,持续,平衡,进出,启用)
        if not enable:
            return np.ones(duration) * scale * balance
        if cut == balance:
            return formula(0, scale, duration)
        else:
            return formula(scale, 0, duration)

    if method_dur == 0:
        return np.ones(this_duration), "NA"
    Height = screen_size[1]
    Width = screen_size[0]
    method_keys = method_name.split("_")
    # parse method name
    for key in method_keys:
        if key in ["black", "replace", "delay"]:
            method_args["alpha"] = key
        elif key in ["pass", "leap", "static", "circular"]:
            method_args["motion"] = key
        elif key in ["up", "down", "left", "right"]:
            method_args["direction"] = key
        elif key in ["major", "minor", "entire"]:
            method_args["scale"] = key
        elif key in ["in", "out", "both"]:
            method_args["cut"] = key
        elif "DG" == key[0:2]:
            try:
                method_args["direction"] = float(key[2:])
            except Exception:
                raise ParserError(
                    '->[31m[ParserError]:->[0m Unrecognized switch method: "'
                    + method_name
                    + '" appeared in dialogue line '
                    + str(i + 1)
                    + "."
                )
        else:
            try:
                method_args["scale"] = int(key)
            except Exception:
                raise ParserError(
                    '->[31m[ParserError]:->[0m Unrecognized switch method: "'
                    + method_name
                    + '" appeared in dialogue line '
                    + str(i + 1)
                    + "."
                )
    # 切入，切出，或者双端
    cutin, cutout = {"in": (1, 0), "out": (0, 1), "both": (1, 1)}[method_args["cut"]]
    # alpha
    if method_args["alpha"] == "replace":  # --
        alpha_timeline = np.hstack(np.ones(this_duration))  # replace的延后功能撤销！
    elif method_args["alpha"] == "delay":  # _-
        alpha_timeline = np.hstack(
            [np.zeros(method_dur), np.ones(this_duration - method_dur)]
        )  # 延后功能
    else:  # method_args['alpha'] == 'black':#>1<
        alpha_timeline = np.hstack(
            [
                dynamic(1, method_dur, 1, 1, cutin),
                np.ones(this_duration - 2 * method_dur),
                dynamic(1, method_dur, 1, 0, cutout),
            ]
        )
    # static 的提前终止
    if method_args["motion"] == "static":
        pos_timeline = "NA"
        return alpha_timeline, pos_timeline

    # direction
    try:
        theta = np.deg2rad(direction_dic[method_args["direction"]])
    except Exception:  # 设定为角度
        theta = np.deg2rad(method_args["direction"])
    # scale
    if method_args["scale"] in [
        "major",
        "minor",
        "entire",
    ]:  # 上下绑定屏幕高度，左右绑定屏幕宽度*scale_dic[method_args['scale']]
        method_args["scale"] = (
            (np.cos(theta) * Height) ** 2 + (np.sin(theta) * Width) ** 2
        ) ** (1 / 2) * scale_dic[method_args["scale"]]
    else:  # 指定了scale
        pass
    # motion
    if method_args["motion"] == "pass":  # >0>
        D1 = np.hstack(
            [
                dynamic(method_args["scale"] * np.sin(theta), method_dur, 0, 1, cutin),
                np.zeros(this_duration - 2 * method_dur),
                dynamic(
                    -method_args["scale"] * np.sin(theta), method_dur, 0, 0, cutout
                ),
            ]
        )
        D2 = np.hstack(
            [
                dynamic(method_args["scale"] * np.cos(theta), method_dur, 0, 1, cutin),
                np.zeros(this_duration - 2 * method_dur),
                dynamic(
                    -method_args["scale"] * np.cos(theta), method_dur, 0, 0, cutout
                ),
            ]
        )
    elif method_args["motion"] == "leap":  # >0<
        D1 = np.hstack(
            [
                dynamic(method_args["scale"] * np.sin(theta), method_dur, 0, 1, cutin),
                np.zeros(this_duration - 2 * method_dur),
                dynamic(method_args["scale"] * np.sin(theta), method_dur, 0, 0, cutout),
            ]
        )
        D2 = np.hstack(
            [
                dynamic(method_args["scale"] * np.cos(theta), method_dur, 0, 1, cutin),
                np.zeros(this_duration - 2 * method_dur),
                dynamic(method_args["scale"] * np.cos(theta), method_dur, 0, 0, cutout),
            ]
        )
    # 实验性质的功能，想必不可能真的有人用这么鬼畜的效果吧
    elif method_args["motion"] == "circular":
        theta_timeline = (
            np.repeat(
                formula(0 - theta, 2 * np.pi - theta, method_dur),
                np.ceil(this_duration / method_dur).astype(int),
            )
            .reshape(method_dur, np.ceil(this_duration / method_dur).astype(int))
            .transpose()
            .ravel()
        )[0:this_duration]
        D1 = np.sin(theta_timeline) * method_args["scale"]
        D2 = -np.cos(theta_timeline) * method_args["scale"]
    else:
        pos_timeline = "NA"
        return alpha_timeline, pos_timeline
    pos_timeline = concat_xy(D1, D2)
    return alpha_timeline, pos_timeline


# 解析函数
class Parser:
    formula: str
    break_point = []
    # 视频+音轨 时间轴
    render_timeline = []
    BGM_queue = []
    this_background = "black"
    # 内建的媒体，主要指BIA
    bulitin_media = {}

    def __init__(
        self,
        stdin_text: list[str],
        render_arg: list[str],
        charactor_table: pd.DataFrame,
    ):
        self.stdin_text = stdin_text
        self.render_arg = render_arg
        self.charactor_table = charactor_table
        break_point: pd.Series[int] = pd.Series(np.arange(len(stdin_text)))
        break_point[0] = 0

    def log(self, text: str, i: int):
        try:
            (
                this_charactor,
                this_duration,
                am_method,
                am_dur,
                bb_method,
                bb_dur,
                ts,
                text_method,
                text_dur,
                this_sound,
            ) = get_dialogue_arg(text)
            # a 1.3 从音频中加载持续时长 {SE1;*78} 注意，这里只需要载入星标时间，检查异常不在这里做：
            asterisk_timeset = RE.RE_asterisk.findall("\t".join(this_sound))  # 在音频标志中读取
            if len(asterisk_timeset) == 0:  # 没检测到星标
                pass
            elif len(asterisk_timeset) == 1:  # 检查到一个星标
                try:
                    asterisk_time = float(asterisk_timeset[0][-1])  # 取第二个，转化为浮点数
                    this_duration = asterisk_pause + np.ceil(
                        (asterisk_time) * frame_rate
                    ).astype(
                        int
                    )  # a1.4.3 添加了句间停顿
                except Exception:
                    print(
                        "->[33m[warning]:->[0m",
                        "Failed to load asterisk time in dialogue line "
                        + str(i + 1)
                        + ".",
                    )
            else:  # 检测到复数个星标
                raise ParserError(
                    "->[31m[ParserError]:->[0m Too much asterisk time labels are set in dialogue line "
                    + str(i + 1)
                    + "."
                )

            # 确保时长不短于切换特效时长
            if this_duration < (2 * max(am_dur, bb_dur) + 1):
                this_duration = 2 * max(am_dur, bb_dur) + 1

            # 建立本小节的timeline文件
            this_timeline = pd.DataFrame(
                index=range(0, this_duration), dtype=str, columns=self.render_arg
            )
            this_timeline["BG1"] = self.this_background
            this_timeline["BG1_a"] = 100
            # 载入切换效果
            alpha_timeline_A, pos_timeline_A = am_methods(
                am_method, am_dur, this_duration, i
            )
            alpha_timeline_B, pos_timeline_B = am_methods(
                bb_method, bb_dur, this_duration, i
            )
            # 各个角色：
            if len(this_charactor) > 3:
                raise ParserError(
                    "->[31m[ParserError]:->[0m Too much charactor is specified in dialogue line "
                    + str(i + 1)
                    + "."
                )
            # logger.debug(charactor_table)
            for k, charactor in enumerate(this_charactor[0:3]):
                name, alpha, subtype = charactor
                # logger.debug(charactor)
                # 处理空缺参数
                if subtype == "":
                    subtype = ".default"
                if alpha == "":
                    alpha = 100
                else:
                    alpha = int(alpha[1:-1])
                # 立绘的参数
                try:
                    this_am: pd.Series[str] = self.charactor_table.loc[name + subtype][
                        "Animation"
                    ]
                    this_timeline["Am" + str(k + 1)] = this_am
                except Exception as E:  # 在角色表里面找不到name，raise在这里！
                    raise ParserError(
                        "->[31m[ParserError]:->[0m Undefined Name "
                        + name
                        + subtype
                        + " in dialogue line "
                        + str(i + 1)
                        + ". due to:",
                        E,
                    ) from E

                # 动画的参数
                if (isinstance(this_am, float)) or (
                    this_am == "NA"
                ):  # this_am 可能为空的，需要先处理这种情况！
                    this_timeline[f"Am{k + 1}_t"] = 0

                else:
                    try:
                        # logger.debug(this_am, name, subtype)
                        this_timeline[f"Am{k + 1}_t"] = media_list[
                            this_am
                        ].get_tick(  # type: ignore
                            this_duration
                        )

                        # eval(
                        #     f"{this_am}.get_tick({this_duration})"
                        # )
                    except NameError as E:  # 指定的am没有定义！
                        # logger.debug(this_timeline)
                        raise ParserError(
                            "->[31m[ParserError]:->[0m",
                            E,
                            ", which is specified to",
                            name + subtype,
                            "as Animation!",
                        ) from E

                # 检查气泡文本的可用性 alpha 1.8.4
                if ('"' in name) | ("\\" in name) | ('"' in ts) | ("\\" in ts):
                    raise ParserError(
                        "->[31m[ParserError]:->[0m",
                        "Invalid symbol (double quote or backslash) appeared in speech text in dialogue line "
                        + str(i + 1)
                        + ".",
                    )
                # 气泡的参数
                if k == 0:
                    this_bb = self.charactor_table.loc[name + subtype]["Bubble"]
                    if (this_bb != this_bb) | (
                        this_bb == "NA"
                    ):  # 主要角色一定要有bubble！，次要的可用没有
                        raise ParserError(
                            "->[31m[ParserError]:->[0m",
                            "No bubble is specified to major charactor",
                            name + subtype,
                            "of dialogue line " + str(i + 1) + ".",
                        )
                    this_timeline["Bb"] = self.charactor_table.loc[name + subtype][
                        "Bubble"
                    ]  # 异常处理，未定义的名字
                    this_timeline["Bb_main"] = ts
                    this_timeline["Bb_header"] = name
                    this_timeline["Bb_a"] = alpha_timeline_B * 100
                    this_timeline["Bb_p"] = pos_timeline_B
                # 透明度参数
                if (k != 0) & (alpha == 100):  # 如果非第一角色，且没有指定透明度，则使用正常透明度60%
                    this_timeline["Am" + str(k + 1) + "_a"] = alpha_timeline_A * 60
                else:  # 否则，使用正常透明度
                    this_timeline["Am" + str(k + 1) + "_a"] = alpha_timeline_A * alpha
                # 位置时间轴信息
                this_timeline["Am" + str(k + 1) + "_p"] = pos_timeline_A

            # 针对文本内容的警告
            try:
                media_name = this_timeline["Bb"][0]
                media = media_list[media_name]
                this_line_limit: int = media.MainText.line_limit  # type: ignore
                # 获取行长，用来展示各类警告信息
            except NameError as E:  # 指定的bb没有定义！
                raise ParserError(
                    "->[31m[ParserError]:->[0m",
                    E,
                    ", which is specified to",
                    this_charactor[0:3],
                    "as Bubble!",
                ) from E

            if (len(ts) > this_line_limit * 4) | (len(ts.split("#")) > 4):  # 行数过多的警告
                print(
                    "->[33m[warning]:->[0m",
                    "More than 4 lines will be displayed in dialogue line "
                    + str(i + 1)
                    + ".",
                )
            if ((ts[0] == "^") | ("#" in ts)) & (
                np.frompyfunc(len, 1, 1)(ts.replace("^", "").split("#")).max()
                > this_line_limit
            ):  # 手动换行的字数超限的警告
                print(
                    "->[33m[warning]:->[0m",
                    "Manual break line length exceed the Bubble line_limit in dialogue line "
                    + str(i + 1)
                    + ".",
                )  # alpha1.6.3
            # 文字显示的参数
            if text_method == "all":
                if text_dur == 0:
                    pass
                else:
                    this_timeline.loc[0:text_dur, "Bb_main"] = ""  # 将前n帧的文本设置为空白
            elif text_method == "w2w":
                word_count_timeline = np.arange(0, this_duration, 1) // text_dur + 1
                this_timeline["Bb_main"] = UF_cut_str(
                    this_timeline["Bb_main"], word_count_timeline
                )
            elif text_method == "l2l":
                if (ts[0] == "^") | ("#" in ts):  # 如果是手动换行的列
                    word_count_timeline = get_l2l(
                        ts, text_dur, this_duration
                    )  # 不保证稳定呢！
                else:
                    line_limit = eval(
                        this_timeline["Bb"][1] + ".MainText.line_limit"
                    )  # 获取主文本对象的line_limit参数
                    word_count_timeline = (
                        np.arange(0, this_duration, 1) // (text_dur * line_limit) + 1
                    ) * line_limit
                this_timeline["Bb_main"] = UF_cut_str(
                    this_timeline["Bb_main"], word_count_timeline
                )
            else:
                raise ParserError(
                    '->[31m[ParserError]:->[0m Unrecognized text display method: "'
                    + text_method
                    + '" appeared in dialogue line '
                    + str(i + 1)
                    + "."
                )
            # 音频信息
            if self.BGM_queue != []:
                this_timeline.loc[0, "BGM"] = self.BGM_queue.pop()  # 从BGM_queue里取出来一个
            for sound in this_sound:  # this_sound = ['{SE_obj;30}','{SE_obj;30}']
                try:
                    se_obj, delay = sound[1:-1].split(";")  # sound = '{SE_obj;30}'
                except Exception:  # #sound = '{SE_obj}'
                    delay = "0"
                    se_obj = sound[1:-1]  # 去掉花括号
                if delay == "":
                    delay = 0
                elif "*" in delay:  # 如果是星标时间 delay 是asterisk_pause的一半
                    delay = int(asterisk_pause / 2)
                elif int(delay) >= this_duration:  # delay 不能比一个单元还长
                    delay = this_duration - 1
                else:
                    delay = int(delay)
                if "*" in se_obj:
                    raise ParserError(
                        "->[31m[ParserError]:->[0m Unprocessed asterisk time label appeared in dialogue line "
                        + str(i + 1)
                        + ". Add --SynthesisAnyway may help."
                    )
                if se_obj in media_list:  # 如果delay在媒体里已经定义，则视为SE
                    this_timeline.loc[0:delay, "SE"] = se_obj
                elif os.path.isfile(se_obj[1:-1]):  # 或者指向一个确定的文件，则视为语音
                    this_timeline.loc[0:delay, "Voice"] = se_obj
                elif se_obj in ["NA", ""]:  # 如果se_obj是空值或NA，则什么都不做 alpha1.8.5
                    pass
                else:
                    raise ParserError(
                        '->[31m[ParserError]:->[0m The sound effect "'
                        + se_obj
                        + '" specified in dialogue line '
                        + str(i + 1)
                        + " is not exist!"
                    )

            self.render_timeline.append(this_timeline)
            self.break_point[i + 1] = self.break_point[i] + this_duration

        except Exception as E:
            print(E)

    def background_render(self, text: str, i: int):
        render_arg = self.render_arg
        render_timeline = self.render_timeline
        break_point = self.break_point
        this_background = self.this_background
        try:
            bgc, method, method_dur = get_background_arg(text)
            if bgc in media_list:  # 检查是否是已定义的对象
                next_background = bgc
            else:
                raise ParserError(
                    '->[31m[ParserError]:->[0m The background "'
                    + bgc
                    + '" specified in background line '
                    + str(i + 1)
                    + " is not defined!"
                )
            if method == "replace":  # replace 改为立刻替换 并持续n秒
                this_timeline = pd.DataFrame(
                    index=range(0, method_dur), dtype=str, columns=render_arg
                )

                this_timeline["BG1"] = next_background
                this_timeline["BG1_a"] = 100
            elif method == "delay":  # delay 等价于原来的replace，延后n秒，然后替换
                this_timeline = pd.DataFrame(
                    index=range(0, method_dur), dtype=str, columns=render_arg
                )

                this_timeline["BG1"] = this_background
                this_timeline["BG1_a"] = 100
            elif method in [
                "cross",
                "black",
                "white",
                "push",
                "cover",
            ]:  # 交叉溶解，黑场，白场，推，覆盖
                this_timeline = pd.DataFrame(
                    index=range(0, method_dur), dtype=str, columns=render_arg
                )

                this_timeline["BG1"] = next_background
                this_timeline["BG2"] = this_background
                if method in ["black", "white"]:
                    this_timeline["BG3"] = method
                    this_timeline["BG1_a"] = formula(-100, 100, method_dur)
                    this_timeline["BG1_a"] = this_timeline["BG1_a"].map(alpha_range)
                    this_timeline["BG2_a"] = formula(100, -100, method_dur)
                    this_timeline["BG2_a"] = this_timeline["BG2_a"].map(alpha_range)
                    this_timeline["BG3_a"] = 100
                elif method == "cross":
                    this_timeline["BG1_a"] = formula(0, 100, method_dur)
                    this_timeline["BG2_a"] = 100
                elif method in ["push", "cover"]:
                    this_timeline["BG1_a"] = 100
                    this_timeline["BG2_a"] = 100
                    if method == "push":  # 新背景从右侧把旧背景推出去
                        this_timeline["BG1_p"] = concat_xy(
                            formula(screen_size[0], 0, method_dur),
                            np.zeros(method_dur),
                        )
                        this_timeline["BG2_p"] = concat_xy(
                            formula(0, -screen_size[0], method_dur),
                            np.zeros(method_dur),
                        )
                    else:  # cover 新背景从右侧进来叠在原图上面
                        this_timeline["BG1_p"] = concat_xy(
                            formula(screen_size[0], 0, method_dur),
                            np.zeros(method_dur),
                        )
                        this_timeline["BG2_p"] = "NA"
            else:
                raise ParserError(
                    '->[31m[ParserError]:->[0m Unrecognized switch method: "'
                    + method
                    + '" appeared in background line '
                    + str(i + 1)
                    + "."
                )
            self.this_background = next_background  # 正式切换背景
            render_timeline.append(this_timeline)
            break_point[i + 1] = break_point[i] + len(this_timeline.index)
        except Exception as E:
            print(E)
            raise ParserError(
                (
                    (
                        "->[31m[ParserError]:->[0m Parse exception occurred in background line "
                        + str(i + 1)
                    )
                    + "."
                )
            ) from E

    def set_method(self, text: str, i: int):
        set_config = [
            "speech_speed",
            "am_method_default",
            "am_dur_default",
            "bb_method_default",
            "bb_dur_default",
            "bg_method_default",
            "bg_dur_default",
            "tx_method_default",
            "tx_dur_default",
            "asterisk_pause",
        ]
        BGM_queue = self.BGM_queue
        try:
            target, args = get_seting_arg(text)
            if target in set_config:
                if args.isdigit():
                    args_new = int(args)
                    if args_new < 0:
                        print(
                            "->[33m[warning]:->[0m",
                            "Setting",
                            target,
                            "to invalid value",
                            args_new,
                            ",the argument will not changed.",
                        )
                        args_new = eval(target)  # 保持原数值不变
                    # print("global {0} ; {0} = {1}".format(target,str(test)))
                    exec(
                        f"{target} = {args_new}",
                        None,
                        media_list,
                    )
                else:  # 否则当作文本型
                    # print("global {0} ; {0} = {1}".format(target,'\"'+args+'\"'))
                    exec(
                        f"{target} = '{args}'",
                        None,
                        media_list,
                    )
            elif target == "BGM":
                if args in media_list:
                    BGM_queue.append(args)
                elif os.path.isfile(args[1:-1]):
                    BGM_queue.append(args)
                elif args == "stop":
                    BGM_queue.append(args)
                else:
                    raise ParserError(
                        '->[31m[ParserError]:->[0m The BGM "'
                        + args
                        + '" specified in setting line '
                        + str(i + 1)
                        + " is not exist!"
                    )
            elif target == "formula":
                if args in formula_available.keys():
                    formula = formula_available[args]
                elif args[:6] == "lambda":
                    try:
                        formula = eval(args)
                        print(
                            "->[33m[warning]:->[0m",
                            "Using lambda formula range ",
                            formula(0, 1, 2),
                            " in line",
                            i + 1,
                            ", which may cause unstableness during displaying!",
                        )

                    except Exception as e:
                        raise ParserError(
                            '->[31m[ParserError]:->[0m Unsupported formula "'
                            + args
                            + '" is specified in setting line '
                            + str(i + 1)
                            + "."
                        ) from e

                else:
                    raise ParserError(
                        '->[31m[ParserError]:->[0m Unsupported formula "'
                        + args
                        + '" is specified in setting line '
                        + str(i + 1)
                        + "."
                    )
            else:
                raise ParserError(
                    '->[31m[ParserError]:->[0m Unsupported setting "'
                    + target
                    + '" is specified in setting line '
                    + str(i + 1)
                    + "."
                )
        except Exception as E:
            print(E)
            raise ParserError(
                (
                    (
                        "->[31m[ParserError]:->[0m Parse exception occurred in setting line "
                        + str(i + 1)
                    )
                    + "."
                )
            ) from E

    def hitpoint(self, text: str, i: int):
        BGM_queue = self.BGM_queue
        render_arg = self.render_arg
        render_timeline = self.render_timeline
        break_point = self.break_point
        bulitin_media = self.bulitin_media
        this_background = self.this_background
        try:
            # 载入参数
            name_tx, heart_max, heart_begin, heart_end = RE.RE_hitpoint.findall(text)[0]
            heart_max = int(heart_max)
            heart_begin = int(heart_begin)
            heart_end = int(heart_end)
            # 建立小节
            this_timeline = pd.DataFrame(
                index=range(0, frame_rate * 4), dtype=str, columns=render_arg
            )

            # 背景
            # alpha_timeline,pos_timeline = am_methods('black',method_dur=frame_rate//2,this_duration=frame_rate*4,i=i)
            alpha_timeline = np.hstack(
                [
                    formula(0, 1, frame_rate // 2),
                    np.ones(frame_rate * 3 - frame_rate // 2),
                    formula(1, 0, frame_rate),
                ]
            )
            this_timeline["BG1"] = "black"  # 黑色背景
            this_timeline["BG1_a"] = alpha_timeline * 80
            this_timeline["BG2"] = this_background
            this_timeline["BG2_a"] = 100
            # 新建内建动画
            Auto_media_name = f"BIA_{str(i + 1)}"
            code_to_run = '{media_name}_{layer} = BuiltInAnimation(anime_type="hitpoint",anime_args=("{name}",{hmax},{hbegin},{hend}),screensize = {screensize},layer={layer})'
            code_to_run_0 = code_to_run.format(
                media_name=Auto_media_name,
                name=name_tx,
                hmax="%d" % heart_max,
                hbegin="%d" % heart_begin,
                hend="%d" % heart_end,
                screensize=str(screen_size),
                layer="0",
            )
            code_to_run_1 = code_to_run.format(
                media_name=Auto_media_name,
                name=name_tx,
                hmax="%d" % heart_max,
                hbegin="%d" % heart_begin,
                hend="%d" % heart_end,
                screensize=str(screen_size),
                layer="1",
            )
            code_to_run_2 = code_to_run.format(
                media_name=Auto_media_name,
                name=name_tx,
                hmax="%d" % heart_max,
                hbegin="%d" % heart_begin,
                hend="%d" % heart_end,
                screensize=str(screen_size),
                layer="2",
            )

            exec(code_to_run_0, None, media_list)  # 灰色框
            exec(code_to_run_1, None, media_list)  # 留下的血
            exec(code_to_run_2, None, media_list)  # 丢掉的血

            bulitin_media[Auto_media_name + "_0"] = code_to_run_0
            bulitin_media[Auto_media_name + "_1"] = code_to_run_1
            bulitin_media[Auto_media_name + "_2"] = code_to_run_2
            # 动画参数
            this_timeline["Am3"] = Auto_media_name + "_0"
            this_timeline["Am3_a"] = alpha_timeline * 100
            this_timeline["Am3_t"] = 0
            this_timeline["Am3_p"] = "NA"
            this_timeline["Am2"] = Auto_media_name + "_1"
            this_timeline["Am2_a"] = alpha_timeline * 100
            this_timeline["Am2_t"] = 0
            this_timeline["Am2_p"] = "NA"
            this_timeline["Am1"] = Auto_media_name + "_2"

            if heart_begin > heart_end:  # 掉血模式
                this_timeline["Am1_a"] = np.hstack(
                    [
                        formula(0, 100, frame_rate // 2),
                        np.ones(frame_rate * 2 - frame_rate // 2) * 100,
                        left(100, 0, frame_rate // 2),
                        np.zeros(frame_rate * 2 - frame_rate // 2),
                    ]
                )  # 0-0.5出现，2-2.5消失
                this_timeline["Am1_p"] = concat_xy(
                    np.zeros(frame_rate * 4),
                    np.hstack(
                        [
                            np.zeros(frame_rate * 2),  # 静止2秒
                            left(
                                0, -int(screen_size[1] * 0.3), frame_rate // 2
                            ),  # 半秒切走
                            int(screen_size[1] * 0.3)
                            * np.ones(frame_rate * 2 - frame_rate // 2),
                        ]
                    ),
                )  # 1.5秒停止
                this_timeline["Am1_t"] = 0
            else:  # 回血模式
                this_timeline["Am1_a"] = alpha_timeline * 100  # 跟随全局血量
                this_timeline["Am1_p"] = "NA"  # 不移动
                this_timeline["Am1_t"] = np.hstack(
                    [
                        np.zeros(frame_rate * 1),  # 第一秒静止
                        np.arange(0, frame_rate, 1),  # 第二秒播放
                        np.ones(frame_rate * 2) * (frame_rate - 1),
                    ]
                )  # 后两秒静止
            # 收尾
            if BGM_queue != []:
                this_timeline.loc[
                    0, "BGM"
                ] = BGM_queue.pop()  # 从BGM_queue里取出来一个 alpha 1.8.5
            render_timeline.append(this_timeline)
            break_point[i + 1] = break_point[i] + len(this_timeline.index)
        except Exception as E:
            print(E)
            raise ParserError(
                "->[31m[ParserError]:->[0m Parse exception occurred in hitpoint line "
                + str(i + 1)
                + "."
            ) from E

    def dice(self, text: str, i: int):
        BGM_queue = self.BGM_queue
        render_arg = self.render_arg
        render_timeline = self.render_timeline
        break_point = self.break_point
        bulitin_media = self.bulitin_media
        this_background = self.this_background
        try:
            # 获取参数
            dice_args = RE.RE_dice.findall(text[7:])
            if len(dice_args) == 0:
                raise ParserError(
                    "->[31m[ParserError]:->[0m",
                    "Invalid syntax, no dice args is specified!",
                )
            # 建立小节
            this_timeline = pd.DataFrame(
                index=range(frame_rate * 5), dtype=str, columns=render_arg
            )

            # 背景
            alpha_timeline = np.hstack(
                [
                    formula(0, 1, frame_rate // 2),
                    np.ones(frame_rate * 4 - frame_rate // 2),
                    formula(1, 0, frame_rate),
                ]
            )
            this_timeline["BG1"] = "black"  # 黑色背景
            this_timeline["BG1_a"] = alpha_timeline * 80
            this_timeline["BG2"] = this_background
            this_timeline["BG2_a"] = 100
            # 新建内建动画
            Auto_media_name = f"BIA_{str(i + 1)}"
            code_to_run = '{media_name}_{layer} = BuiltInAnimation(anime_type="dice",anime_args={dice_args},screensize = {screensize},layer={layer})'
            code_to_run_0 = code_to_run.format(
                media_name=Auto_media_name,
                dice_args=str(dice_args),
                screensize=str(screen_size),
                layer="0",
            )
            code_to_run_1 = code_to_run.format(
                media_name=Auto_media_name,
                dice_args=str(dice_args),
                screensize=str(screen_size),
                layer="1",
            )
            code_to_run_2 = code_to_run.format(
                media_name=Auto_media_name,
                dice_args=str(dice_args),
                screensize=str(screen_size),
                layer="2",
            )

            exec(code_to_run_0, None, media_list)  # 描述和检定值
            exec(code_to_run_1, None, media_list)  # 老虎机
            exec(code_to_run_2, None, media_list)  # 输出结果
            bulitin_media[Auto_media_name + "_0"] = code_to_run_0
            bulitin_media[Auto_media_name + "_1"] = code_to_run_1
            bulitin_media[Auto_media_name + "_2"] = code_to_run_2
            # 动画参数0
            this_timeline["Am3"] = Auto_media_name + "_0"
            this_timeline["Am3_a"] = alpha_timeline * 100
            this_timeline["Am3_t"] = 0
            this_timeline["Am3_p"] = "NA"
            # 1
            this_timeline["Am2"] = np.hstack(
                [
                    np.repeat(Auto_media_name + "_1", int(frame_rate * 2.5)),
                    np.repeat("NA", frame_rate * 5 - int(frame_rate * 2.5)),
                ]
            )  # 2.5s
            this_timeline["Am2_a"] = np.hstack(
                [
                    formula(0, 100, frame_rate // 2),
                    np.ones(int(frame_rate * 2.5) - 2 * frame_rate // 2) * 100,
                    formula(100, 0, frame_rate // 2),
                    np.zeros(frame_rate * 5 - int(frame_rate * 2.5)),
                ]
            )
            this_timeline["Am2_t"] = np.hstack(
                [
                    np.arange(0, int(frame_rate * 2.5)),
                    np.zeros(frame_rate * 5 - int(frame_rate * 2.5)),
                ]
            )
            this_timeline["Am2_p"] = "NA"
            # 2
            this_timeline["Am1"] = np.hstack(
                [
                    np.repeat("NA", frame_rate * 5 - int(frame_rate * 2.5)),
                    np.repeat(Auto_media_name + "_2", int(frame_rate * 2.5)),
                ]
            )
            this_timeline["Am1_a"] = np.hstack(
                [
                    np.zeros(frame_rate * 5 - int(frame_rate * 2.5)),
                    formula(0, 100, frame_rate // 2),
                    np.ones(int(frame_rate * 2.5) - frame_rate // 2 - frame_rate) * 100,
                    formula(100, 0, frame_rate),
                ]
            )
            this_timeline["Am1_t"] = 0
            this_timeline["Am1_p"] = "NA"
            # SE
            this_timeline.loc[0 : frame_rate // 3, "SE"] = "'./media/SE_dice.wav'"
            # 收尾
            if BGM_queue != []:
                this_timeline.loc[
                    0, "BGM"
                ] = BGM_queue.pop()  # 从BGM_queue里取出来一个 alpha 1.8.5
            render_timeline.append(this_timeline)
            break_point[i + 1] = break_point[i] + len(this_timeline.index)
        except Exception as E:
            print(E)
            raise ParserError(
                (
                    (
                        "->[31m[ParserError]:->[0m Parse exception occurred in dice line "
                        + str(i + 1)
                    )
                    + "."
                )
            ) from E

    def parser(self):
        render_timeline = self.render_timeline
        self.break_point = pd.Series(index=list(range(len(self.stdin_text))), dtype=int)
        self.break_point[0] = 0
        break_point = self.break_point
        bulitin_media = self.bulitin_media
        for i, text in enumerate(self.stdin_text):
            # 空白行 或者注释行
            if text == "" or text[0] == "#":
                self.break_point[i + 1] = self.break_point[i]
                continue
            elif text[0] == "[":
                # 从ts长度预设的 this_duration
                self.log(text, i)
                continue
            elif "<background>" in text:
                self.background_render(text, i)
                continue
            elif ("<set:" in text) & (">:" in text):
                self.set_method(text, i)
            elif text[:11] == "<hitpoint>:":
                self.hitpoint(text, i)
                continue
            elif text[:7] == "<dice>:":
                self.dice(text, i)
                continue
            else:
                raise ParserError(
                    f"->[31m[ParserError]:->[0m Unrecognized line: {str(i + 1)}."
                )
            break_point[i + 1] = break_point[i]
        render_timeline = pd.concat(render_timeline, axis=0)
        render_timeline.index = np.arange(0, len(render_timeline), 1)
        render_timeline = render_timeline.fillna("NA")  # 假设一共10帧
        timeline_diff = render_timeline.iloc[:-1].copy()  # 取第0-9帧
        timeline_diff.index = timeline_diff.index + 1  # 设置为第1-10帧
        timeline_diff.loc[0] = "NA"  # 再把第0帧设置为NA
        dropframe = (render_timeline == timeline_diff.sort_index()).all(
            axis=1
        )  # 这样，就是原来的第10帧和第9帧在比较了
        bulitin_media = pd.Series(bulitin_media, dtype=str)
        # 这样就去掉了，和前一帧相同的帧，节约了性能
        return render_timeline[dropframe == False].copy(), break_point, bulitin_media


# 渲染函数
def render(
    this_frame: dict[str, Union[str, int]],
    channel_list,
    media_list: dict[
        str,
        Union[
            Text,
            str,
            BuiltInAnimation,
            Text,
            StrokeText,
            Bubble,
            Animation,
            BGM,
            Audio,
        ],
    ],
    screen: pygame.surface.Surface,
):
    global zorder
    # global screen
    for layer in zorder:
        # 不渲染的条件：图层为"Na"，或者np.nan
        if (this_frame[layer] == "NA") | (this_frame[layer] != this_frame[layer]):
            continue
        elif this_frame[f"{layer}_a"] <= 0:  # 或者图层的透明度小于等于0(由于fillna("NA"),出现的异常)
            continue
        # global zorder, media_list

        # for layer in zorder:
        #     # 不渲染的条件：图层为"Na"，或者np.nan
        #     if (this_frame[layer] == "NA") | (this_frame[layer] != this_frame[layer]):
        #         continue
        #     elif this_frame[layer + "_a"] <= 0:  # 或者图层的透明度小于等于0(由于fillna("NA"),出现的异常)
        #         continue
        if this_frame[layer] not in media_list:
            raise RuntimeError(
                '->[31m[RenderError]:->[0m Undefined media object : "'
                + this_frame[layer]
                + '".'
            )
            continue
        media_name = this_frame[layer]
        if layer[:2] == "BG":
            try:
                media_list[media_name].display(
                    surface=screen,
                    alpha=this_frame[f"{layer}_a"],
                    adjust=this_frame[f"{layer}_p"],
                )  # type: ignore

            except Exception as e:
                raise RuntimeError(
                    '->[31m[RenderError]:->[0m Failed to render "'
                    + this_frame[layer]
                    + '" as Background.'
                ) from e

        elif layer[:2] == "Am":  # 兼容H_LG1(1)这种动画形式 alpha1.6.3
            try:
                media_name = this_frame[layer]
                media_list[media_name].display(
                    surface=screen,
                    alpha=this_frame[f"{layer}_a"],
                    adjust=f"{this_frame[f'{layer}_p']}",
                    frame=this_frame[f"{layer}_t"],
                )

            except Exception as e:
                logger.exception(e)
                raise RuntimeError(
                    '->[31m[RenderError]:->[0m Failed to render "'
                    + this_frame[layer]
                    + '" as Animation.'
                ) from e

        elif layer == "Bb":
            try:
                obj = media_list[media_name]
                obj.display(
                    surface=screen,
                    text=f"{this_frame[f'{layer}_main']}",
                    header=f"{this_frame[f'{layer}_header']}",
                    alpha=this_frame[f"{layer}_a"],
                    adjust=f"{this_frame[f'{layer}_p']}",
                )

            except Exception as e:
                raise RuntimeError(
                    '->[31m[RenderError]:->[0m Failed to render "'
                    + this_frame[layer]
                    + '" as Bubble.'
                ) from e

    for key in ["BGM", "Voice", "SE"]:
        if (this_frame[key] == "NA") | (this_frame[key] != this_frame[key]):  # 如果是空的
            continue
        elif this_frame[key] == "stop":  # a 1.6.0更新
            pygame.mixer.music.stop()  # 停止
            pygame.mixer.music.unload()  # 换碟
        elif this_frame[key] not in media_list:  # 不是预先定义的媒体，则一定是合法的路径
            if key == "BGM":
                temp_BGM = BGM(filepath=this_frame[key][1:-1])
                temp_BGM.display()
            else:
                temp_Audio = Audio(filepath=this_frame[key][1:-1])
                temp_Audio.display(channel=channel_list[key])  # 这里的参数需要是对象
        else:  # 预先定义的媒体
            try:
                media_name = this_frame[key]
                if key == "BGM":
                    media_list[media_name].display()
                    # 否则就直接播放对象
                else:
                    media_list[media_name].display(channel=channel_list[key])  # type: ignore
                    # 否则就直接播放对象
            except Exception as exc:
                raise RuntimeError(
                    '->[31m[RenderError]:->[0m Failed to play audio "'
                    + this_frame[layer]
                    + '"'
                ) from exc

            return 1


# 手动换行的l2l
def get_l2l(ts: str, text_dur, this_duration):  # 如果是手动换行的列
    lines = ts.split("#")
    wc_list = []
    len_this = 0
    for x, l in enumerate(lines):  # x是井号的数量
        len_this = len_this + len(l) + 1  # 当前行的长度
        # print(len_this,len(l),x,ts[0:len_this])
        wc_list.append(np.ones(text_dur * len(l)) * len_this)
    try:
        wc_list.append(
            np.ones(this_duration - (len(ts) - x) * text_dur) * len(ts)
        )  # this_duration > est # 1.6.1 update
        word_count_timeline = np.hstack(wc_list)
    except Exception:
        word_count_timeline = np.hstack(wc_list)  # this_duration < est
        word_count_timeline = word_count_timeline[:this_duration]
    return word_count_timeline.astype(int)


# 倒计时器
def timer(clock, screen, note_text, white, W, H):
    # global W, H
    white.display(screen)
    screen.blit(
        note_text.render("%d" % clock, fgcolor=(150, 150, 150, 255), size=0.0926 * H)[
            0
        ],
        (0.484 * W, 0.463 * H),
    )  # for 1080p
    pygame.display.update()
    pygame.time.delay(1000)


def stop_SE(channel_list: dict[str, pygame.mixer.Channel]):
    for Ch in channel_list.values():
        Ch.stop()


def pause_SE(stats, channel_list: dict[str, pygame.mixer.Channel]):
    if stats == 0:
        pygame.mixer.music.pause()
        for Ch in channel_list.values():
            Ch.pause()
    else:
        pygame.mixer.music.unpause()
        for Ch in channel_list.values():
            Ch.unpause()
